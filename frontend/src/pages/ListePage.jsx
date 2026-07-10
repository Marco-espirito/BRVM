import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getActions, refresh, formatFCFA } from "../api.js";

// Watchlist : simple liste de symboles stockee dans le navigateur.
function lireWatchlist() {
  try {
    return JSON.parse(localStorage.getItem("watchlist")) ?? [];
  } catch {
    return [];
  }
}

// Drapeaux des pays de l'UEMOA representes a la BRVM.
const DRAPEAUX = {
  "Côte d'Ivoire": "🇨🇮",
  "Sénégal": "🇸🇳",
  "Bénin": "🇧🇯",
  "Burkina Faso": "🇧🇫",
  "Mali": "🇲🇱",
  "Niger": "🇳🇪",
  "Togo": "🇹🇬",
};

// Pastille de liquidite : a quel point l'action s'echange facilement.
const LIQUIDITE = {
  haute: {
    icone: "🟢",
    aide: "Liquidité haute : plus de 1 000 titres échangés par jour en moyenne — facile d'acheter et de revendre.",
  },
  moyenne: {
    icone: "🟡",
    aide: "Liquidité moyenne : entre 100 et 1 000 titres/jour — passer un gros ordre peut prendre du temps.",
  },
  faible: {
    icone: "🔴",
    aide: "Liquidité faible : moins de 100 titres échangés par jour — difficile de revendre rapidement. Prudence pour un débutant.",
  },
};

// Petites explications pour debutant, affichees au survol des colonnes.
const AIDE = {
  cours: "Dernier cours de clôture, en FCFA. Un cours élevé ne veut pas dire « cher » : ce qui compte, c'est le prix par rapport à ce que rapporte l'action.",
  variation: "Évolution du cours sur la dernière séance. Une journée ne dit rien : regarde la tendance sur des semaines.",
  volume: "Nombre d'actions échangées dans la journée, avec une pastille de liquidité : 🟢 facile à acheter/revendre, 🟡 moyen, 🔴 difficile (calculée sur le volume moyen des jours enregistrés).",
  dividende: "Dernier dividende annuel versé, en FCFA par action. À la BRVM, c'est la principale source de gain des investisseurs.",
  rendement: "Dividende ÷ cours actuel. Ex : 6 % = pour 100 000 FCFA investis, ~6 000 FCFA de dividendes par an (avant impôts). Un rendement anormalement élevé (⚠️) est souvent exceptionnel, pas durable.",
};

