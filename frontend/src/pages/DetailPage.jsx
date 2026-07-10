import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { getAction, formatFCFA } from "../api.js";

export default function DetailPage() {
  const { symbole } = useParams();
  const [action, setAction] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    getAction(symbole).then(setAction).catch((e) => setErreur(e.message));
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

      <h2>Évolution du cours de clôture</h2>
      {action.historique.length < 2 ? (
        <p className="info">
          Un seul point pour l'instant. Le graphique se remplira au fil des jours,
          à chaque rafraîchissement des cours (un point par jour).
        </p>
      ) : (
        <div className="graphique">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={action.historique}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="jour" />
              <YAxis domain={["auto", "auto"]} width={80} />
              <Tooltip formatter={(v) => formatFCFA(v)} />
              <Line
                type="monotone"
                dataKey="cours_cloture"
                stroke="#2563eb"
                strokeWidth={2}
                dot={false}
                name="Clôture"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
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
