import { useState } from "react";
import { connexion, inscription } from "../api.js";

export default function ConnexionPage({ onConnexion }) {
  const [mode, setMode] = useState("connexion");
  const [form, setForm] = useState({ nom: "", email: "", mot_de_passe: "" });
  const [erreur, setErreur] = useState("");
  async function envoyer(e) { e.preventDefault(); setErreur(""); try { const u = mode === "connexion" ? await connexion(form.email, form.mot_de_passe) : await inscription(form.email, form.mot_de_passe, form.nom); onConnexion(u); } catch (err) { setErreur(err.message); } }
  return <div className="connexion-page"><div className="connexion-carte"><h1>📈 BRVM Explorer</h1><p>{mode === "connexion" ? "Connecte-toi pour retrouver tes portefeuilles sur tous tes appareils." : "Crée ton espace personnel sécurisé."}</p><form onSubmit={envoyer}>{mode === "inscription" && <label>Nom<input required value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} /></label>}<label>E-mail<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label><label>Mot de passe<input type="password" minLength="10" required value={form.mot_de_passe} onChange={(e) => setForm({ ...form, mot_de_passe: e.target.value })} /></label>{erreur && <p className="erreur-auth">{erreur}</p>}<button className="btn">{mode === "connexion" ? "Se connecter" : "Créer mon compte"}</button></form><button className="lien-auth" onClick={() => setMode(mode === "connexion" ? "inscription" : "connexion")}>{mode === "connexion" ? "Créer un compte" : "J’ai déjà un compte"}</button></div></div>;
}
