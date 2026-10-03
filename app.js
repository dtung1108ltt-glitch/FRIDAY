const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");
const welcome = document.querySelector("#welcome");
const messagesElement = document.querySelector("#messages");
const newChatButton = document.querySelector("#new-chat");
const serviceStatus = document.querySelector("#service-status-text");
const serviceStatusIndicator = document.querySelector("#service-status-indicator");

let history = [];
let busy = false;

async function refreshServiceStatus() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) throw new Error("Backend health check failed");
    const health = await response.json();
    serviceStatus.textContent = health.configured ? "Đang hoạt động" : "Cần cấu hình HF_TOKEN";
    serviceStatusIndicator.classList.toggle("offline", !health.configured);
    serviceStatus.parentElement.title = `${health.provider} · ${health.model}`;
  } catch {
    serviceStatus.textContent = "Backend chưa kết nối";
    serviceStatusIndicator.classList.add("offline");
  }
}

function scrollToLatest() {
  messagesElement.scrollIntoView({ block: "end", behavior: "smooth" });
}

function addMessage(role, text, { typing = false } = {}) {
  const message = document.createElement("article");
  message.className = `message ${role === "user" ? "user" : "assistant"}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "B" : "F";
  avatar.setAttribute("aria-hidden", "true");

  const body = document.createElement("div");
  body.className = typing ? "message-body typing" : "message-body";
  if (typing) {
    body.setAttribute("aria-label", "FRIDAY đang suy nghĩ");
    for (let index = 0; index < 3; index += 1) {
      body.append(document.createElement("span"));
    }
  } else {
    body.textContent = text;
  }

  message.append(avatar, body);
  messagesElement.append(message);
  scrollToLatest();
  return message;
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message || busy) return;

  welcome.hidden = true;
  messagesElement.classList.add("active");
  history.push({ role: "user", text: message });
  addMessage("user", message);
  input.value = "";
  input.style.height = "auto";
  busy = true;
  sendButton.disabled = true;
  const pending = addMessage("model", "", { typing: true });

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const result = await response.json();
    pending.remove();
    if (!response.ok) {
      history.pop();
      addMessage("model", `Mình chưa thể trả lời: ${result.error || result.detail || "Đã có lỗi xảy ra."}`);
      return;
    }
    history.push({ role: "model", text: result.reply });
    addMessage("model", result.reply);
  } catch {
    pending.remove();
    history.pop();
    addMessage("model", "Không kết nối được với FRIDAY. Hãy kiểm tra kết nối mạng rồi thử lại nhé.");
  } finally {
    busy = false;
    sendButton.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void sendMessage(input.value);
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => void sendMessage(button.dataset.prompt || ""));
});

function startNewChat() {
  if (busy) return;
  history = [];
  messagesElement.replaceChildren();
  messagesElement.classList.remove("active");
  welcome.hidden = false;
  input.value = "";
  input.focus();
}

newChatButton.addEventListener("click", startNewChat);
void refreshServiceStatus();
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    startNewChat();
  }
});
