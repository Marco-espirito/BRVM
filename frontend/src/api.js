// Petit client pour parler a l'API FastAPI du backend.
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const fetch = (url, options = {}) => window.fetch(url, { ...options, credentials: "include" });

export async function inscription(email, mot_de_passe, nom) {
  const r = await fetch(`${BASE}/auth/inscription`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, mot_de_passe, nom }) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Inscription impossible"); return r.json();
}
export async function connexion(email, mot_de_passe) {
  const r = await fetch(`${BASE}/auth/connexion`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, mot_de_passe }) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Connexion impossible"); return r.json();
}
export async function getMoi() { const r = await fetch(`${BASE}/auth/moi`); if (!r.ok) return null; return r.json(); }
export async function deconnexion() { await fetch(`${BASE}/auth/deconnexion`, { method: "POST" }); }
export async function modifierProfil(nom) { const r = await fetch(`${BASE}/auth/profil`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom }) }); if (!r.ok) throw new Error((await r.json()).detail ?? "Modification impossible"); return r.json(); }
export async function changerMotDePasse(mot_de_passe_actuel, nouveau_mot_de_passe) { const r = await fetch(`${BASE}/auth/mot-de-passe`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mot_de_passe_actuel, nouveau_mot_de_passe }) }); if (!r.ok) throw new Error((await r.json()).detail ?? "Modification impossible"); return r.json(); }
export async function getMesPortefeuilles() { const r = await fetch(`${BASE}/mes-portefeuilles`); if (!r.ok) throw new Error("Connexion requise"); return r.json(); }
export async function creerPortefeuille(nom) { const r = await fetch(`${BASE}/mes-portefeuilles`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom }) }); if (!r.ok) throw new Error("Création impossible"); return r.json(); }
export async function renommerPortefeuille(id, nom) { const r = await fetch(`${BASE}/mes-portefeuilles/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nom }) }); if (!r.ok) throw new Error((await r.json()).detail ?? "Modification impossible"); return r.json(); }
export async function supprimerPortefeuille(id) { const r = await fetch(`${BASE}/mes-portefeuilles/${id}`, { method: "DELETE" }); if (!r.ok) throw new Error((await r.json()).detail ?? "Suppression impossible"); return r.json(); }
export async function getWatchlist() { const r = await fetch(`${BASE}/watchlist`); if (!r.ok) return []; return r.json(); }
export async function ajouterWatchlist(symbole) { await fetch(`${BASE}/watchlist/${symbole}`, { method: "PUT" }); }
export async function retirerWatchlist(symbole) { await fetch(`${BASE}/watchlist/${symbole}`, { method: "DELETE" }); }

export async function getActions() {
  const r = await fetch(`${BASE}/actions`);
  if (!r.ok) throw new Error("Erreur chargement des actions");
  return r.json();
}

export async function getStatutDonnees() {
  const r = await fetch(`${BASE}/donnees/statut`);
  if (!r.ok) throw new Error("Statut des données indisponible");
  return r.json();
}

export async function getAction(symbole) {
  const r = await fetch(`${BASE}/actions/${symbole}`);
  if (!r.ok) throw new Error("Action introuvable");
  return r.json();
}

// Formate un nombre en FCFA : 28500 -> "28 500 FCFA"
export function formatFCFA(n) {
  if (n === null || n === undefined) return "-";
  return new Intl.NumberFormat("fr-FR").format(n) + " FCFA";
}

export async function getTopActions(limit = 10) {
  const r = await fetch(`${BASE}/top-actions?limit=${limit}`);
  if (!r.ok) throw new Error("Erreur chargement du top");
  return r.json();
}

// --- Portefeuille virtuel (achats fictifs pour apprendre) ---

export async function getPortefeuille(portefeuilleId) {
  const r = await fetch(`${BASE}/portefeuille?portefeuille_id=${portefeuilleId}`);
  if (!r.ok) throw new Error("Erreur chargement du portefeuille");
  return r.json();
}

export async function acheterPosition(symbole, quantite, frais_courtage_pct = 0, portefeuille_id = null) {
  const r = await fetch(`${BASE}/portefeuille/positions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbole, quantite, frais_courtage_pct, portefeuille_id }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Achat impossible");
  return r.json();
}

export async function mouvementEspeces(type, montant, portefeuilleId) {
  const r = await fetch(`${BASE}/portefeuille/especes?portefeuille_id=${portefeuilleId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type, montant }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Mouvement impossible");
  return r.json();
}

export async function vendrePartiellement(id, quantite, frais_courtage_pct = 0, fiscalite_pct = 0, portefeuilleId = null) {
  const r = await fetch(`${BASE}/portefeuille/positions/${id}/vendre?portefeuille_id=${portefeuilleId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantite, frais_courtage_pct, fiscalite_pct }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Vente impossible");
  return r.json();
}

export const exportTransactionsCsv = (id) => `${BASE}/portefeuille/export.csv?portefeuille_id=${id}`;

export async function getAlertes() {
  const r = await fetch(`${BASE}/alertes`);
  if (!r.ok) throw new Error("Erreur chargement des alertes");
  return r.json();
}

export async function creerAlerte(alerte) {
  const r = await fetch(`${BASE}/alertes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(alerte),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Création impossible");
  return r.json();
}

export async function supprimerAlerte(id) {
  const r = await fetch(`${BASE}/alertes/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Suppression impossible");
}

export async function evaluerAlertes() {
  const r = await fetch(`${BASE}/alertes/evaluer`, { method: "POST" });
  if (!r.ok) throw new Error("Vérification des alertes impossible");
  return r.json();
}

export async function marquerAlerteLue(id) {
  await fetch(`${BASE}/alertes/evenements/${id}/lire`, { method: "POST" });
}

export async function getCalendrierDividendes(portefeuilleId = null) {
  const suffixe = portefeuilleId ? `?portefeuille_id=${portefeuilleId}` : "";
  const r = await fetch(`${BASE}/dividendes/calendrier${suffixe}`);
  if (!r.ok) throw new Error("Erreur chargement du calendrier");
  return r.json();
}

export async function lancerBacktest(parametres) {
  const r = await fetch(`${BASE}/backtest`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parametres),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Backtest impossible");
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
