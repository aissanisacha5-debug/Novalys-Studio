// Accès à l'API locale de Nova. Le jeton est injecté par le serveur dans la page.
const TOKEN = document.querySelector('meta[name="jarvis-token"]').content;

export class ApiError extends Error {
  constructor(err, status) {
    super(err?.message || "Erreur inconnue");
    this.code = err?.code; this.details = err?.details || {}; this.status = status;
  }
}

export async function api(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: { "X-Jarvis-Token": TOKEN, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError({ code: "hors_ligne", message: "Nova ne répond pas. Le service local est peut-être arrêté." }, 0);
  }
  if (res.status === 401) {
    // Nova a redémarré (nouveau jeton) : on recharge la page, une fois par minute au plus.
    let last = 0;
    try { last = Number(sessionStorage.getItem("jarvis-reload") || 0); } catch { /* stockage indisponible */ }
    if (Date.now() - last > 60000) {
      try { sessionStorage.setItem("jarvis-reload", String(Date.now())); } catch { /* ignore */ }
      location.reload();
    }
  }
  let json = null;
  try { json = await res.json(); } catch { /* réponse vide */ }
  if (!res.ok || !json?.ok) throw new ApiError(json?.error || { message: `HTTP ${res.status}` }, res.status);
  return json.data;
}

export const get = (p) => api("GET", p);
export const post = (p, b = {}) => api("POST", p, b);
export const patch = (p, b = {}) => api("PATCH", p, b);
export const del = (p) => api("DELETE", p);

// Flux d'événements temps réel (SSE) avec reconnexion automatique.
export function stream(onEvent, onStatus) {
  let es;
  const open = () => {
    es = new EventSource(`/api/stream?token=${encodeURIComponent(TOKEN)}`);
    es.onopen = () => onStatus?.(true);
    es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch { /* ignore */ } };
    es.onerror = () => { onStatus?.(false); };
  };
  open();
  return () => es?.close();
}
