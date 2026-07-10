import { Link, Outlet } from "react-router-dom";

// Layout commun : un en-tete + la page courante (Outlet).
export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">
          📈 BRVM Explorer
        </Link>
        <span className="sous-titre">
          Bourse Régionale des Valeurs Mobilières · Afrique de l'Ouest
        </span>
      </header>
      <main className="contenu">
        <Outlet />
      </main>
      <footer className="footer">
        Données publiques brvm.org · Projet d'apprentissage, ne constitue pas un
        conseil en investissement.
      </footer>
    </div>
  );
}
