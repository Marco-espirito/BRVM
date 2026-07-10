import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ajouterWatchlist, getActions, getTopActions, getWatchlist, retirerWatchlist, formatFCFA } from "../api.js";

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

// Emoji par secteur officiel BRVM.
const EMOJI_SECTEUR = {
  "Services financiers": "🏦",
  "Télécommunications": "📡",
  "Énergie": "⛽",
  "Consommation de base": "🛒",
  "Consommation discrétionnaire": "🛍️",
  "Industriels": "🏭",
  "Services publics": "💡",
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
  const [watchlist, setWatchlist] = useState([]);
  const [paysActif, setPaysActif] = useState(null); // null = tous
  const [secteurActif, setSecteurActif] = useState(null); // null = tous

  async function charger() {
    setChargement(true);
    setErreur(null);
    try {
      // Le score /100 (rendement + liquidite + historique du dividende)
      // vient de /top-actions : on le greffe sur chaque action.
      const [liste, scores] = await Promise.all([
        getActions(),
        getTopActions(47).catch(() => []),
      ]);
      const favorisSynchronises = await getWatchlist();
      setWatchlist(favorisSynchronises);
      const scoreParSymbole = Object.fromEntries(
        scores.map((s) => [s.symbole, s.score])
      );
      setActions(
        liste.map((a) => ({ ...a, score: scoreParSymbole[a.symbole] ?? null }))
      );
    } catch (e) {
      setErreur(e.message);
    } finally {
      setChargement(false);
    }
  }

  useEffect(() => {
    charger();
  }, []);

  async function toggleEtoile(symbole) {
    setWatchlist((w) => {
      const nouvelle = w.includes(symbole)
        ? w.filter((s) => s !== symbole)
        : [...w, symbole];
      return nouvelle;
    });
    if (watchlist.includes(symbole)) await retirerWatchlist(symbole);
    else await ajouterWatchlist(symbole);
  }

  // Les deux filtres se repondent : le panneau Pays compte dans le perimetre
  // du secteur choisi, et le panneau Secteurs dans celui du pays choisi.
  const paysDisponibles = useMemo(() => {
    const compte = {};
    for (const a of actions)
      if (secteurActif === null || a.secteur === secteurActif)
        compte[a.pays] = (compte[a.pays] ?? 0) + 1;
    return Object.entries(compte).sort((x, y) => y[1] - x[1]);
  }, [actions, secteurActif]);

  const secteursDisponibles = useMemo(() => {
    const compte = {};
    for (const a of actions)
      if (a.secteur && (paysActif === null || a.pays === paysActif))
        compte[a.secteur] = (compte[a.secteur] ?? 0) + 1;
    return Object.entries(compte).sort((x, y) => y[1] - x[1]);
  }, [actions, paysActif]);

  // Choisir un pays : si le secteur en cours n'existe pas dans ce pays,
  // on le retire (sinon la liste afficherait 0 action). Et inversement.
  function choisirPays(pays) {
    const nouveau = paysActif === pays ? null : pays;
    setPaysActif(nouveau);
    if (
      nouveau &&
      secteurActif &&
      !actions.some((a) => a.pays === nouveau && a.secteur === secteurActif)
    )
      setSecteurActif(null);
    // Filtrer = chercher les meilleures : on trie par score decroissant.
    if (nouveau) setTri({ champ: "score", sens: -1 });
  }

  function choisirSecteur(secteur) {
    const nouveau = secteurActif === secteur ? null : secteur;
    setSecteurActif(nouveau);
    if (
      nouveau &&
      paysActif &&
      !actions.some((a) => a.secteur === nouveau && a.pays === paysActif)
    )
      setPaysActif(null);
    if (nouveau) setTri({ champ: "score", sens: -1 });
  }

  // Filtrage + tri, favoris toujours en tete
  const affichees = useMemo(() => {
    const q = recherche.trim().toLowerCase();
    let liste = actions.filter(
      (a) =>
        (a.symbole.toLowerCase().includes(q) ||
          a.nom.toLowerCase().includes(q)) &&
        (paysActif === null || a.pays === paysActif) &&
        (secteurActif === null || a.secteur === secteurActif)
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
  }, [actions, recherche, tri, watchlist, paysActif, secteurActif]);

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
      </div>

      <div className="filtres-barre">
        {/* Filtre pays : bouton compact, panneau au survol */}
        <div className="dropdown">
          <button className={"dropdown-btn " + (paysActif ? "filtre-on" : "")}>
            {paysActif
              ? `${DRAPEAUX[paysActif] ?? ""} ${paysActif}`
              : "🌍 Pays"}{" "}
            ▾
          </button>
          <div className="dropdown-panel">
            <button
              className={"filtre-pays " + (paysActif === null ? "actif" : "")}
              onClick={() => setPaysActif(null)}
            >
              🌍 Tous ({paysDisponibles.reduce((s, [, nb]) => s + nb, 0)})
            </button>
            {paysDisponibles.map(([pays, nb]) => (
              <button
                key={pays}
                className={"filtre-pays " + (paysActif === pays ? "actif" : "")}
                onClick={() => choisirPays(pays)}
              >
                {DRAPEAUX[pays] ?? "🏳️"} {pays} ({nb})
              </button>
            ))}
          </div>
        </div>

        {/* Filtre secteurs : idem */}
        {secteursDisponibles.length > 0 && (
          <div className="dropdown">
            <button className={"dropdown-btn " + (secteurActif ? "filtre-on" : "")}>
              {secteurActif
                ? `${EMOJI_SECTEUR[secteurActif] ?? ""} ${secteurActif}`
                : "🏢 Secteurs"}{" "}
              ▾
            </button>
            <div className="dropdown-panel">
              <button
                className={"filtre-pays " + (secteurActif === null ? "actif" : "")}
                onClick={() => setSecteurActif(null)}
              >
                🏢 Tous les secteurs
                {paysActif ? ` ${DRAPEAUX[paysActif] ?? ""}` : ""}
              </button>
              {secteursDisponibles.map(([secteur, nb]) => (
                <button
                  key={secteur}
                  className={"filtre-pays " + (secteurActif === secteur ? "actif" : "")}
                  onClick={() => choisirSecteur(secteur)}
                >
                  {EMOJI_SECTEUR[secteur] ?? "🏢"} {secteur} ({nb})
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Rappel des filtres actifs + reset */}
        {(paysActif || secteurActif) && (
          <button
            className="filtre-reset"
            onClick={() => {
              setPaysActif(null);
              setSecteurActif(null);
            }}
          >
            ✕ Réinitialiser
          </button>
        )}
      </div>

      <div className="table-scroll table-scroll-principal"><table className="tableau">
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
            <th>Achat</th>
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
                  {a.score != null && (
                    <span
                      className="score-pill"
                      title={`Score ${a.score}/100 : rendement (40) + liquidité (30) + historique du dividende (30). Détail sur l'onglet Portefeuille.`}
                    >
                      {Math.round(a.score)}
                    </span>
                  )}
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
                <td>
                  <Link
                    className="btn-mini-acheter"
                    to={`/portefeuille?acheter=${encodeURIComponent(a.symbole)}`}
                    title={`Acheter des actions ${a.symbole}`}
                  >
                    Acheter
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table></div>
      <p className="compteur">
        {affichees.length} actions affichées
        {tri.champ === "score" &&
          tri.sens === -1 &&
          " · triées de la meilleure à la moins bonne (score /100 à côté du symbole)"}
        {watchlist.length > 0 && ` · ${watchlist.length} en watchlist ⭐`}
        {" · "}survole les ⓘ pour comprendre chaque colonne
      </p>
    </>
  );
}
