// helper for calling our API. pages are served by the same server so we can
// just use paths like "/restaurants"

import { clearSession, getToken } from "./session.js";

export class ApiError extends Error {
  constructor(message, { status = null, detail = null } = {}) {
    super(message);
    this.name = "ApiError";
    // null if we never got a response
    this.status = status;
    // "detail" from FastAPI's error response (if there is one)
    this.detail = detail;
  }
}

export async function apiRequest(path, { method = "GET", body } = {}) {
  const options = { method, headers: { Accept: "application/json" } };
  const token = getToken();
  if (token) options.headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError("Could not reach the server. Check that it is running.");
  }

  let data;
  try {
    data = await readJson(response);
  } catch {
    throw new ApiError("Could not read the server response. The request may have completed.", {
      status: response.status,
    });
  }
  if (!response.ok) {
    // the server rejected our token (expired, or the server restarted), so drop it
    if (response.status === 401 && token) clearSession();
    throw new ApiError(errorMessage(response.status, data, Boolean(token)), {
      status: response.status,
      detail: data?.detail ?? null,
    });
  }
  return data;
}

async function readJson(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    // 500s come back as plain text "Internal Server Error"
    return null;
  }
}

function errorMessage(status, data, signedIn) {
  if (status === 401) return signedIn ? "Your session has expired. Sign in again." : "Sign in to continue.";
  if (status === 403) return "This account is not allowed to do that.";
  if (typeof data?.detail === "string") return data.detail;
  if (status === 422) return "Some fields are invalid.";
  if (status >= 500) return "The server could not complete the request. Try again later.";
  return `Request failed (HTTP ${status}).`;
}