export default function ListePage() {
  const [actions, setActions] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);
  const [recherche, setRecherche] = useState("");
  const [tri, setTri] = useState({ champ: "symbole", sens: 1 });
  const [watchlist, setWatchlist] = useState(lireWatchlist);
  const [rafraichit, setRafraichit] = useState(false);
  const [paysActif, setPaysActif] = useState(null); // null = tous

  async function charger() {
    setChargement(true);
    setErreur(null);
    try {
      setActions(await getActions());
    } catch (e) {
      setErreur(e.message);
    } finally {
      setChargement(false);
    }
  }

  useEffect(() => {
    charger();
  }, []);

  async function rafraichir() {
    setRafraichit(true);
    try {
      await refresh(); // relance le scraping cote backend
      await charger();
    } catch (e) {
      setErreur(e.message);
    } finally {
      setRafraichit(false);
    }
  }

  function toggleEtoile(symbole) {
    setWatchlist((w) => {
      const nouvelle = w.includes(symbole)
        ? w.filter((s) => s !== symbole)
        : [...w, symbole];
      localStorage.setItem("watchlist", JSON.stringify(nouvelle));
      return nouvelle;
    });
  }

  // Liste des pays presents, avec le nombre d'actions par pays
  const paysDisponibles = useMemo(() => {
    const compte = {};
    for (const a of actions) compte[a.pays] = (compte[a.pays] ?? 0) + 1;
    return Object.entries(compte).sort((x, y) => y[1] - x[1]);
  }, [actions]);

  // Filtrage + tri, favoris toujours en tete
  const affichees = useMemo(() => {
    const q = recherche.trim().toLowerCase();
    let liste = actions.filter(
      (a) =>
        (a.symbole.toLowerCase().includes(q) ||
          a.nom.toLowerCase().includes(q)) &&
        (paysActif === null || a.pays === paysActif)
    );
    liste = [...liste].sort((a, b) => {
      const favA = watchlist.includes(a.symbole) ? 0 : 1;
      const favB = watchlist.includes(b.symbole) ? 0 : 1;
      if (favA !== favB) return favA - favB; // favoris d'abord
      const va = a[tri.champ] ?? -Infinity;
      const vb = b[tri.champ] ?? -Infinity;
      if (typeof va === "string") return va.localeCompare(vb) * tri.sens;
      return (va - vb) * tri.sens;
    });
    return liste;
  }, [actions, recherche, tri, watchlist, paysActif]);

  function trierPar(champ) {
    setTri((t) =>
      t.champ === champ ? { champ, sens: -t.sens } : { champ, sens: 1 }
    );
  }

  if (chargement) return <p className="info">Chargement des cotations…</p>;
  if (erreur)
    return (
      <div className="info erreur">
        <p>Erreur : {erreur}</p>
        <p>Le backend est-il démarré sur http://localhost:8000 ?</p>
      </div>
    );

  return (
    <>
      <div className="barre-outils">
        <input
          className="recherche"
          placeholder="Rechercher une action (ex: Sonatel, NTLC…)"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
        />
        <button className="btn" onClick={rafraichir} disabled={rafraichit}>
          {rafraichit ? "⏳ Scraping en cours…" : "🔄 Rafraîchir les cours"}
        </button>
      </div>

      <div className="filtres-pays">
        <button
          className={"filtre-pays " + (paysActif === null ? "actif" : "")}
          onClick={() => setPaysActif(null)}
        >
          🌍 Tous ({actions.length})
        </button>
        {paysDisponibles.map(([pays, nb]) => (
          <button
            key={pays}
            className={"filtre-pays " + (paysActif === pays ? "actif" : "")}
            onClick={() => setPaysActif(paysActif === pays ? null : pays)}
          >
            {DRAPEAUX[pays] ?? "🏳️"} {pays} ({nb})
          </button>
        ))}
      </div>

      <table className="tableau">
        <thead>
          <tr>
            <th className="col-etoile" title="Ta watchlist : clique sur l'étoile pour épingler une action en haut de la liste.">⭐</th>
            <th onClick={() => trierPar("symbole")}>Symbole</th>
            <th onClick={() => trierPar("nom")}>Société</th>
            <th onClick={() => trierPar("cours_cloture")} className="num" title={AIDE.cours}>
              Cours ⓘ
            </th>
            <th onClick={() => trierPar("variation")} className="num" title={AIDE.variation}>
              Variation ⓘ
            </th>
            <th onClick={() => trierPar("dividende")} className="num" title={AIDE.dividende}>
              Dividende ⓘ
            </th>
            <th onClick={() => trierPar("rendement")} className="num" title={AIDE.rendement}>
              Rendement ⓘ
            </th>
            <th onClick={() => trierPar("volume")} className="num" title={AIDE.volume}>
              Volume ⓘ
            </th>
          </tr>
        </thead>
        <tbody>
          {affichees.map((a) => {
            const favori = watchlist.includes(a.symbole);
            return (
              <tr key={a.symbole} className={favori ? "ligne-favori" : ""}>
                <td className="col-etoile">
                  <button
                    className={"etoile " + (favori ? "active" : "")}
                    onClick={() => toggleEtoile(a.symbole)}
                    title={favori ? "Retirer de la watchlist" : "Ajouter à la watchlist"}
                  >
                    {favori ? "★" : "☆"}
                  </button>
                </td>
                <td>
                  <Link to={`/action/${a.symbole}`} className="symbole">
                    {a.symbole}
                  </Link>
                </td>
                <td className="nom">
                  <span title={a.pays}>{DRAPEAUX[a.pays] ?? ""}</span> {a.nom}
                </td>
                <td className="num">{formatFCFA(a.cours_cloture)}</td>
                <td
                  className={
                    "num " +
                    (a.variation > 0 ? "hausse" : a.variation < 0 ? "baisse" : "")
                  }
                >
                  {a.variation > 0 ? "▲" : a.variation < 0 ? "▼" : "•"}{" "}
                  {a.variation?.toFixed(2)}%
                </td>
                <td className="num">
                  {a.dividende != null ? (
                    <span title={`Dividende ${a.annee_dividende}`}>
                      {formatFCFA(a.dividende)}
                    </span>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="num rendement">
                  {a.rendement != null ? (
                    <>
                      {a.rendement.toFixed(2)}%
                      {a.rendement > 15 && (
                        <span title="Rendement anormalement élevé : probablement un dividende exceptionnel, non durable. À vérifier avant de s'emballer !">
                          {" "}⚠️
                        </span>
                      )}
                    </>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="num">
                  {a.liquidite && (
                    <span title={LIQUIDITE[a.liquidite].aide}>
                      {LIQUIDITE[a.liquidite].icone}{" "}
                    </span>
                  )}
                  {a.volume?.toLocaleString("fr-FR") ?? "-"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="compteur">
        {affichees.length} actions affichées
        {watchlist.length > 0 && ` · ${watchlist.length} en watchlist ⭐`}
        {" · "}survole les ⓘ pour comprendre chaque colonne
      </p>
    </>
  );
}
