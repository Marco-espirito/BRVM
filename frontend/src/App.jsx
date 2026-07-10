import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { deconnexion, evaluerAlertes, getMoi, getStatutDonnees, marquerAlerteLue } from "./api.js";
import ConnexionPage from "./pages/ConnexionPage.jsx";

// Layout commun : un en-tete + la page courante (Outlet).
export default function App() {
  const location = useLocation();
  const [utilisateur, setUtilisateur] = useState(undefined);
  const [statutDonnees, setStatutDonnees] = useState(null);
  useEffect(() => { getMoi().then(setUtilisateur).catch(() => setUtilisateur(null)); }, []);
  useEffect(() => { if (utilisateur) getStatutDonnees().then(setStatutDonnees).catch(() => setStatutDonnees(null)); }, [utilisateur]);
  useEffect(() => {
    if (!utilisateur) return undefined;
    async function verifier() {
      try {
        const evenements = await evaluerAlertes();
        for (const evenement of evenements) {
          if ("Notification" in window && Notification.permission === "granted") {
            new Notification(evenement.titre, { body: evenement.message, tag: `brvm-${evenement.id}` });
            await marquerAlerteLue(evenement.id);
          }
        }
      } catch { /* backend indisponible : le reste de l'application continue */ }
    }
    verifier();
    const intervalle = setInterval(verifier, 5 * 60 * 1000);
    return () => clearInterval(intervalle);
  }, [utilisateur]);
  if (utilisateur === undefined) return <p className="info">Chargement…</p>;
  if (!utilisateur) return <ConnexionPage onConnexion={setUtilisateur} />;
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          📈 BRVM Explorer
        </Link>
        <span className="sous-titre">
          Bourse Régionale des Valeurs Mobilières · Afrique de l'Ouest
        </span>
        <nav className="onglets">
          <NavLink to="/tableau-de-bord" className="onglet">
            🧭 Tableau de bord
          </NavLink>
          <NavLink to="/" end className="onglet">
            📋 Actions
          </NavLink>
          <NavLink to="/portefeuille" className="onglet">
            💼 Mon portefeuille
          </NavLink>
          <NavLink to="/alertes" className="onglet">
            🔔 Mes alertes
          </NavLink>
          <NavLink to="/analyse" className={({ isActive }) => `onglet ${(isActive || ["/comparateur", "/screener", "/backtest"].includes(location.pathname)) ? "active" : ""}`}>
            🧭 Analyse
          </NavLink>
          <NavLink to="/calendrier" className="onglet">
            📅 Dividendes
          </NavLink>
          <NavLink to="/objectif" className="onglet">
            🎯 Objectif
          </NavLink>
        </nav>
        <div className="actions-compte"><Link className="btn-compte" to="/parametres">⚙️ {utilisateur.nom}</Link><button className="btn-deconnexion" onClick={async () => { await deconnexion(); setUtilisateur(null); }}>Déconnexion</button></div>
        {statutDonnees && <StatutDonnees statut={statutDonnees} />}
      </header>
      <main className="contenu">
        <Outlet context={{ utilisateur, setUtilisateur }} />
      </main>
      <footer className="footer">
        Données publiques brvm.org · Projet d'apprentissage, ne constitue pas un
        conseil en investissement.
      </footer>
    </div>
  );
}

function StatutDonnees({ statut }) {
  const libelles = { a_jour: "Données à jour", a_verifier: "Données à vérifier", ancien: "Données anciennes", indisponible: "Données indisponibles" };
  const dateSeance = statut.derniere_seance
    ? new Date(`${statut.derniere_seance}T12:00:00`).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
    : "aucune séance";
  const heure = statut.recupere_le
    ? new Date(`${statut.recupere_le}Z`).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    : "heure inconnue";
  return <div className={`statut-donnees ${statut.statut}`} title={`Dernière récupération : ${heure}. Couverture : ${statut.actions_couvertes}/${statut.actions_total} actions.`}>
    <span className="statut-point" />
    <span><strong>{libelles[statut.statut]}</strong><small>Séance du {dateSeance} · {statut.actions_couvertes}/{statut.actions_total} actions</small></span>
  </div>;
}
