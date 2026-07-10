import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";
import { getAction, getActions, lancerBacktest, formatFCFA, formatEUR, enEuros } from "../api.js";

const COULEURS = { Rendement: "#f59e0b", Score: "#2563eb", Diversification: "#16a34a" };

export default function BacktestPage() {
  const [dateDepart, setDateDepart] = useState("");
  const [capital, setCapital] = useState(1000000);
  const [frais, setFrais] = useState(1);
  const [taille, setTaille] = useState(5);
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState("");
  const [chargement, setChargement] = useState(false);
  useEffect(() => { getActions().then((a) => a.length && getAction(a[0].symbole)).then((d) => { if (d?.historique?.length > 1) setDateDepart(d.historique[0].jour); }).catch(() => {}); }, []);

  async function lancer(e) {
    e.preventDefault(); setChargement(true); setErreur("");
    try { setResultat(await lancerBacktest({ date_depart: dateDepart, capital, frais_pct: frais, taille_panier: taille })); }
    catch (err) { setErreur(err.message); setResultat(null); }
    finally { setChargement(false); }
  }
  const graphique = resultat ? fusionner(resultat.strategies) : [];

  return <div className="backtest-page">
    <h1>Backtesting pédagogique</h1>
    <p className="explication">Observe ce qu’auraient donné plusieurs règles simples sur l’historique réellement collecté. Un résultat historique favorable n’est pas une prévision.</p>
    <form className="form-backtest" onSubmit={lancer}>
      <label>Date de l’investissement<input type="date" required value={dateDepart} onChange={(e) => setDateDepart(e.target.value)} /></label>
      <label>Capital initial (FCFA)<input type="number" min="10000" step="10000" value={capital} onChange={(e) => setCapital(Number(e.target.value))} /></label>
      <label>Frais par ordre (%)<input type="number" min="0" max="20" step="0.1" value={frais} onChange={(e) => setFrais(Number(e.target.value))} /></label>
      <label>Actions par stratégie<input type="number" min="2" max="10" value={taille} onChange={(e) => setTaille(Number(e.target.value))} /></label>
      <button className="btn" disabled={chargement || !dateDepart}>{chargement ? "Calcul…" : "Lancer le backtest"}</button>
    </form>
    {erreur && <p className="info erreur">{erreur}</p>}

    {resultat && <>
      <p className="info">Période réellement simulée : <strong>{resultat.date_depart_effective}</strong> → <strong>{resultat.date_fin}</strong>. Historique disponible depuis le {resultat.historique_disponible_depuis}.</p>
      <div className="cartes-backtest">{resultat.strategies.map((s) => <div className="strategie-carte" key={s.strategie} style={{ borderTopColor: COULEURS[s.strategie] }}><h2>{s.strategie}</h2><p>{s.description}</p><div className={`performance-strategie ${s.performance_pct > 0 ? "hausse" : s.performance_pct < 0 ? "baisse" : ""}`}>{s.performance_pct > 0 ? "+" : ""}{s.performance_pct.toFixed(2)} %</div><dl><dt>Valeur finale</dt><dd>{formatFCFA(s.valeur_finale)}</dd><dt>Dividendes inclus</dt><dd>{formatFCFA(s.dividendes)}</dd><dt>Frais achat + vente</dt><dd>{formatFCFA(s.frais)}</dd></dl><div className="symboles-backtest">{s.symboles.map((x) => <span key={x}>{x}</span>)}</div></div>)}</div>

      <h2>Comparaison des valeurs</h2>
      {graphique.length < 2 ? <p className="info">L’historique ne contient pas encore assez de séances pour tracer une évolution significative.</p> : <div className="graphique"><ResponsiveContainer width="100%" height={380}><LineChart data={graphique}><CartesianGrid strokeDasharray="3 3" stroke="#eee" /><XAxis dataKey="jour" /><YAxis width={90} domain={["auto", "auto"]} tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip formatter={(v) => [formatFCFA(v), `≈ ${formatEUR(enEuros(v))}`]} /><Legend /><ReferenceLine y={capital} stroke="#9ca3af" strokeDasharray="5 4" />{resultat.strategies.map((s) => <Line key={s.strategie} type="monotone" dataKey={s.strategie} stroke={COULEURS[s.strategie]} strokeWidth={3} dot={false} connectNulls />)}</LineChart></ResponsiveContainer></div>}

      <div className="limites-backtest"><h2>Limites à garder en tête</h2><ul>{resultat.limites.map((l, i) => <li key={i}>{l}</li>)}</ul></div>
    </>}
  </div>;
}

function fusionner(strategies) {
  const lignes = new Map();
  for (const strategie of strategies) for (const point of strategie.points) {
    if (!lignes.has(point.jour)) lignes.set(point.jour, { jour: point.jour });
    lignes.get(point.jour)[strategie.strategie] = point.valeur;
  }
  return [...lignes.values()].sort((a, b) => a.jour.localeCompare(b.jour));
}
