// Analyse comparee d'une action face au reste de la cote BRVM.
// Chaque metrique est expliquee avec des mots simples et traduite en euros
// concrets selon le montant que l'utilisateur envisage d'investir.
import { useState } from "react";
import { FCFA_PAR_EURO, formatEUR } from "../api.js";

function mediane(valeurs) {
  if (!valeurs.length) return null;
  const tri = [...valeurs].sort((a, b) => a - b);
  const m = Math.floor(tri.length / 2);
  return tri.length % 2 ? tri[m] : (tri[m - 1] + tri[m]) / 2;
}

// Position 0..100 de `valeur` entre min et max du marche (pour la jauge).
function positionPct(valeur, valeurs) {
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);
  if (max === min) return 50;
  return ((valeur - min) / (max - min)) * 100;
}

// Classement decroissant : 1 = valeur la plus haute du marche.
function rang(valeur, valeurs) {
  return [...valeurs].sort((a, b) => b - a).indexOf(valeur) + 1;
}

function Jauge({ valeur, valeurs, format }) {
  const pct = positionPct(valeur, valeurs);
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);
  return (
    <div className="jauge-bloc">
      <div className="jauge">
        <div className="jauge-marqueur" style={{ left: `${pct}%` }} />
      </div>
      <div className="jauge-labels">
        <span>{format(min)} (min du marché)</span>
        <span>{format(max)} (max)</span>
      </div>
    </div>
  );
}

function BlocMetrique({ emoji, titre, valeurAffichee, enfants }) {
  return (
    <div className="bloc-analyse">
      <h3>
        {emoji} {titre} : <span className="valeur-metrique">{valeurAffichee}</span>
      </h3>
      {enfants}
    </div>
  );
}

function tendanceDividendes(dividendes) {
  const serie = [...(dividendes ?? [])]
    .filter((d) => d.montant != null)
    .sort((a, b) => a.annee - b.annee);
  if (serie.length < 2) return null;
  const premier = serie[0];
  const dernier = serie[serie.length - 1];
  const evolution = ((dernier.montant - premier.montant) / premier.montant) * 100;
  const toujoursEnHausse = serie.every(
    (d, i) => i === 0 || d.montant >= serie[i - 1].montant
  );
  if (toujoursEnHausse && evolution > 5)
    return {
      verdict: "en hausse régulière",
      emoji: "🌱",
      texte: `Il n'a jamais baissé entre ${premier.annee} et ${dernier.annee} (+${evolution.toFixed(0)} % au total). C'est le meilleur signe possible : l'entreprise gagne de plus en plus et partage.`,
    };
  if (Math.abs(evolution) <= 5)
    return {
      verdict: "stable",
      emoji: "⚖️",
      texte: `Quasi le même montant chaque année depuis ${premier.annee}. Fiable, mais ton revenu n'augmentera pas.`,
    };
  if (evolution < 0)
    return {
      verdict: "en baisse",
      emoji: "📉",
      texte: `Il a reculé de ${Math.abs(evolution).toFixed(0)} % depuis ${premier.annee}. Prudence : ce que tu toucherais l'an prochain sera peut-être moins que le chiffre affiché.`,
    };
  return {
    verdict: "irrégulier",
    emoji: "🎢",
    texte: `Il monte et descend selon les années. Ne compte pas sur un revenu fixe avec cette action.`,
  };
}

