import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { formatFCFA, getAlertes, getCalendrierDividendes, getMesPortefeuilles, getPortefeuille } from "../api.js";

export default function TableauBordPage() {
  const [donnees, setDonnees] = useState(null);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    async function charger() {
      const portefeuilles = await getMesPortefeuilles();
      const memorise = Number(localStorage.getItem("portefeuille-actif"));
      const actif = portefeuilles.find((p) => p.id === memorise) ?? portefeuilles[0];
      if (!actif) throw new Error("Aucun portefeuille disponible.");
      const [portefeuille, calendrier, alertes] = await Promise.all([
        getPortefeuille(actif.id),
        getCalendrierDividendes(actif.id).catch(() => ({ evenements: [], prochaine_date: null, revenu_total_estime: 0 })),
        getAlertes().catch(() => []),
      ]);
      setDonnees({ actif, portefeuille, calendrier, alertes });
    }
    charger().catch((e) => setErreur(e.message));
  }, []);

  const prochainesEcheances = useMemo(() => donnees?.calendrier.evenements
    .filter((e) => e.date_detachement)
    .sort((a, b) => a.date_detachement.localeCompare(b.date_detachement))
    .slice(0, 3) ?? [], [donnees]);

  if (erreur) return <p className="info erreur">{erreur}</p>;
  if (!donnees) return <p className="info">Préparation du tableau de bord…</p>;
  const { actif, portefeuille, alertes } = donnees;
  const exposition = portefeuille.valeur_globale > 0 ? portefeuille.valeur_totale / portefeuille.valeur_globale * 100 : 0;
  const variation = portefeuille.performance_totale_pct ?? 0;

  return <div className="dashboard-page">
    <div className="dashboard-entete">
      <div><div className="dashboard-surtitle">Situation du portefeuille</div><h1>{actif.nom}</h1><p>Une lecture rapide de tes avoirs, revenus potentiels et points d’attention.</p></div>
      <Link className="btn lien-btn" to="/portefeuille">Gérer le portefeuille</Link>
    </div>

    <section className="dashboard-bilan">
      <div className="dashboard-valeur"><span>Valeur globale</span><strong>{formatFCFA(portefeuille.valeur_globale)}</strong><small>{portefeuille.positions.length} entreprise{portefeuille.positions.length > 1 ? "s" : ""} en portefeuille</small></div>
      <div className="dashboard-indicateurs">
        <Indicateur label="Actions" valeur={formatFCFA(portefeuille.valeur_totale)} detail={`${exposition.toFixed(1)} % du patrimoine`} />
        <Indicateur label="Liquidités" valeur={formatFCFA(portefeuille.solde_especes)} detail="disponibles pour investir" />
        <Indicateur label="Performance totale" valeur={`${variation >= 0 ? "+" : ""}${variation.toFixed(2)} %`} classe={variation >= 0 ? "hausse" : "baisse"} detail="dividendes connus inclus" />
        <Indicateur label="Dividendes annuels estimés" valeur={formatFCFA(portefeuille.dividendes_annuels)} classe="hausse" detail="estimation brute" />
      </div>
    </section>

    <div className="dashboard-grille">
      <section className="dashboard-panneau">
        <div className="dashboard-panneau-titre"><div><span>À venir</span><h2>Dividendes annoncés</h2></div><Link to="/calendrier">Voir le calendrier →</Link></div>
        {prochainesEcheances.length ? <div className="dashboard-liste">{prochainesEcheances.map((e) => <div key={e.symbole} className="dashboard-ligne"><div><strong>{e.symbole}</strong><span>{e.nom}</span></div><div><strong>{e.date_detachement}</strong><span>{formatFCFA(e.revenu_estime)} estimés</span></div></div>)}</div> : <p className="dashboard-vide">Aucun détachement daté n’est actuellement annoncé.</p>}
      </section>

      <section className="dashboard-panneau">
        <div className="dashboard-panneau-titre"><div><span>Risque</span><h2>Diversification</h2></div><Link to="/portefeuille">Voir l’analyse →</Link></div>
        <div className="concentration-jauge"><div style={{ width: `${Math.min(portefeuille.concentration_max_pct ?? 0, 100)}%` }} /></div>
        <strong className="concentration-valeur">{portefeuille.concentration_max_pct?.toFixed(1) ?? "0.0"} %</strong>
        <p>Poids de la plus grande position. {portefeuille.concentration_max_pct > 40 ? "Cette concentration mérite une attention particulière." : "La concentration maximale reste sous le seuil d’alerte de 40 %."}</p>
        <div className="dashboard-secteurs">{portefeuille.repartition_secteurs.slice(0, 4).map((s) => <span key={s.libelle}>{s.libelle} <strong>{s.pourcentage.toFixed(0)} %</strong></span>)}</div>
      </section>

      <section className="dashboard-panneau dashboard-alertes">
        <div className="dashboard-panneau-titre"><div><span>Surveillance</span><h2>Alertes actives</h2></div><Link to="/alertes">Gérer les alertes →</Link></div>
        <strong className="dashboard-compte-alertes">{alertes.filter((a) => a.active).length}</strong>
        <p>règle{alertes.filter((a) => a.active).length > 1 ? "s" : ""} surveillée{alertes.filter((a) => a.active).length > 1 ? "s" : ""} automatiquement.</p>
        {alertes.length === 0 && <Link className="btn-mini-acheter" to="/alertes">Créer une première alerte</Link>}
      </section>
    </div>
  </div>;
}

function Indicateur({ label, valeur, detail, classe = "" }) {
  return <div className="dashboard-indicateur"><span>{label}</span><strong className={classe}>{valeur}</strong><small>{detail}</small></div>;
}
