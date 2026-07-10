import { useEffect, useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";
import { getAction, getActions, formatFCFA } from "../api.js";

const COULEURS = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626"];
const PERIODES = [
  ["7 jours", "variation_7j"], ["30 jours", "variation_30j"],
  ["6 mois", "variation_6m"], ["1 an", "variation_1a"],
];

export default function ComparateurPage() {
  const [actions, setActions] = useState([]);
  const [selection, setSelection] = useState([]);
  const [details, setDetails] = useState([]);
  const [erreur, setErreur] = useState("");

  useEffect(() => {
    getActions().then((liste) => {
      setActions(liste);
      setSelection(liste.slice(0, 2).map((a) => a.symbole));
    }).catch((e) => setErreur(e.message));
  }, []);

  useEffect(() => {
    if (selection.length < 2) return setDetails([]);
    Promise.all(selection.map(getAction)).then(setDetails).catch((e) => setErreur(e.message));
  }, [selection]);

  function modifier(index, symbole) {
    setSelection((courante) => courante.map((s, i) => i === index ? symbole : s));
  }
  function ajouter() {
    const libre = actions.find((a) => !selection.includes(a.symbole));
    if (libre && selection.length < 5) setSelection([...selection, libre.symbole]);
  }

  const fiches = useMemo(() => details.map((d) => ({
    ...d,
    resume: actions.find((a) => a.symbole === d.symbole),
    dernierDiv: d.dividendes?.find((x) => x.montant != null),
  })), [details, actions]);

  const graphique = useMemo(() => construireBase100(details), [details]);

  return <div className="comparateur-page">
    <h1>Comparateur d’actions</h1>
    <p className="explication">Compare de 2 à 5 sociétés sur une même échelle. Une valeur de 110 signifie une progression de 10 % depuis le premier jour commun.</p>
    {erreur && <p className="info erreur">{erreur}</p>}

    <div className="selecteurs-comparateur">
      {selection.map((symbole, index) => <div className="selecteur-action" key={index} style={{ borderColor: COULEURS[index] }}>
        <select value={symbole} onChange={(e) => modifier(index, e.target.value)}>
          {actions.map((a) => <option key={a.symbole} value={a.symbole} disabled={selection.includes(a.symbole) && a.symbole !== symbole}>{a.symbole} — {a.nom}</option>)}
        </select>
        {selection.length > 2 && <button title="Retirer" onClick={() => setSelection(selection.filter((_, i) => i !== index))}>×</button>}
      </div>)}
      {selection.length < 5 && <button className="btn" onClick={ajouter}>+ Ajouter une société</button>}
    </div>

    {fiches.length === selection.length && <>
      <h2>Vue d’ensemble</h2>
      <div className="table-scroll"><table className="tableau comparaison-table">
        <thead><tr><th>Indicateur</th>{fiches.map((f, i) => <th key={f.symbole} style={{ color: COULEURS[i] }}>{f.symbole}</th>)}</tr></thead>
        <tbody>
          <Ligne titre="Cours actuel" fiches={fiches} valeur={(f) => formatFCFA(f.resume?.cours_cloture)} />
          <Ligne titre="Rendement du dividende" fiches={fiches} valeur={(f) => pct(f.resume?.rendement)} meilleur={(f) => f.resume?.rendement} />
          <Ligne titre="Liquidité" fiches={fiches} valeur={(f) => `${iconeLiquidite(f.resume?.liquidite)} ${f.resume?.liquidite ?? "inconnue"}`} />
          <Ligne titre="Volume moyen" fiches={fiches} valeur={(f) => f.resume?.volume_moyen?.toLocaleString("fr-FR") ?? "—"} meilleur={(f) => f.resume?.volume_moyen} />
          <Ligne titre="Dernier dividende" fiches={fiches} valeur={(f) => f.dernierDiv ? `${formatFCFA(f.dernierDiv.montant)} (${f.dernierDiv.annee})` : "—"} />
          <Ligne titre="Plus haut 52 semaines" fiches={fiches} valeur={(f) => formatFCFA(f.performances?.plus_haut_52s)} />
          <Ligne titre="Plus bas 52 semaines" fiches={fiches} valeur={(f) => formatFCFA(f.performances?.plus_bas_52s)} />
        </tbody>
      </table></div>

      <h2>Performances</h2>
      <div className="cartes-periodes">{PERIODES.map(([titre, cle]) => <div className="periode-comparaison" key={cle}><h3>{titre}</h3>{fiches.map((f, i) => <div key={f.symbole}><span style={{ background: COULEURS[i] }} />{f.symbole}<strong className={classe(f.performances?.[cle])}>{pct(f.performances?.[cle], true)}</strong></div>)}</div>)}</div>

      <h2>Évolution comparée en base 100</h2>
      {graphique.length < 2 ? <p className="info">Il faut au moins deux séances communes pour afficher le graphique comparatif.</p> : <div className="graphique"><ResponsiveContainer width="100%" height={380}><LineChart data={graphique}><CartesianGrid strokeDasharray="3 3" stroke="#eee" /><XAxis dataKey="jour" /><YAxis domain={["auto", "auto"]} width={55} /><Tooltip formatter={(v) => Number(v).toFixed(2)} /><Legend /><ReferenceLine y={100} stroke="#9ca3af" strokeDasharray="4 4" />{fiches.map((f, i) => <Line key={f.symbole} type="monotone" dataKey={f.symbole} stroke={COULEURS[i]} strokeWidth={i === 0 ? 3 : 2} dot={false} connectNulls />)}</LineChart></ResponsiveContainer></div>}

      <h2>Historique des dividendes</h2>
      <div className="grille-dividendes-comparateur">{fiches.map((f, i) => <div className="repartition-carte" key={f.symbole}><h3 style={{ color: COULEURS[i] }}>{f.symbole}</h3>{f.dividendes?.length ? <table className="mini-table"><tbody>{f.dividendes.map((d) => <tr key={d.annee}><td>{d.annee}</td><td>{formatFCFA(d.montant)}</td><td>{pct(d.rendement)}</td></tr>)}</tbody></table> : <p className="explication">Aucun dividende connu.</p>}</div>)}</div>
    </>}
  </div>;
}

function construireBase100(details) {
  if (details.length < 2) return [];
  const series = details.map((d) => new Map(d.historique.filter((p) => p.cours_cloture != null).map((p) => [p.jour, p.cours_cloture])));
  const joursCommuns = [...series[0].keys()].filter((jour) => series.every((s) => s.has(jour))).sort();
  if (!joursCommuns.length) return [];
  const bases = series.map((s) => s.get(joursCommuns[0]));
  return joursCommuns.map((jour) => Object.fromEntries([["jour", jour], ...details.map((d, i) => [d.symbole, Number((series[i].get(jour) / bases[i] * 100).toFixed(2))]) ]));
}
function Ligne({ titre, fiches, valeur, meilleur }) {
  const valeurs = meilleur ? fiches.map(meilleur) : [];
  const max = meilleur ? Math.max(...valeurs.filter((v) => v != null)) : null;
  return <tr><td><strong>{titre}</strong></td>{fiches.map((f, i) => <td key={f.symbole} className={meilleur && valeurs[i] === max ? "comparaison-meilleur" : ""}>{valeur(f)}</td>)}</tr>;
}
const pct = (v, signe = false) => v == null ? "—" : `${signe && v > 0 ? "+" : ""}${Number(v).toFixed(2)} %`;
const classe = (v) => v > 0 ? "hausse" : v < 0 ? "baisse" : "";
const iconeLiquidite = (v) => ({ haute: "🟢", moyenne: "🟡", faible: "🔴" }[v] ?? "⚪");
