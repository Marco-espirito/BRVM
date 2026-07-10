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
