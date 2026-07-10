import { useEffect, useState } from "react";
import { creerAlerte, getActions, getAlertes, supprimerAlerte } from "../api.js";

const TYPES = {
  cours_superieur: "Cours supérieur à",
  cours_inferieur: "Cours inférieur à",
  rendement_superieur: "Rendement supérieur à",
  nouveau_dividende: "Nouveau dividende",
  detachement: "Date de détachement annoncée",
  rappel_detachement: "Rappel avant détachement",
};

export default function AlertesPage() {
  const [actions, setActions] = useState([]);
  const [alertes, setAlertes] = useState([]);
  const [form, setForm] = useState({ symbole: "", type: "cours_inferieur", seuil: "", email: "" });
  const [erreur, setErreur] = useState("");

  async function charger() {
    const [liste, regles] = await Promise.all([getActions(), getAlertes()]);
    setActions(liste);
    setAlertes(regles);
    if (!form.symbole && liste.length) setForm((f) => ({ ...f, symbole: liste[0].symbole }));
  }
  useEffect(() => { charger().catch((e) => setErreur(e.message)); }, []);

  const avecSeuil = ["cours_superieur", "cours_inferieur", "rendement_superieur", "rappel_detachement"].includes(form.type);
  async function ajouter(e) {
    e.preventDefault();
    setErreur("");
    try {
      await creerAlerte({ ...form, seuil: avecSeuil ? Number(form.seuil) : null, email: form.email || null });
      setForm((f) => ({ ...f, seuil: "" }));
      await charger();
    } catch (err) { setErreur(err.message); }
  }
  async function activerNavigateur() {
    if (!("Notification" in window)) return setErreur("Ce navigateur ne prend pas en charge les notifications.");
    const permission = await Notification.requestPermission();
    if (permission !== "granted") setErreur("Permission de notification refusée.");
  }

  return (
    <div className="alertes-page">
      <div className="titre-actions">
        <div><h1>Alertes personnalisées</h1><p className="explication">Les règles sont vérifiées au chargement de l’application et après chaque mise à jour des données.</p></div>
        <button className="btn" onClick={activerNavigateur}>🔔 Activer les notifications</button>
      </div>
      {erreur && <p className="info erreur">{erreur}</p>}
      <form className="form-alerte" onSubmit={ajouter}>
        <label>Action<select value={form.symbole} onChange={(e) => setForm({ ...form, symbole: e.target.value })}>{actions.map((a) => <option key={a.symbole} value={a.symbole}>{a.symbole} — {a.nom}</option>)}</select></label>
        <label>Condition<select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{Object.entries(TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        {avecSeuil && <label>{form.type === "rendement_superieur" ? "Seuil (%)" : form.type === "rappel_detachement" ? "Jours avant" : "Seuil (FCFA)"}<input type="number" min="0.01" step={form.type === "rappel_detachement" ? "1" : "0.01"} required value={form.seuil} onChange={(e) => setForm({ ...form, seuil: e.target.value })} /></label>}
        <label>E-mail optionnel<input type="email" placeholder="nom@exemple.com" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <button className="btn" type="submit">Créer l’alerte</button>
      </form>

      <h2>Mes alertes</h2>
      {alertes.length === 0 ? <p className="info">Aucune alerte configurée.</p> : (
        <div className="liste-alertes">{alertes.map((a) => <div className="alerte-carte" key={a.id}>
          <div><strong>{a.symbole}</strong> · {TYPES[a.type]} {a.seuil != null && <strong>{a.seuil.toLocaleString("fr-FR")}{a.type === "rendement_superieur" ? " %" : a.type === "rappel_detachement" ? " jours" : " FCFA"}</strong>}<div className="explication">{a.email ? `Navigateur + ${a.email}` : "Notification navigateur"}</div></div>
          <button className="btn-vendre" onClick={async () => { await supprimerAlerte(a.id); await charger(); }}>Supprimer</button>
        </div>)}</div>
      )}
      <div className="note-fiscale"><strong>Envoi par e-mail :</strong> configure SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER et SMTP_PASSWORD sur le backend. Sans SMTP, les notifications navigateur restent disponibles.</div>
    </div>
  );
}
