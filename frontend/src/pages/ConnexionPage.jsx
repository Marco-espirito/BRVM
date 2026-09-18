import { useState } from "react";
import { connexion, demanderReinitialisation, inscription, reinitialiserMotDePasse } from "../api.js";

export default function ConnexionPage({ onConnexion }) {
  const jetonInitial = new URLSearchParams(window.location.search).get("reset_token");
  const [mode, setMode] = useState(jetonInitial ? "reinitialisation" : "connexion");
  const [form, setForm] = useState({ nom: "", email: "", mot_de_passe: "" });
  const [erreur, setErreur] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [lienDev, setLienDev] = useState("");
  const [motDePasseVisible, setMotDePasseVisible] = useState(false);
  async function envoyer(e) {
    e.preventDefault(); setErreur(""); setConfirmation("");
    try {
      if (mode === "oubli") {
        const resultat = await demanderReinitialisation(form.email);
        setConfirmation(resultat.message); setLienDev(resultat.lien_developpement ?? ""); return;
      }
      if (mode === "reinitialisation") {
        const resultat = await reinitialiserMotDePasse(jetonInitial, form.mot_de_passe);
        window.history.replaceState({}, "", window.location.pathname);
        setConfirmation(resultat.message); setMode("connexion"); setForm({ ...form, mot_de_passe: "" }); return;
      }
      const u = mode === "connexion" ? await connexion(form.email, form.mot_de_passe) : await inscription(form.email, form.mot_de_passe, form.nom);
      onConnexion(u);
    } catch (err) { setErreur(err.message); }
  }
  const textes = { connexion: "Connecte-toi pour retrouver tes portefeuilles sur tous tes appareils.", inscription: "Crée ton espace personnel sécurisé.", oubli: "Indique ton e-mail pour recevoir un lien valable 30 minutes.", reinitialisation: "Choisis un nouveau mot de passe sécurisé." };
  return <div className="connexion-page"><div className="connexion-carte"><h1>📈 BRVM Explorer</h1><p>{textes[mode]}</p><form onSubmit={envoyer}>
    {mode === "inscription" && <label>Nom<input required value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} /></label>}
    {mode !== "reinitialisation" && <label>E-mail<input type="email" autoComplete="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>}
    {mode !== "oubli" && <label>{mode === "reinitialisation" ? "Nouveau mot de passe" : "Mot de passe"}<span className="champ-mot-de-passe"><input type={motDePasseVisible ? "text" : "password"} minLength="10" maxLength="128" autoComplete={mode === "connexion" ? "current-password" : "new-password"} required value={form.mot_de_passe} onChange={(e) => setForm({ ...form, mot_de_passe: e.target.value })} /><button type="button" className="bouton-visibilite" aria-label={motDePasseVisible ? "Masquer le mot de passe" : "Afficher le mot de passe"} title={motDePasseVisible ? "Masquer le mot de passe" : "Afficher le mot de passe"} onClick={() => setMotDePasseVisible((visible) => !visible)}>{motDePasseVisible ? "🙈" : "👁️"}</button></span></label>}
    {erreur && <p className="erreur-auth">{erreur}</p>}{confirmation && <p className="succes-auth">{confirmation}</p>}
    {lienDev && <a className="lien-dev-reset" href={lienDev}>Ouvrir le lien local de réinitialisation</a>}
    <button className="btn">{{ connexion: "Se connecter", inscription: "Créer mon compte", oubli: "Envoyer le lien", reinitialisation: "Modifier mon mot de passe" }[mode]}</button>
  </form>
  {mode === "connexion" && <button className="lien-auth" onClick={() => setMode("oubli")}>Mot de passe oublié ?</button>}
  <button className="lien-auth" onClick={() => { setMode(mode === "connexion" ? "inscription" : "connexion"); setErreur(""); setConfirmation(""); setLienDev(""); setMotDePasseVisible(false); }}>{mode === "connexion" ? "Créer un compte" : "Retour à la connexion"}</button>
  </div></div>;
}
