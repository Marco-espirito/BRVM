import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { getAction, getActions, formatFCFA } from "../api.js";
import AnalyseComparative from "../components/AnalyseComparative.jsx";

export default function DetailPage() {
  const { symbole } = useParams();
  const [action, setAction] = useState(null);
  const [marche, setMarche] = useState([]); // toutes les actions, pour comparer
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    getAction(symbole).then(setAction).catch((e) => setErreur(e.message));
    getActions().then(setMarche).catch(() => {}); // comparaison optionnelle
  }, [symbole]);

  if (erreur) return <p className="info erreur">Erreur : {erreur}</p>;
  if (!action) return <p className="info">Chargement…</p>;

  const dernier = action.historique[action.historique.length - 1];

  // Dernier dividende connu + rendement sur le cours actuel
  const dernierDiv = action.dividendes?.find((d) => d.montant != null);
  const rendementActuel =
    dernierDiv && dernier?.cours_cloture
      ? (dernierDiv.montant / dernier.cours_cloture) * 100
      : null;
  const p = action.performances ?? {};
  const performanceItems = [
    ["7 jours", p.variation_7j],
    ["30 jours", p.variation_30j],
    ["6 mois", p.variation_6m],
    ["1 an", p.variation_1a],
  ];
  const technique = action.indicateurs_techniques ?? {};

  return (
    <div className="detail">
      <Link to="/" className="retour">
        ← Retour à la liste
      </Link>

      <h1>
        {action.nom} <span className="symbole-detail">({action.symbole})</span>
      </h1>

      {dernier && (
        <div className="cartes">
          <Carte titre="Cours de clôture" valeur={formatFCFA(dernier.cours_cloture)} />
          <Carte
            titre="Variation"
            valeur={`${dernier.variation?.toFixed(2)}%`}
            classe={
              dernier.variation > 0
                ? "hausse"
                : dernier.variation < 0
                ? "baisse"
                : ""
            }
          />
          <Carte titre="Volume échangé" valeur={dernier.volume?.toLocaleString("fr-FR")} />
          {dernierDiv && (
            <Carte
              titre={`Dividende ${dernierDiv.annee}`}
              valeur={formatFCFA(dernierDiv.montant)}
            />
          )}
          {rendementActuel != null && (
            <Carte
              titre="Rendement (sur cours actuel)"
              valeur={`${rendementActuel.toFixed(2)}%`}
              classe={rendementActuel > 15 ? "" : "hausse"}
            />
          )}
        </div>
      )}

      {marche.length > 0 && (
        <AnalyseComparative action={action} marche={marche} />
      )}

      <section className="bloc-performances">
        <h2>Performances</h2>
        <div className="cartes cartes-performance">
          {performanceItems.map(([titre, valeur]) => (
            <Carte
              key={titre}
              titre={titre}
              valeur={valeur == null ? "Historique insuffisant" : `${valeur > 0 ? "+" : ""}${valeur.toFixed(2)}%`}
              classe={valeur > 0 ? "hausse" : valeur < 0 ? "baisse" : ""}
            />
          ))}
          <Carte titre="Plus haut 52 semaines" valeur={formatFCFA(p.plus_haut_52s)} />
          <Carte titre="Plus bas 52 semaines" valeur={formatFCFA(p.plus_bas_52s)} />
        </div>
        <p className="explication">
          Les variations utilisent la dernière séance disponible avant chaque échéance.
          Les extrêmes portent sur l’historique réellement collecté, jusqu’à 52 semaines.
        </p>
      </section>

      {action.prochain_detachement && (
        <div className="encart-detachement">
          📅 <strong>Prochain dividende annoncé :</strong>{" "}
          {formatFCFA(action.prochain_detachement.montant)} par action —
          détachement le{" "}
          <strong>{action.prochain_detachement.date_detachement}</strong>.
          <div className="explication">
            Pour toucher ce dividende, il faut détenir l'action <em>avant</em>{" "}
            cette date. Après le détachement, le cours baisse généralement du
            montant du dividende.
          </div>
        </div>
      )}

      {action.dividendes?.length > 0 && (
        <>
          <h2>Historique des dividendes</h2>
          <table className="tableau tableau-dividendes">
            <thead>
              <tr>
                <th>Année</th>
                <th className="num">Dividende / action</th>
                <th className="num">Rendement à l'époque</th>
              </tr>
            </thead>
            <tbody>
              {action.dividendes.map((d) => (
                <tr key={d.annee}>
                  <td>{d.annee}</td>
                  <td className="num">{formatFCFA(d.montant)}</td>
                  <td className="num">
                    {d.rendement != null ? `${d.rendement.toFixed(2)}%` : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="explication">
            💡 Un bon signe pour un investisseur long terme : un dividende{" "}
            <strong>stable ou en hausse</strong> d'année en année.
          </p>
        </>
      )}

      <section className="indicateurs-techniques">
        <h2>Indicateurs techniques simples</h2>
        <p className="explication">Ces mesures décrivent les cours passés. Elles ne constituent ni un signal d’achat, ni un signal de vente.</p>
        <div className="cartes cartes-performance">
          <Carte titre="Moyenne mobile 20" valeur={formatFCFA(technique.moyenne_mobile_20)} />
          <Carte titre="Moyenne mobile 50" valeur={formatFCFA(technique.moyenne_mobile_50)} />
          <Carte titre="RSI (14 séances)" valeur={technique.rsi_14 == null ? "Historique insuffisant" : technique.rsi_14.toFixed(2)} />
          <Carte titre="Volatilité annualisée (20)" valeur={technique.volatilite_20 == null ? "Historique insuffisant" : `${technique.volatilite_20.toFixed(2)}%`} />
          <Carte titre="Volume moyen (20)" valeur={technique.volume_moyen_20 == null ? "—" : Math.round(technique.volume_moyen_20).toLocaleString("fr-FR")} />
        </div>
        {technique.rsi_14 != null && <div className="rsi-jauge"><div className="rsi-zones"><span>0</span><span>30</span><span>Zone intermédiaire</span><span>70</span><span>100</span></div><div className="rsi-piste"><i style={{ left: `${technique.rsi_14}%` }} /></div></div>}
        <div className="explications-techniques">{technique.explications?.map((texte, i) => <p key={i}>💡 {texte}</p>)}</div>
      </section>

      <h2>Évolution du cours et moyennes mobiles</h2>
      {action.historique.length < 2 ? (
        <p className="info">
          Un seul point pour l'instant. Le graphique se remplira au fil des jours,
          à chaque rafraîchissement des cours (un point par jour).
        </p>
      ) : (
        <div className="graphique">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={technique.points ?? []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="jour" />
              <YAxis domain={["auto", "auto"]} width={80} />
              <Tooltip formatter={(v) => formatFCFA(v)} />
              <Legend />
              <Line
                type="monotone"
                dataKey="cours"
                stroke="#2563eb"
                strokeWidth={2}
                dot={false}
                name="Clôture"
              />
              <Line type="monotone" dataKey="moyenne_mobile_20" stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls name="Moyenne 20" />
              <Line type="monotone" dataKey="moyenne_mobile_50" stroke="#7c3aed" strokeWidth={2} dot={false} connectNulls name="Moyenne 50" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <h2>Comparaison avec le marché</h2>
      {action.comparaison_indices?.length < 2 ? (
        <p className="info">
          La comparaison apparaîtra après au moins deux séances communes enregistrées
          pour l’action, le BRVM Composite et le BRVM 30.
        </p>
      ) : (
        <>
          <p className="explication">
            Base 100 au premier jour commun : 105 correspond à une hausse de 5 %.
          </p>
          <div className="graphique">
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={action.comparaison_indices}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="jour" />
                <YAxis domain={["auto", "auto"]} width={55} />
                <Tooltip formatter={(v) => Number(v).toFixed(2)} />
                <Legend />
                <Line type="monotone" dataKey="action" stroke="#2563eb" strokeWidth={3} dot={false} name={action.symbole} />
                <Line type="monotone" dataKey="brvm_composite" stroke="#16a34a" strokeWidth={2} dot={false} name="BRVM Composite" />
                <Line type="monotone" dataKey="brvm_30" stroke="#f59e0b" strokeWidth={2} dot={false} name="BRVM 30" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

function Carte({ titre, valeur, classe = "" }) {
  return (
    <div className="carte">
      <div className="carte-titre">{titre}</div>
      <div className={"carte-valeur " + classe}>{valeur ?? "-"}</div>
    </div>
  );
}
