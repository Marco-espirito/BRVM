import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getActions, formatFCFA } from "../api.js";

const DEFAUT = { rendement: "", liquidite: "toutes", regularite: "toutes", secteur: "tous", pays: "tous", prixMin: "", prixMax: "", variation30: "" };
const RANG_LIQUIDITE = { faible: 1, moyenne: 2, haute: 3 };
const RANG_REGULARITE = { faible: 1, moyenne: 2, forte: 3 };

function lireFiltres() {
  try { return JSON.parse(localStorage.getItem("screener-filtres-sauvegardes")) ?? []; }
  catch { return []; }
}

export default function ScreenerPage() {
  const [actions, setActions] = useState([]);
  const [filtres, setFiltres] = useState(DEFAUT);
  const [sauvegardes, setSauvegardes] = useState(lireFiltres);
  const [erreur, setErreur] = useState("");
  useEffect(() => { getActions().then(setActions).catch((e) => setErreur(e.message)); }, []);

  const secteurs = useMemo(() => [...new Set(actions.map((a) => a.secteur).filter(Boolean))].sort(), [actions]);
  const pays = useMemo(() => [...new Set(actions.map((a) => a.pays).filter(Boolean))].sort(), [actions]);
  const resultats = useMemo(() => actions.filter((a) => {
    if (filtres.rendement !== "" && (a.rendement == null || a.rendement < Number(filtres.rendement))) return false;
    if (filtres.liquidite !== "toutes" && (RANG_LIQUIDITE[a.liquidite] ?? 0) < RANG_LIQUIDITE[filtres.liquidite]) return false;
    if (filtres.regularite !== "toutes" && (RANG_REGULARITE[a.regularite_dividende] ?? 0) < RANG_REGULARITE[filtres.regularite]) return false;
    if (filtres.secteur !== "tous" && a.secteur !== filtres.secteur) return false;
    if (filtres.pays !== "tous" && a.pays !== filtres.pays) return false;
    if (filtres.prixMin !== "" && a.cours_cloture < Number(filtres.prixMin)) return false;
    if (filtres.prixMax !== "" && a.cours_cloture > Number(filtres.prixMax)) return false;
    if (filtres.variation30 !== "" && (a.variation_30j == null || a.variation_30j < Number(filtres.variation30))) return false;
    return true;
  }).sort((a, b) => (b.rendement ?? -Infinity) - (a.rendement ?? -Infinity)), [actions, filtres]);

  function changer(cle, valeur) { setFiltres({ ...filtres, [cle]: valeur }); }
  function sauvegarder() {
    const nom = window.prompt("Nom de cette configuration");
    if (!nom?.trim()) return;
    const nouvelle = [...sauvegardes.filter((s) => s.nom !== nom.trim()), { nom: nom.trim(), filtres }];
    setSauvegardes(nouvelle);
    localStorage.setItem("screener-filtres-sauvegardes", JSON.stringify(nouvelle));
  }
  function supprimer(nom) {
    const nouvelle = sauvegardes.filter((s) => s.nom !== nom);
    setSauvegardes(nouvelle);
    localStorage.setItem("screener-filtres-sauvegardes", JSON.stringify(nouvelle));
  }

  return <div className="screener-page">
    <div className="titre-actions"><div><h1>Screener avancé</h1><p className="explication">Combine les critères pour réduire les 47 actions à une sélection adaptée à ta stratégie.</p></div><button className="btn" onClick={sauvegarder}>💾 Sauvegarder les filtres</button></div>
    {erreur && <p className="info erreur">{erreur}</p>}
    {sauvegardes.length > 0 && <div className="filtres-sauvegardes"><strong>Configurations :</strong>{sauvegardes.map((s) => <span key={s.nom}><button onClick={() => setFiltres(s.filtres)}>{s.nom}</button><button title="Supprimer" onClick={() => supprimer(s.nom)}>×</button></span>)}</div>}

    <div className="panneau-screener">
      <Champ titre="Rendement minimal (%)"><input type="number" step="0.1" min="0" value={filtres.rendement} onChange={(e) => changer("rendement", e.target.value)} placeholder="Ex. 5" /></Champ>
      <Champ titre="Liquidité minimale"><select value={filtres.liquidite} onChange={(e) => changer("liquidite", e.target.value)}><option value="toutes">Toutes</option><option value="faible">Faible ou mieux</option><option value="moyenne">Moyenne ou haute</option><option value="haute">Haute uniquement</option></select></Champ>
      <Champ titre="Régularité minimale"><select value={filtres.regularite} onChange={(e) => changer("regularite", e.target.value)}><option value="toutes">Toutes</option><option value="faible">Faible ou mieux</option><option value="moyenne">2 ans ou plus</option><option value="forte">4 ans ou plus</option></select></Champ>
      <Champ titre="Secteur"><select value={filtres.secteur} onChange={(e) => changer("secteur", e.target.value)}><option value="tous">Tous les secteurs</option>{secteurs.map((s) => <option key={s}>{s}</option>)}</select></Champ>
      <Champ titre="Pays"><select value={filtres.pays} onChange={(e) => changer("pays", e.target.value)}><option value="tous">Tous les pays</option>{pays.map((p) => <option key={p}>{p}</option>)}</select></Champ>
      <Champ titre="Prix minimum (FCFA)"><input type="number" min="0" value={filtres.prixMin} onChange={(e) => changer("prixMin", e.target.value)} /></Champ>
      <Champ titre="Prix maximum (FCFA)"><input type="number" min="0" value={filtres.prixMax} onChange={(e) => changer("prixMax", e.target.value)} /></Champ>
      <Champ titre="Variation 30 j minimale (%)"><input type="number" step="0.1" value={filtres.variation30} onChange={(e) => changer("variation30", e.target.value)} placeholder="Ex. -5" /></Champ>
      <button className="filtre-reset" onClick={() => setFiltres(DEFAUT)}>Réinitialiser</button>
    </div>

    <div className="resultats-screener"><strong>{resultats.length}</strong> action{resultats.length > 1 ? "s" : ""} trouvée{resultats.length > 1 ? "s" : ""}</div>
    <div className="table-scroll"><table className="tableau"><thead><tr><th>Action</th><th>Société</th><th>Pays</th><th>Secteur</th><th className="num">Cours</th><th className="num">Rendement</th><th>Liquidité</th><th>Régularité</th><th className="num">Variation 30 j</th></tr></thead><tbody>{resultats.map((a) => <tr key={a.symbole}><td><Link className="symbole" to={`/action/${a.symbole}`}>{a.symbole}</Link></td><td>{a.nom}</td><td>{a.pays}</td><td><span className="chip-secteur">{a.secteur ?? "—"}</span></td><td className="num">{formatFCFA(a.cours_cloture)}</td><td className="num rendement">{a.rendement == null ? "—" : `${a.rendement.toFixed(2)} %`}</td><td>{iconeLiquidite(a.liquidite)} {a.liquidite ?? "—"}</td><td><span className={`regularite-badge ${a.regularite_dividende}`}>{a.regularite_dividende} · {a.annees_dividende_consecutives} an{a.annees_dividende_consecutives > 1 ? "s" : ""}</span></td><td className={`num ${a.variation_30j > 0 ? "hausse" : a.variation_30j < 0 ? "baisse" : ""}`}>{a.variation_30j == null ? "—" : `${a.variation_30j > 0 ? "+" : ""}${a.variation_30j.toFixed(2)} %`}</td></tr>)}</tbody></table></div>
    {filtres.variation30 !== "" && actions.some((a) => a.variation_30j == null) && <p className="explication">Les actions sans 30 jours d’historique sont exclues lorsque ce filtre est actif.</p>}
  </div>;
}
function Champ({ titre, children }) { return <label className="champ-screener"><span>{titre}</span>{children}</label>; }
const iconeLiquidite = (v) => ({ haute: "🟢", moyenne: "🟡", faible: "🔴" }[v] ?? "⚪");
