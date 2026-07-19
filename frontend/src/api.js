/**
 * API client for the Ask My Docs backend.
 *
 * All fetch calls go through the Vite proxy (/api → localhost:8000)
 * so we avoid CORS issues during development. In production,
 * update BASE_URL to the real backend origin.
 */

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

/**
 * Upload multiple files for ingestion.
 * @param {File[]} files - Browser File objects from an <input>.
 * @returns {{ results: object[], total_chunks: number }}
 */
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

/**
 * Ask a question and receive a cited answer.
 * @param {string} question
 * @returns {AskResponse}
 */
export async function askQuestion(question) {
  return request("/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

/**
 * Check backend health.
 * @returns {{ status: string, chunk_count: number }}
 */
export async function checkHealth() {
  return request("/health");
}

/**
 * Get index statistics.
 */
export async function getStats() {
  return request("/stats");
}
