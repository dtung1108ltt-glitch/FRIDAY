import logging
import os
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "Qwen/Qwen3-4B-Instruct-2507"
HUGGING_FACE_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
SYSTEM_PROMPT = (
    "Bạn là FRIDAY, một trợ lý AI có danh tính và phong cách riêng: bình tĩnh, "
    "sắc sảo, thân thiện, chủ động và thực tế. Trả lời bằng tiếng Việt theo mặc "
    "định, trừ khi người dùng yêu cầu ngôn ngữ khác. Trình bày rõ ràng, súc tích "
    "nhưng đủ ý; ưu tiên hướng dẫn có thể áp dụng. Bạn được xây dựng dựa trên "
    "model mã nguồn mở Qwen3. Khi được hỏi, hãy nói trung thực rằng FRIDAY là "
    "trợ lý AI do dự án này xây dựng trên nền Qwen3, không tuyên bố FRIDAY là "
    "một model nền tảng được huấn luyện độc lập. Không bịa đặt thông tin; hãy "
    "nêu rõ khi chưa chắc chắn."
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("friday")
app = FastAPI(title="FRIDAY AI", version="1.0.0")


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "model"]
    text: str = Field(min_length=1, max_length=12_000)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tin nhắn không được để trống.")
        return value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=100)


def configured_model() -> str:
    return os.getenv("HF_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def configured_token() -> str | None:
    return os.getenv("HF_TOKEN", "").strip() or None


def extract_provider_error(payload: object) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error:
            return error
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
    return "Hugging Face Inference Providers không thể xử lý yêu cầu."


def extract_reply(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ).strip()
    return ""


@app.middleware("http")
async def prevent_caching_api_responses(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
async def stylesheet() -> FileResponse:
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
async def frontend_script() -> FileResponse:
    return FileResponse(ROOT / "app.js", media_type="text/javascript")


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "configured": configured_token() is not None,
            "model": configured_model(),
            "provider": "Hugging Face Inference Providers",
        }
    )


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> JSONResponse:
    token = configured_token()
    if token is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "FRIDAY chưa được cấu hình Hugging Face token. "
                "Hãy thiết lập HF_TOKEN rồi khởi động lại ứng dụng."
            ),
        )

    messages = payload.messages[-20:]
    if messages[-1].role != "user":
        raise HTTPException(
            status_code=400,
            detail="Tin nhắn cuối cùng phải là câu hỏi của người dùng.",
        )

    request_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[
            {
                "role": "assistant" if message.role == "model" else "user",
                "content": message.text,
            }
            for message in messages
        ],
    ]
    request_body = {
        "model": configured_model(),
        "messages": request_messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                HUGGING_FACE_CHAT_URL,
                headers={"Authorization": f"Bearer {token}"},
                json=request_body,
            )
    except httpx.TimeoutException as error:
        logger.warning("Hugging Face request timed out: %s", error)
        raise HTTPException(
            status_code=504,
            detail="FRIDAY chờ model quá lâu. Vui lòng thử lại sau.",
        ) from error
    except httpx.RequestError as error:
        logger.warning("Hugging Face request failed: %s", error)
        raise HTTPException(
            status_code=502,
            detail="Không kết nối được với Hugging Face. Hãy kiểm tra mạng và thử lại.",
        ) from error

    try:
        provider_payload = response.json()
    except ValueError:
        provider_payload = {}

    if response.is_error:
        detail = extract_provider_error(provider_payload)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail=detail)
        if response.status_code in (401, 403):
            raise HTTPException(
                status_code=502,
                detail=(
                    "Hugging Face từ chối token. Hãy kiểm tra HF_TOKEN và quyền "
                    "Inference Providers của token."
                ),
            )
        logger.warning("Hugging Face returned HTTP %s: %s", response.status_code, detail)
        raise HTTPException(status_code=502, detail=detail)

    reply = extract_reply(provider_payload)
    if not reply:
        raise HTTPException(
            status_code=502,
            detail="FRIDAY chưa nhận được câu trả lời hợp lệ từ model. Hãy thử lại.",
        )
    return JSONResponse({"reply": reply})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "3000")),
        reload=os.getenv("FRIDAY_RELOAD", "").lower() == "true",
    )
