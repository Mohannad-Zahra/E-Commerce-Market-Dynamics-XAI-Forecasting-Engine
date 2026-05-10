/**
 * api.js
 * ------
 * Central configuration for the FastAPI backend.
 * All components import BASE_URL from here — change once, updates everywhere.
 */

export const BASE_URL = "http://localhost:8000";
export const N8N_CHAT_WEBHOOK = `${BASE_URL}/api/chat`;

/** Convenience fetch wrapper with JSON auto-parse */
export async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}
