// signed-in session (#95). kept in sessionStorage, which can be missing or blocked,
// so every access is guarded and the pages work signed out

const TOKEN_KEY = "accessToken";
const CUSTOMER_KEY = "customer";

function read(key) {
  try {
    return globalThis.sessionStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function getToken() {
  return read(TOKEN_KEY);
}

// {id, name, role} of the signed-in account, or null
export function getCustomer() {
  try {
    const customer = JSON.parse(read(CUSTOMER_KEY));
    return Number.isInteger(customer?.id) ? customer : null;
  } catch {
    return null;
  }
}

// takes the POST /auth/login response
export function saveSession({ access_token, customer }) {
  try {
    globalThis.sessionStorage.setItem(TOKEN_KEY, access_token);
  } catch {
    return false;
  }
  return saveCustomer(customer);
}

export function saveCustomer({ id, name, role }) {
  try {
    globalThis.sessionStorage.setItem(CUSTOMER_KEY, JSON.stringify({ id, name, role }));
    return true;
  } catch {
    return false;
  }
}

export function clearSession() {
  try {
    globalThis.sessionStorage.removeItem(TOKEN_KEY);
    globalThis.sessionStorage.removeItem(CUSTOMER_KEY);
  } catch {
    // nothing stored, nothing to clear
  }
}
