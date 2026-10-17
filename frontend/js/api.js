// Shared helper for calling the REST API. Pages are served from the same
// origin as the API, so paths are relative (e.g. "/restaurants").

export class ApiError extends Error {
  constructor(message, { status = null, detail = null } = {}) {
    super(message);
    this.name = "ApiError";
    // null when the request never reached the server.
    this.status = status;
    // The "detail" field of a FastAPI error body, when there is one.
    this.detail = detail;
  }
}

export async function apiRequest(path, { method = "GET", body } = {}) {
  const options = { method, headers: { Accept: "application/json" } };
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

  const data = await readJson(response);
  if (!response.ok) {
    throw new ApiError(errorMessage(response.status, data), {
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
    // e.g. the plain-text "Internal Server Error" body of an HTTP 500.
    return null;
  }
}

function errorMessage(status, data) {
  if (typeof data?.detail === "string") return data.detail;
  if (status === 422) return "Some fields are invalid.";
  if (status >= 500) return "The server could not complete the request. Try again later.";
  return `Request failed (HTTP ${status}).`;
}