export default function AnalyseComparative({ action, marche }) {
  const [montant, setMontant] = useState(500); // investissement fictif en €

  const moi = marche.find((a) => a.symbole === action.symbole);
  if (!moi) return null;

  const nb = marche.length;

  const variations = marche.filter((a) => a.variation != null).map((a) => a.variation);
  const volumes = marche.filter((a) => a.volume_moyen != null).map((a) => a.volume_moyen);
  const rendements = marche.filter((a) => a.rendement != null).map((a) => a.rendement);

  const varMoyenne = variations.reduce((s, v) => s + v, 0) / variations.length;
  const volMediane = mediane(volumes);
  const rendMediane = mediane(rendements);
  const tendance = tendanceDividendes(action.dividendes);

  // Traduction du montant en actions concretes
  const montantFCFA = montant * FCFA_PAR_EURO;
  const nbActions = moi.cours_cloture
    ? Math.floor(montantFCFA / moi.cours_cloture)
    : 0;
  const impactJour = (montant * (moi.variation ?? 0)) / 100; // en €
  const divAnnuelEur =
    moi.dividende != null && nbActions > 0
      ? (nbActions * moi.dividende) / FCFA_PAR_EURO
      : null;
  const joursPourAcheter =
    moi.volume_moyen > 0 ? nbActions / moi.volume_moyen : null;

  return (
    <section className="analyse">
      <h2>🔍 Analyse comparée — {moi.symbole} face aux {nb} actions de la cote</h2>

      <div className="montant-fictif">
        💶 Et si j'investissais{" "}
        <input
          type="number"
          min="1"
          value={montant}
          onChange={(e) => setMontant(Number(e.target.value) || 0)}
        />{" "}
        € ? → ça ferait{" "}
        <strong>
          {nbActions.toLocaleString("fr-FR")} action{nbActions > 1 ? "s" : ""}{" "}
          {moi.symbole}
        </strong>{" "}
        au cours actuel. Toutes les explications ci-dessous utilisent ce montant.
      </div>

      {/* ---------------- VARIATION ---------------- */}
      {moi.variation != null && (
        <BlocMetrique
          emoji="📊"
          titre="Variation du jour"
          valeurAffichee={
            <span className={moi.variation > 0 ? "hausse" : moi.variation < 0 ? "baisse" : ""}>
              {moi.variation > 0 ? "+" : ""}
              {moi.variation.toFixed(2)}%
            </span>
          }
          enfants={
            <>
              <p className="explication">
                <strong>C'est quoi ?</strong> De combien le prix de l'action a
                bougé depuis hier. C'est tout. Ça monte et ça descend tous les
                jours, comme le prix de l'essence.
              </p>
              <p className="interpretation">
                💶 <strong>Avec tes {montant} € investis</strong>, la journée
                d'aujourd'hui ({moi.variation > 0 ? "+" : ""}
                {moi.variation.toFixed(2)} %) représente{" "}
                <strong className={impactJour >= 0 ? "hausse" : "baisse"}>
                  {impactJour >= 0 ? "+" : ""}
                  {formatEUR(impactJour)}
                </strong>{" "}
                sur la valeur de revente.{" "}
                <strong>
                  Mais attention : tu possèdes toujours tes {nbActions.toLocaleString("fr-FR")} actions, et tes
                  dividendes ne changent pas.
                </strong>{" "}
                Une baisse ne te fait vraiment perdre de l'argent que si tu
                vends ce jour-là. Si tu gardes, ce n'est qu'un chiffre qui
                bouge sur un écran.
              </p>
              <Jauge
                valeur={moi.variation}
                valeurs={variations}
                format={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`}
              />
              <p className="analyse-stats">
                Aujourd'hui : <strong>{rang(moi.variation, variations)}ᵉ / {nb}</strong>
                {" · "}moyenne du marché :{" "}
                <strong>{varMoyenne > 0 ? "+" : ""}{varMoyenne.toFixed(2)}%</strong>
                {" · "}bon à savoir : la BRVM plafonne à ±7,5 % par jour, pas de
                krach éclair possible.
              </p>
            </>
          }
        />
      )}

      {/* ---------------- VOLUME ---------------- */}
      {moi.volume_moyen != null && (
        <BlocMetrique
          emoji="🔄"
          titre="Volume / liquidité"
          valeurAffichee={
            <>
              {Math.round(moi.volume_moyen).toLocaleString("fr-FR")} titres/jour{" "}
              {moi.liquidite === "haute" ? "🟢" : moi.liquidite === "moyenne" ? "🟡" : "🔴"}
            </>
          }
          enfants={
            <>
              <p className="explication">
                <strong>C'est quoi ?</strong> Le nombre d'actions qui trouvent
                un acheteur chaque jour. Pour vendre, il faut que quelqu'un
                achète en face — comme sur Leboncoin. Beaucoup d'échanges =
                tu revends quand tu veux. Peu d'échanges = tu peux rester
                coincé avec tes actions.
              </p>
              <p className="interpretation">
                💶 <strong>Tes {nbActions.toLocaleString("fr-FR")} actions</strong> face aux ~
                {Math.round(moi.volume_moyen).toLocaleString("fr-FR")} échangées par jour :{" "}
                {joursPourAcheter == null || nbActions === 0 ? (
                  "montant trop petit pour estimer."
                ) : joursPourAcheter <= 0.1 ? (
                  <>ton ordre passerait <strong>dans la journée, sans problème</strong>. Acheter et revendre est facile ici.</>
                ) : joursPourAcheter <= 1 ? (
                  <>ton ordre représenterait une bonne partie d'une journée d'échanges : il passerait, mais <strong>peut-être pas en une seule fois</strong>.</>
                ) : (
                  <>ton ordre représente <strong>{Math.ceil(joursPourAcheter)} jours d'échanges complets</strong> : acheter serait lent, et surtout <strong>revendre pourrait prendre des semaines</strong>. C'est le vrai danger de cette action pour un débutant.</>
                )}
              </p>
              <Jauge
                valeur={moi.volume_moyen}
                valeurs={volumes}
                format={(v) => Math.round(v).toLocaleString("fr-FR")}
              />
              <p className="analyse-stats">
                Classement : <strong>{rang(moi.volume_moyen, volumes)}ᵉ / {nb}</strong> la plus échangée
                {" · "}médiane du marché :{" "}
                <strong>{Math.round(volMediane).toLocaleString("fr-FR")} titres/jour</strong>
              </p>
            </>
          }
        />
      )}

      {/* ---------------- RENDEMENT ---------------- */}
      <BlocMetrique
        emoji="💰"
        titre="Rendement du dividende"
        valeurAffichee={
          moi.rendement != null ? `${moi.rendement.toFixed(2)}%${moi.rendement > 15 ? " ⚠️" : ""}` : "inconnu"
        }
        enfants={
          moi.rendement != null ? (
            <>
              <p className="explication">
                <strong>C'est quoi ?</strong> Le « loyer » que te verse
                l'entreprise chaque année pour te remercier d'être actionnaire.
                Contrairement à la variation, ce n'est pas un chiffre qui
                bouge sur un écran : c'est du <strong>vrai argent versé sur ton
                compte</strong>, une fois par an, que le cours ait monté ou baissé.
              </p>
              <p className="interpretation">
                💶 <strong>Avec tes {montant} €</strong> ({nbActions.toLocaleString("fr-FR")} actions ×{" "}
                {moi.dividende?.toLocaleString("fr-FR")} FCFA), tu toucherais
                environ{" "}
                <strong className="hausse">{formatEUR(divAnnuelEur)} par an</strong>{" "}
                avant impôts — même les jours où la variation est rouge.
              </p>
              <Jauge
                valeur={moi.rendement}
                valeurs={rendements}
                format={(v) => `${v.toFixed(1)}%`}
              />
              <p className="analyse-stats">
                Classement : <strong>{rang(moi.rendement, rendements)}ᵉ / {rendements.length}</strong> payeuses connues
                {" · "}médiane du marché : <strong>{rendMediane.toFixed(2)}%</strong>
                {" → "}
                {moi.rendement > rendMediane ? (
                  <strong className="hausse">au-dessus de la médiane</strong>
                ) : (
                  <strong>sous la médiane</strong>
                )}
              </p>
              {moi.rendement > 15 && (
                <p className="interpretation">
                  ⚠️ Rendement anormalement élevé : le dernier dividende était
                  probablement exceptionnel. Ne compte pas le retoucher chaque
                  année — regarde l'historique ci-dessous.
                </p>
              )}
              {tendance && (
                <p className="interpretation">
                  {tendance.emoji} <strong>Dividende {tendance.verdict}</strong> : {tendance.texte}
                </p>
              )}
            </>
          ) : (
            <p className="explication">
              Aucun dividende récent trouvé : cette société ne verse rien à ses
              actionnaires en ce moment (elle réinvestit tout, ou elle perd de
              l'argent). Avec {montant} €, tu toucherais <strong>0 €/an</strong> :
              ton seul espoir de gain serait la hausse du cours.
            </p>
          )
        }
      />

      <p className="explication note-analyse">
        📚 À retenir : la <strong>variation</strong> ne touche que la valeur de
        revente (rien n'est perdu tant qu'on ne vend pas), le{" "}
        <strong>volume</strong> dit si tu peux récupérer ton argent facilement,
        et le <strong>rendement</strong> est le seul des trois qui met du vrai
        argent dans ta poche chaque année.
      </p>
    </section>
  );
}
