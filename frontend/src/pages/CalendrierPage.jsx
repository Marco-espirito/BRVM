import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { creerAlerte, getAction, getCalendrierDividendes, formatFCFA, formatEUR, enEuros } from "../api.js";

const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];

export default function CalendrierPage() {
  const [calendrier, setCalendrier] = useState(null);
  const [courant, setCourant] = useState(() => new Date());
  const [symbole, setSymbole] = useState("");
  const [detail, setDetail] = useState(null);
  const [message, setMessage] = useState("");
  useEffect(() => { getCalendrierDividendes(Number(localStorage.getItem("portefeuille-actif")) || null).then((c) => {
    setCalendrier(c);
    if (c.prochaine_date) { const d = dateLocale(c.prochaine_date); setCourant(new Date(d.getFullYear(), d.getMonth(), 1)); }
    if (c.evenements.length) setSymbole(c.evenements[0].symbole);
  }).catch((e) => setMessage(e.message)); }, []);
  useEffect(() => { if (symbole) getAction(symbole).then(setDetail).catch(() => setDetail(null)); }, [symbole]);

  const evenementsMois = useMemo(() => calendrier?.evenements.filter((e) => {
    if (!e.date_detachement) return false;
    const d = dateLocale(e.date_detachement);
    return d.getFullYear() === courant.getFullYear() && d.getMonth() === courant.getMonth();
  }) ?? [], [calendrier, courant]);

  if (!calendrier) return <p className="info">Chargement du calendrier…</p>;
  async function rappeler(e) {
    const jours = Number(window.prompt(`Combien de jours avant le détachement de ${e.symbole} ?`, "7"));
    if (!jours) return;
    try { await creerAlerte({ symbole: e.symbole, type: "rappel_detachement", seuil: jours, email: null }); setMessage(`Rappel créé pour ${e.symbole}, ${jours} jour(s) avant.`); }
    catch (err) { setMessage(err.message); }
  }
  function changerMois(delta) { setCourant(new Date(courant.getFullYear(), courant.getMonth() + delta, 1)); }

  return <div className="calendrier-page">
    <h1>Calendrier des dividendes</h1>
    <p className="explication">Les dates proviennent des annonces collectées. La date de paiement reste « non communiquée » lorsqu’elle n’est pas publiée par la source.</p>
    {message && <p className="info">{message}</p>}
    <div className="cartes">
      <div className="carte"><div className="carte-titre">Revenus futurs estimés</div><div className="carte-valeur hausse">{formatFCFA(calendrier.revenu_total_estime)}</div><div className="carte-sous">≈ {formatEUR(enEuros(calendrier.revenu_total_estime))}</div></div>
      <div className="carte"><div className="carte-titre">Prochain détachement</div><div className="carte-valeur">{calendrier.prochaine_date ? formatDate(calendrier.prochaine_date) : "Aucun annoncé"}</div></div>
      <div className="carte"><div className="carte-titre">Annonces suivies</div><div className="carte-valeur">{calendrier.evenements.length}</div></div>
    </div>

    <div className="calendrier-entete"><button onClick={() => changerMois(-1)}>←</button><h2>{MOIS[courant.getMonth()]} {courant.getFullYear()}</h2><button onClick={() => changerMois(1)}>→</button></div>
    <GrilleMois date={courant} evenements={evenementsMois} onRappel={rappeler} />

    <h2>Détachements annoncés et revenus du portefeuille</h2>
    <div className="table-scroll"><table className="tableau"><thead><tr><th>Action</th><th>Détachement</th><th>Paiement</th><th className="num">Montant/action</th><th className="num">Quantité détenue</th><th className="num">Revenu estimé</th><th></th></tr></thead><tbody>{calendrier.evenements.map((e) => <tr key={e.symbole}><td><Link className="symbole" to={`/action/${e.symbole}`}>{e.symbole}</Link> · {e.nom}</td><td>{e.date_detachement ? formatDate(e.date_detachement) : e.date_detachement_source}</td><td>{e.date_paiement ? formatDate(e.date_paiement) : "Non communiquée"}</td><td className="num">{formatFCFA(e.montant)}</td><td className="num">{e.quantite_portefeuille}</td><td className="num hausse">{formatFCFA(e.revenu_estime)}</td><td><button className="btn" onClick={() => rappeler(e)}>🔔 Rappel</button></td></tr>)}</tbody></table></div>

    <h2>Historique par entreprise</h2>
    <select className="select-historique" value={symbole} onChange={(e) => setSymbole(e.target.value)}>{calendrier.evenements.map((e) => <option key={e.symbole} value={e.symbole}>{e.symbole} — {e.nom}</option>)}</select>
    {detail?.dividendes?.length ? <table className="tableau tableau-dividendes"><thead><tr><th>Année</th><th className="num">Dividende/action</th><th className="num">Rendement</th></tr></thead><tbody>{detail.dividendes.map((d) => <tr key={d.annee}><td>{d.annee}</td><td className="num">{formatFCFA(d.montant)}</td><td className="num">{d.rendement == null ? "—" : `${d.rendement.toFixed(2)} %`}</td></tr>)}</tbody></table> : <p className="info">Aucun historique disponible pour cette entreprise.</p>}
  </div>;
}

function GrilleMois({ date, evenements, onRappel }) {
  const debut = new Date(date.getFullYear(), date.getMonth(), 1);
  const nbJours = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  const decalage = (debut.getDay() + 6) % 7;
  return <div className="grille-calendrier">{["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"].map((j) => <div className="jour-semaine" key={j}>{j}</div>)}{Array.from({ length: decalage }, (_, i) => <div className="case-jour vide" key={`v${i}`} />)}{Array.from({ length: nbJours }, (_, i) => i + 1).map((jour) => { const es = evenements.filter((e) => dateLocale(e.date_detachement).getDate() === jour); return <div className="case-jour" key={jour}><span>{jour}</span>{es.map((e) => <button key={e.symbole} onClick={() => onRappel(e)} title={`${e.nom} — ${formatFCFA(e.montant)}`}>{e.symbole}<small>{formatFCFA(e.montant)}</small></button>)}</div>; })}</div>;
}
function dateLocale(iso) { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); }
function formatDate(iso) { return dateLocale(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" }); }
