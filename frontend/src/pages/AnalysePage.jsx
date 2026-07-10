import { Link } from "react-router-dom";

const OUTILS = [
  { icone: "🔎", titre: "Screener avancé", description: "Filtre les actions par rendement, liquidité, régularité du dividende, secteur, pays, prix et variation.", lien: "/screener", action: "Rechercher des actions" },
  { icone: "⚖️", titre: "Comparateur d’actions", description: "Compare de 2 à 5 entreprises sur une base 100, leurs performances, dividendes et niveaux de liquidité.", lien: "/comparateur", action: "Comparer des entreprises" },
  { icone: "🧪", titre: "Backtesting pédagogique", description: "Observe ce qu’auraient donné différentes stratégies sur l’historique disponible, frais et dividendes inclus.", lien: "/backtest", action: "Tester une stratégie" },
];

export default function AnalysePage() {
  return <div className="analyse-hub">
    <div className="analyse-hub-entete"><div className="dashboard-surtitle">Outils de décision</div><h1>Analyser le marché</h1><p className="explication">Sélectionne, compare ou teste une méthode avant de constituer ton portefeuille fictif.</p></div>
    <div className="analyse-hub-grille">{OUTILS.map((outil) => <article className="analyse-hub-carte" key={outil.lien}>
      <span className="analyse-hub-icone">{outil.icone}</span><h2>{outil.titre}</h2><p>{outil.description}</p><Link className="btn lien-btn" to={outil.lien}>{outil.action} →</Link>
    </article>)}</div>
    <p className="note-fiscale"><strong>À retenir :</strong> ces outils servent à comprendre et à comparer des données passées. Ils ne prédisent pas les performances futures.</p>
  </div>;
}
