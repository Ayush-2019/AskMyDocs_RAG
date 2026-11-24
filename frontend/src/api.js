
const BASE_URL = "/api";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || res.statusText, res.status);
  }

  return res.json();
}

export async function uploadFiles(files) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));

  const res = await fetch(`${BASE_URL}/upload`, {
    method: "POST",
    body: form, // don't set Content-Type — browser adds boundary
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || res.statusText, res.status);
  }

  return res.json();
}


export async function askQuestion(question) {
  return request("/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}


export async function checkHealth() {
  return request("/health");
}


export async function getStats() {
  return request("/stats");
}
