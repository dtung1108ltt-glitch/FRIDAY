# FRIDAY AI

FRIDAY là ứng dụng chat AI tiếng Việt gồm giao diện web (HTML/CSS/JavaScript) và backend Python (FastAPI). Trợ lý có system prompt, tên và phong cách riêng; câu trả lời được tạo bởi model mã nguồn mở **Qwen3-4B-Instruct-2507** qua Hugging Face Inference Providers. FRIDAY là ứng dụng AI tùy biến dựa trên model nền Qwen3, không phải model nền tảng được huấn luyện độc lập.

Inference Providers có hạn mức miễn phí phụ thuộc tài khoản, model, provider và chính sách hiện hành; có thể cần Hugging Face token với quyền gọi Inference Providers.

## Yêu cầu

- Python 3.10 trở lên.
- Hugging Face token tạo tại [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), có quyền gọi Inference Providers.

## Cài đặt và chạy trên Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:HF_TOKEN = "hf_token_cua_ban"
python main.py
```

Mở [http://127.0.0.1:3000](http://127.0.0.1:3000). Token được đọc ở backend và không được gửi xuống trình duyệt.

Trong PowerShell bị chặn kích hoạt virtualenv, có thể bỏ qua bước activate và chạy trực tiếp:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:HF_TOKEN = "hf_token_cua_ban"
.\.venv\Scripts\python.exe main.py
```

### Cấu hình tùy chọn

- `HF_MODEL`: model Hugging Face; mặc định `Qwen/Qwen3-4B-Instruct-2507`.
- `HOST`: địa chỉ bind; mặc định `127.0.0.1`. Chỉ dùng `0.0.0.0` khi cần truy cập từ máy khác và đã cấu hình bảo vệ phù hợp.
- `PORT`: cổng backend; mặc định `3000`.
- `LOG_LEVEL`: mức log; mặc định `INFO`.

Có thể dùng [.env.example](./.env.example) làm mẫu tham khảo. Ứng dụng đọc cấu hình từ biến môi trường; không đưa token thật vào mã nguồn hoặc frontend.

## API

- `GET /api/health`: trạng thái cấu hình backend, model và provider.
- `POST /api/chat`: gửi lịch sử chat dạng `{ "messages": [{ "role": "user", "text": "..." }] }`; vai trò trợ lý trong lịch sử dùng `"model"`.
- `GET /docs`: tài liệu API tương tác FastAPI.

Chạy backend ở chế độ phát triển:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 3000
```

## Cấu trúc

- `main.py`: FastAPI, xác thực/kiểm tra dữ liệu, gọi Hugging Face và phục vụ frontend.
- `index.html`, `styles.css`, `app.js`: giao diện chat và kết nối API.
- `requirements.txt`: thư viện Python.
