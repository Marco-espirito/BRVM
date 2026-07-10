import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { changerMotDePasse, modifierProfil } from "../api.js";

export default function ParametresPage() {
  const { utilisateur, setUtilisateur } = useOutletContext();
  const [nom, setNom] = useState(utilisateur.nom);
  const [motsDePasse, setMotsDePasse] = useState({ actuel: "", nouveau: "", confirmation: "" });
  const [messageProfil, setMessageProfil] = useState("");
  const [messageSecurite, setMessageSecurite] = useState("");
  const [erreur, setErreur] = useState("");

  async function enregistrerProfil(e) {
    e.preventDefault(); setErreur(""); setMessageProfil("");
    try { const profil = await modifierProfil(nom); setUtilisateur(profil); setMessageProfil("Nom mis à jour."); }
    catch (err) { setErreur(err.message); }
  }
  async function enregistrerMotDePasse(e) {
    e.preventDefault(); setErreur(""); setMessageSecurite("");
    if (motsDePasse.nouveau !== motsDePasse.confirmation) return setErreur("Les deux nouveaux mots de passe ne correspondent pas.");
    try { await changerMotDePasse(motsDePasse.actuel, motsDePasse.nouveau); setMotsDePasse({ actuel: "", nouveau: "", confirmation: "" }); setMessageSecurite("Mot de passe modifié. Les autres appareils ont été déconnectés."); }
    catch (err) { setErreur(err.message); }
  }

  return <div className="parametres-page">
    <div><div className="dashboard-surtitle">Compte utilisateur</div><h1>Paramètres</h1><p className="explication">Gère ton identité affichée et la sécurité de ton compte.</p></div>
    {erreur && <p className="info erreur">{erreur}</p>}
    <div className="parametres-grille">
      <form className="parametres-carte" onSubmit={enregistrerProfil}>
        <div><span className="operation-etiquette">Profil</span><h2>Informations personnelles</h2></div>
        <label className="champ"><span>Adresse e-mail</span><input value={utilisateur.email} disabled /><small>L’adresse e-mail ne peut pas encore être modifiée.</small></label>
        <label className="champ"><span>Nom affiché</span><input maxLength="100" required value={nom} onChange={(e) => setNom(e.target.value)} /></label>
        {messageProfil && <p className="message-succes">{messageProfil}</p>}
        <button className="btn">Enregistrer le profil</button>
      </form>
      <form className="parametres-carte" onSubmit={enregistrerMotDePasse}>
        <div><span className="operation-etiquette">Sécurité</span><h2>Changer le mot de passe</h2></div>
        <label className="champ"><span>Mot de passe actuel</span><input type="password" autoComplete="current-password" required value={motsDePasse.actuel} onChange={(e) => setMotsDePasse({ ...motsDePasse, actuel: e.target.value })} /></label>
        <label className="champ"><span>Nouveau mot de passe</span><input type="password" minLength="10" maxLength="128" autoComplete="new-password" required value={motsDePasse.nouveau} onChange={(e) => setMotsDePasse({ ...motsDePasse, nouveau: e.target.value })} /><small>Au moins 10 caractères.</small></label>
        <label className="champ"><span>Confirmer le nouveau mot de passe</span><input type="password" minLength="10" maxLength="128" autoComplete="new-password" required value={motsDePasse.confirmation} onChange={(e) => setMotsDePasse({ ...motsDePasse, confirmation: e.target.value })} /></label>
        {messageSecurite && <p className="message-succes">{messageSecurite}</p>}
        <button className="btn">Changer le mot de passe</button>
      </form>
    </div>
  </div>;
}
