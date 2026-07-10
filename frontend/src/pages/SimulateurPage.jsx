import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getActions,
  formatFCFA,
  formatEUR,
  enEuros,
  FCFA_PAR_EURO,
} from "../api.js";

// Retenue a la source indicative sur les dividendes dans l'UEMOA (IRVM).
// Le taux exact varie selon le pays (~7 a 15 %) : on prend 10 % pour donner
// un ordre de grandeur realiste.
const TAUX_IRVM = 0.10;

const LIQUIDITE_ICONE = { haute: "🟢", moyenne: "🟡", faible: "🔴" };

export default function SimulateurPage() {
  const [actions, setActions] = useState([]);
  const [erreur, setErreur] = useState(null);
  const [symbole, setSymbole] = useState("");
  const [nbActions, setNbActions] = useState(100);

  useEffect(() => {
    getActions()
      .then((data) => {
        setActions(data);
        // Preselectionne la 1re action qui a un dividende connu
        const premiere = data.find((a) => a.dividende != null);
        if (premiere) setSymbole(premiere.symbole);
      })
      .catch((e) => setErreur(e.message));
  }, []);

  const action = useMemo(
    () => actions.find((a) => a.symbole === symbole),
    [actions, symbole]
  );

  // Tous les calculs de la simulation
  const calcul = useMemo(() => {
    if (!action || !action.cours_cloture || nbActions <= 0) return null;
    const cout = nbActions * action.cours_cloture;
    const divBrut =
      action.dividende != null ? nbActions * action.dividende : null;
    const divNet = divBrut != null ? divBrut * (1 - TAUX_IRVM) : null;
    return {
      cout,
      divBrut,
      divNet,
      rendementBrut:
        divBrut != null ? (divBrut / cout) * 100 : null,
      // Nb de jours de volume moyen necessaires pour acheter la position :
      // au-dela de ~1 jour, l'ordre risque de trainer sur ce marche.
      joursPourAcheter:
        action.volume_moyen > 0 ? nbActions / action.volume_moyen : null,
    };
  }, [action, nbActions]);

  if (erreur)
    return (
      <div className="info erreur">
        <p>Erreur : {erreur}</p>
        <p>Le backend est-il démarré sur http://localhost:8000 ?</p>
      </div>
    );
  if (!actions.length) return <p className="info">Chargement…</p>;

  const budgetEnEuros = calcul ? enEuros(calcul.cout) : null;

  return (
    <>
      <h1>🧮 Simulateur de dividendes</h1>
      <p className="explication" style={{ marginBottom: 20 }}>
        Choisis une action et un nombre de titres : le simulateur estime ton
        investissement et ce qu'il te rapporterait en dividendes chaque année,
        en FCFA et en euros (parité fixe : 1 € = {FCFA_PAR_EURO} FCFA).
      </p>

      <div className="simulateur-form">
        <label className="champ">
          <span>Action</span>
          <select value={symbole} onChange={(e) => setSymbole(e.target.value)}>
            {actions.map((a) => (
              <option key={a.symbole} value={a.symbole}>
                {a.symbole} — {a.nom}
                {a.dividende == null ? " (dividende inconnu)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="champ champ-nombre">
          <span>Nombre d'actions</span>
          <input
            type="number"
            min="1"
            value={nbActions}
            onChange={(e) => setNbActions(Number(e.target.value))}
          />
        </label>
      </div>

      {action && calcul && (
        <>
          <div className="cartes">
            <Carte
              titre="💸 Coût d'achat estimé"
              valeur={formatFCFA(calcul.cout)}
              sous={`≈ ${formatEUR(budgetEnEuros)}`}
              detail={`${nbActions} × ${formatFCFA(action.cours_cloture)} (cours actuel)`}
            />
            {calcul.divBrut != null ? (
              <>
                <Carte
                  titre={`💰 Dividendes annuels bruts (base ${action.annee_dividende})`}
                  valeur={formatFCFA(calcul.divBrut)}
                  sous={`≈ ${formatEUR(enEuros(calcul.divBrut))}`}
                  detail={`${nbActions} × ${formatFCFA(action.dividende)} par action`}
                />
                <Carte
                  titre="✂️ Après retenue à la source (~10 %)"
                  valeur={formatFCFA(calcul.divNet)}
                  sous={`≈ ${formatEUR(enEuros(calcul.divNet))} / an`}
                  detail="Impôt IRVM prélevé directement dans le pays d'origine (7 à 15 % selon le pays)"
                />
                <Carte
                  titre="📈 Rendement brut"
                  valeur={`${calcul.rendementBrut.toFixed(2)}%`}
                  detail="Dividendes bruts ÷ coût d'achat"
                />
              </>
            ) : (
              <Carte
                titre="💰 Dividendes"
                valeur="Inconnu"
                detail="Pas de dividende récent trouvé pour cette société"
              />
            )}
          </div>

          {/* Alertes pedagogiques */}
          {calcul.rendementBrut > 15 && (
            <div className="alerte">
              ⚠️ <strong>Rendement anormalement élevé.</strong> Le dernier
              dividende de {action.symbole} était probablement exceptionnel
              (vente d'actif, résultat inhabituel…). Ne compte pas dessus
              chaque année : regarde l'historique sur la{" "}
              <Link to={`/action/${action.symbole}`}>fiche de l'action</Link>.
            </div>
          )}
          {action.liquidite === "faible" && (
            <div className="alerte">
              🔴 <strong>Action peu liquide.</strong> Il ne s'échange que{" "}
              {Math.round(action.volume_moyen)} titres de {action.symbole} par
              jour en moyenne. Acheter {nbActions} actions représente{" "}
              {calcul.joursPourAcheter > 1
                ? `environ ${Math.ceil(calcul.joursPourAcheter)} jours de volume : ton ordre pourrait mettre longtemps à être exécuté, et revendre sera tout aussi lent.`
                : "une part importante du volume quotidien : l'ordre peut être lent à exécuter."}
            </div>
          )}

          <div className="note-fiscale">
            <h2>📋 À savoir (résident fiscal français)</h2>
            <ul>
              <li>
                <strong>Estimation, pas promesse</strong> : le calcul se base
                sur le dernier dividende versé ({action.annee_dividende ?? "?"}
                ). Une société peut l'augmenter, le baisser ou le supprimer.
              </li>
              <li>
                <strong>Fiscalité française</strong> : vivant en France, tu dois
                déclarer ces dividendes. Ils subissent le prélèvement
                forfaitaire (~30 %), avec un crédit d'impôt possible selon la
                convention fiscale du pays — à valider avec un professionnel.
              </li>
              <li>
                <strong>Frais non inclus</strong> : les SGI prennent des frais
                de courtage (souvent ~1 % par ordre) et parfois des frais de
                tenue de compte.
              </li>
              <li>
                <strong>Comment acheter depuis la France ?</strong> Via une SGI
                agréée BRVM (certaines acceptent l'ouverture de compte à
                distance pour les résidents français). Jamais d'achat
                automatisé ici : cet outil sert à comprendre, pas à trader.
              </li>
            </ul>
          </div>
        </>
      )}
    </>
  );
}

function Carte({ titre, valeur, sous, detail }) {
  return (
    <div className="carte">
      <div className="carte-titre">{titre}</div>
      <div className="carte-valeur">{valeur}</div>
      {sous && <div className="carte-sous">{sous}</div>}
      {detail && <div className="carte-detail">{detail}</div>}
    </div>
  );
}
