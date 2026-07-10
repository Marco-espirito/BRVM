import { useEffect, useMemo, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, ReferenceLine,
} from "recharts";
import { getActions, formatFCFA, formatEUR, enEuros } from "../api.js";

export default function ObjectifPage() {
  const [actions, setActions] = useState([]);
  const [selection, setSelection] = useState([]);
  const [objectif, setObjectif] = useState(50000);
  const [capitalInitial, setCapitalInitial] = useState(0);
  const [mensuel, setMensuel] = useState(50000);
  const [annees, setAnnees] = useState(10);
  const [reinvestir, setReinvestir] = useState(true);
  useEffect(() => { getActions().then((liste) => {
    setActions(liste);
    setSelection(liste.filter((a) => a.rendement > 0 && a.rendement <= 15).sort((a, b) => (b.rendement ?? 0) - (a.rendement ?? 0)).slice(0, 3).map((a) => a.symbole));
  }); }, []);

  const choisies = useMemo(() => actions.filter((a) => selection.includes(a.symbole)), [actions, selection]);
  const rendementMoyen = choisies.length ? choisies.reduce((s, a) => s + (a.rendement ?? 0), 0) / choisies.length : 0;
  const capitalNecessaire = rendementMoyen > 0 ? objectif / (rendementMoyen / 100) : 0;
  const simulation = useMemo(() => simuler({ capitalInitial, mensuel, annees, rendement: rendementMoyen, reinvestir, objectif }), [capitalInitial, mensuel, annees, rendementMoyen, reinvestir, objectif]);
  const final = simulation.points.at(-1) ?? { capital: 0, dividendes: 0, versements: 0 };

  function toggle(symbole) {
    setSelection((s) => s.includes(symbole) ? (s.length > 1 ? s.filter((x) => x !== symbole) : s) : [...s, symbole]);
  }

  return <div className="objectif-page">
    <h1>Objectif d’investissement</h1>
    <p className="explication">Définis le revenu annuel recherché, construis un panier et simule l’effet des versements réguliers et du réinvestissement.</p>
    <div className="objectif-layout">
      <div className="objectif-form">
        <label>Dividendes annuels visés (FCFA)<input type="number" min="1000" step="1000" value={objectif} onChange={(e) => setObjectif(Number(e.target.value))} /></label>
        <label>Capital de départ (FCFA)<input type="number" min="0" step="10000" value={capitalInitial} onChange={(e) => setCapitalInitial(Number(e.target.value))} /></label>
        <label>Investissement mensuel (FCFA)<input type="number" min="0" step="5000" value={mensuel} onChange={(e) => setMensuel(Number(e.target.value))} /></label>
        <label>Horizon : <strong>{annees} ans</strong><input type="range" min="1" max="30" value={annees} onChange={(e) => setAnnees(Number(e.target.value))} /></label>
        <label className="case-reinvestir"><input type="checkbox" checked={reinvestir} onChange={(e) => setReinvestir(e.target.checked)} /> Réinvestir automatiquement les dividendes</label>
      </div>
      <div className="objectif-resultat">
        <span>Capital estimé nécessaire aujourd’hui</span>
        <strong>{rendementMoyen ? formatFCFA(capitalNecessaire) : "Sélectionne un panier"}</strong>
        <small>≈ {formatEUR(enEuros(capitalNecessaire))} avec un rendement moyen de {rendementMoyen.toFixed(2)} %</small>
      </div>
    </div>

    <h2>Panier équipondéré</h2>
    <p className="explication">Chaque société reçoit la même part du capital. Les rendements supérieurs à 15 % sont signalés comme potentiellement exceptionnels.</p>
    <div className="panier-actions">{actions.filter((a) => a.rendement != null).map((a) => <button key={a.symbole} className={selection.includes(a.symbole) ? "actif" : ""} onClick={() => toggle(a.symbole)}><strong>{a.symbole}</strong><span>{a.rendement.toFixed(2)} %</span>{a.rendement > 15 && <small>⚠ exceptionnel ?</small>}</button>)}</div>

    <div className="cartes">
      <Carte titre={`Capital après ${annees} ans`} valeur={formatFCFA(final.capital)} sous={`Versements : ${formatFCFA(final.versements)}`} />
      <Carte titre="Dividendes annuels estimés" valeur={formatFCFA(final.dividendes)} classe="hausse" sous={`Objectif : ${formatFCFA(objectif)}`} />
      <Carte titre="Date estimée de l’objectif" valeur={simulation.moisAtteinte == null ? `Au-delà de ${annees} ans` : simulation.moisAtteinte === 0 ? "Déjà atteint" : `${Math.ceil(simulation.moisAtteinte / 12)} an(s)`} />
      <Carte titre="Dividendes cumulés" valeur={formatFCFA(simulation.dividendesCumules)} sous={reinvestir ? "réinjectés dans le capital" : "conservés en revenus"} />
    </div>

    <h2>Projection</h2>
    <div className="graphique"><ResponsiveContainer width="100%" height={350}><AreaChart data={simulation.points}><defs><linearGradient id="objectifCapital" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#2563eb" stopOpacity={0.35}/><stop offset="95%" stopColor="#2563eb" stopOpacity={0.03}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#eee" /><XAxis dataKey="libelle" /><YAxis width={90} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip formatter={(v) => formatFCFA(v)} /><ReferenceLine y={capitalNecessaire} stroke="#16a34a" strokeDasharray="5 4" label={{ value: "capital cible", fill: "#166534", fontSize: 11 }} /><Area type="monotone" dataKey="capital" stroke="#2563eb" strokeWidth={3} fill="url(#objectifCapital)" name="Capital" /></AreaChart></ResponsiveContainer></div>

    <div className="note-fiscale"><strong>Hypothèses :</strong> rendement constant basé sur les derniers dividendes connus, panier rééquilibré à parts égales, versements sans variation de cours ni frais. Le réinvestissement est appliqué une fois par an. Il s’agit d’une projection pédagogique, pas d’une promesse de revenu.</div>
  </div>;
}

function simuler({ capitalInitial, mensuel, annees, rendement, reinvestir, objectif }) {
  let capital = capitalInitial, versements = capitalInitial, dividendesCumules = 0, moisAtteinte = capital * rendement / 100 >= objectif ? 0 : null;
  const points = [{ libelle: "Départ", capital, dividendes: capital * rendement / 100, versements }];
  for (let mois = 1; mois <= annees * 12; mois++) {
    capital += mensuel; versements += mensuel;
    if (mois % 12 === 0) {
      const dividendes = capital * rendement / 100;
      dividendesCumules += dividendes;
      if (reinvestir) capital += dividendes;
      points.push({ libelle: `An ${mois / 12}`, capital: Math.round(capital), dividendes: Math.round(capital * rendement / 100), versements });
    }
    if (moisAtteinte == null && capital * rendement / 100 >= objectif) moisAtteinte = mois;
  }
  return { points, moisAtteinte, dividendesCumules };
}
function Carte({ titre, valeur, sous, classe = "" }) { return <div className="carte"><div className="carte-titre">{titre}</div><div className={`carte-valeur ${classe}`}>{valeur}</div>{sous && <div className="carte-detail">{sous}</div>}</div>; }
