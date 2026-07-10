// Petit client pour parler a l'API FastAPI du backend.
const BASE = "http://localhost:8000";

export async function getActions() {
  const r = await fetch(`${BASE}/actions`);
  if (!r.ok) throw new Error("Erreur chargement des actions");
  return r.json();
}

export async function getAction(symbole) {
  const r = await fetch(`${BASE}/actions/${symbole}`);
  if (!r.ok) throw new Error("Action introuvable");
  return r.json();
}

export async function refresh() {
  const r = await fetch(`${BASE}/refresh`, { method: "POST" });
  if (!r.ok) throw new Error("Erreur lors du rafraichissement");
  return r.json();
}

// Formate un nombre en FCFA : 28500 -> "28 500 FCFA"
export function formatFCFA(n) {
  if (n === null || n === undefined) return "-";
  return new Intl.NumberFormat("fr-FR").format(n) + " FCFA";
}

export async function getTopActions() {
  const r = await fetch(`${BASE}/top-actions`);
  if (!r.ok) throw new Error("Erreur chargement du top 10");
  return r.json();
}

// --- Portefeuille virtuel (achats fictifs pour apprendre) ---

export async function getPortefeuille() {
  const r = await fetch(`${BASE}/portefeuille`);
  if (!r.ok) throw new Error("Erreur chargement du portefeuille");
  return r.json();
}

export async function acheterPosition(symbole, quantite) {
  const r = await fetch(`${BASE}/portefeuille/positions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbole, quantite }),
  });
  if (!r.ok) throw new Error("Achat impossible");
  return r.json();
}

export async function vendrePosition(id) {
  const r = await fetch(`${BASE}/portefeuille/positions/${id}`, {
    method: "DELETE",
  });
  if (!r.ok) throw new Error("Vente impossible");
  return r.json();
}

// Parite FIXE garantie par accord monetaire UEMOA/France : pas besoin
// d'API de change, ce taux ne bouge jamais.
export const FCFA_PAR_EURO = 655.957;

export function enEuros(fcfa) {
  if (fcfa === null || fcfa === undefined) return null;
  return fcfa / FCFA_PAR_EURO;
}

// Formate un montant en euros : 6113.2 -> "6 113,20 €"
export function formatEUR(n) {
  if (n === null || n === undefined) return "-";
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(n);
}
