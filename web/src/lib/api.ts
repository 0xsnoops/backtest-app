const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error ${res.status}`);
  }
  return res.json();
}

export const api = {
  register: (email: string, password: string) =>
    apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: async (email: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);
    const res = await fetch(`${API_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData.toString(),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    return data;
  },

  me: () => apiFetch("/api/auth/me"),

  createSimulation: (data: Record<string, unknown>) =>
    apiFetch("/api/simulations", { method: "POST", body: JSON.stringify(data) }),

  listSimulations: () => apiFetch("/api/simulations"),

  getSimulation: (id: string) => apiFetch(`/api/simulations/${id}`),

  listRounds: (simId: string) => apiFetch(`/api/simulations/${simId}/rounds`),

  startRound: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/start`, { method: "POST" }),

  getCandle: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/candle`),

  advance: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/advance`, { method: "POST" }),

  placeOrder: (simId: string, roundId: string, order: Record<string, unknown>) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/orders`, {
      method: "POST",
      body: JSON.stringify(order),
    }),

  listOrders: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/orders`),

  listFills: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/fills`),

  getRoundMetrics: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/metrics`),

  getSimMetrics: (simId: string) =>
    apiFetch(`/api/simulations/${simId}/metrics`),

  replayRound: (simId: string, roundId: string) =>
    apiFetch(`/api/simulations/${simId}/rounds/${roundId}/replay`, { method: "POST" }),
};

export function createWS(token: string): WebSocket {
  return new WebSocket(`${WS_URL}/ws?token=${token}`);
}

export { getToken };
