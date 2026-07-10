import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  Legend,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from "recharts";
import {
  getActions,
  getPortefeuille,
  getTopActions,
  acheterPosition,
  vendrePartiellement,
  mouvementEspeces,
  exportTransactionsCsv,
  getMesPortefeuilles,
  creerPortefeuille,
  renommerPortefeuille,
  supprimerPortefeuille,
  formatFCFA,
  formatEUR,
  enEuros,
} from "../api.js";

const DRAPEAUX = {
  "Côte d'Ivoire": "🇨🇮",
  "Sénégal": "🇸🇳",
  "Bénin": "🇧🇯",
  "Burkina Faso": "🇧🇫",
  "Mali": "🇲🇱",
  "Niger": "🇳🇪",
  "Togo": "🇹🇬",
};
const COULEURS = ["#2563eb", "#16a34a", "#f59e0b", "#7c3aed", "#dc2626", "#0891b2", "#64748b"];

export default function PortefeuillePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [portefeuille, setPortefeuille] = useState(null);
  const [actions, setActions] = useState([]);
  const [top, setTop] = useState([]);
  const [erreur, setErreur] = useState(null);
  const [symbole, setSymbole] = useState("");
  const [quantite, setQuantite] = useState(10);
  const [enCours, setEnCours] = useState(false);
  const [fraisAchat, setFraisAchat] = useState(1);
  const [portefeuilles, setPortefeuilles] = useState([]);
  const [portefeuilleActif, setPortefeuilleActif] = useState(null);
  const [operation, setOperation] = useState(null);
  const [operationQuantite, setOperationQuantite] = useState(1);
  const [operationMontant, setOperationMontant] = useState(100000);
  const [operationFrais, setOperationFrais] = useState(1);
  const [operationFiscalite, setOperationFiscalite] = useState(0);
  const [gestionPortefeuille, setGestionPortefeuille] = useState(null);

  async function charger(forcerId = null) {
    try {
      const ps = await getMesPortefeuilles();
      const memorise = Number(localStorage.getItem("portefeuille-actif"));
      const id = forcerId ?? (portefeuilleActif && ps.some((p) => p.id === portefeuilleActif) ? portefeuilleActif : ps.find((p) => p.id === memorise)?.id) ?? ps[0]?.id;
      setPortefeuilles(ps); setPortefeuilleActif(id);
      const [p, a, t] = await Promise.all([
        getPortefeuille(id),
        getActions(),
        getTopActions(),
      ]);
      setPortefeuille(p);
      setActions(a);
      setTop(t);
      const symboleDemande = searchParams.get("acheter")?.toUpperCase();
      if (symboleDemande && a.some((action) => action.symbole === symboleDemande)) {
        setSymbole(symboleDemande);
        setSearchParams({}, { replace: true });
      } else if (!symbole && a.length) setSymbole(a[0].symbole);
    } catch (e) {
      setErreur(e.message);
    }
  }

  useEffect(() => {
    charger();
  }, []);

  const actionChoisie = useMemo(
    () => actions.find((a) => a.symbole === symbole),
    [actions, symbole]
  );
  const coutEstime =
    actionChoisie?.cours_cloture && quantite > 0
      ? actionChoisie.cours_cloture * quantite
      : null;
  const coutAvecFrais = coutEstime == null
    ? null
    : coutEstime * (1 + fraisAchat / 100);
  const soldeInsuffisant = coutAvecFrais != null && coutAvecFrais > (portefeuille?.solde_especes ?? 0);

  async function acheter(e) {
    e.preventDefault();
    if (!symbole || quantite <= 0) return;
    setEnCours(true);
    setErreur(null);
    try {
      await acheterPosition(symbole, quantite, fraisAchat, portefeuilleActif);
      await charger();
    } catch (e2) {
      setErreur(e2.message);
    } finally {
      setEnCours(false);
    }
  }

  function ouvrirOperation(type, position = null) {
    setOperation({ type, position });
    setOperationQuantite(type === "VENTE" ? position.quantite : 1);
    setOperationMontant(100000);
    setOperationFrais(fraisAchat);
    setOperationFiscalite(0);
    setErreur(null);
  }

  async function confirmerOperation(e) {
    e.preventDefault();
    if (!operation) return;
    const { type, position } = operation;
    const estEspeces = type === "DEPOT" || type === "RETRAIT";
    setErreur(null);
    setEnCours(true);
    try {
      if (estEspeces) await mouvementEspeces(type, operationMontant, portefeuilleActif);
      else if (type === "AJOUT") await acheterPosition(position.symbole, operationQuantite, operationFrais, portefeuilleActif);
      else await vendrePartiellement(position.id, operationQuantite, operationFrais, operationFiscalite, portefeuilleActif);
      await charger();
      setOperation(null);
    } catch (e) {
      setErreur(e.message);
    } finally {
      setEnCours(false);
    }
  }

  if (erreur && !portefeuille)
    return (
      <div className="info erreur">
        <p>Erreur : {erreur}</p>
        <p>Le backend est-il démarré sur http://localhost:8000 ?</p>
      </div>
    );
  if (!portefeuille) return <p className="info">Chargement…</p>;

  const { positions, historique } = portefeuille;
  const nombreTotalActions = positions.reduce(
    (total, position) => total + Number(position.quantite || 0),
    0,
  );
  const mouvementsAvecSolde = portefeuille.mouvements_especes ?? [];
  const gain = portefeuille.plus_value;

  return (
    <>
      <h1>💼 Mon portefeuille virtuel</h1>
      <div className="gestion-portefeuilles">
        <select value={portefeuilleActif ?? ""} onChange={(e) => { const id = Number(e.target.value); setPortefeuilleActif(id); localStorage.setItem("portefeuille-actif", id); charger(id); }}>{portefeuilles.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}</select>
        <button className="btn" onClick={() => setGestionPortefeuille({ type: "CREER" })}>+ Nouveau</button>
        <button className="btn-secondaire" onClick={() => setGestionPortefeuille({ type: "RENOMMER", portefeuille: portefeuilles.find((p) => p.id === portefeuilleActif) })}>Renommer</button>
        <button className="btn-vendre" disabled={portefeuilles.length <= 1} onClick={() => setGestionPortefeuille({ type: "SUPPRIMER", portefeuille: portefeuilles.find((p) => p.id === portefeuilleActif) })}>Supprimer</button>
      </div>
      <p className="explication" style={{ marginBottom: 16 }}>
        Achète des actions <strong>fictivement</strong> au cours du jour, comme
        si c'était réel : ton portefeuille évolue ensuite avec les vrais cours
        de la BRVM, jour après jour. Zéro risque, 100 % apprentissage — aucun
        ordre réel n'est passé.
      </p>

      <div className="tresorerie-barre">
        <div>
          <span>Liquidités disponibles</span>
          <strong>{formatFCFA(portefeuille.solde_especes)}</strong>
        </div>
        <button className="btn" onClick={() => ouvrirOperation("DEPOT")}>+ Déposer</button>
        <button className="btn-secondaire" onClick={() => ouvrirOperation("RETRAIT")}>Retirer</button>
      </div>

      {/* Top 10 pedagogique */}
      {top.length > 0 && (
        <details className="top10" open={portefeuille.positions.length === 0}>
          <summary>
            🏆 <strong>Top 10 diversifié pour débuter</strong> — le meilleur de
            chaque secteur BRVM (★), puis les meilleurs scores. Score sur 100 :
            rendement (40) + liquidité (30) + historique du dividende (30)
          </summary>
          <div className="top10-liste">
            {top.map((t) => (
              <div key={t.symbole} className="top10-carte">
                <div className="top10-entete">
                  <span className="top10-rang">#{t.rang}</span>
                  <Link to={`/action/${t.symbole}`} className="symbole">
                    {t.symbole}
                  </Link>
                  <span title={t.pays}>{DRAPEAUX[t.pays] ?? ""}</span>
                  <span className="top10-score">{t.score}/100</span>
                </div>
                <div className="top10-nom">{t.nom}</div>
                {t.secteur && (
                  <div>
                    <span className={"chip-secteur" + (t.meilleur_du_secteur ? " champion" : "")}>
                      {t.meilleur_du_secteur ? "★ Meilleur secteur " : ""}
                      {t.secteur}
                    </span>
                  </div>
                )}
                <div className="top10-barre">
                  <div
                    className="top10-barre-remplie"
                    style={{ width: `${t.score}%` }}
                  />
                </div>
                <ul className="top10-raisons">
                  {t.raisons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
                <button
                  className="btn top10-choisir"
                  onClick={() => {
                    setSymbole(t.symbole);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                >
                  Choisir pour l'achat ↑
                </button>
              </div>
            ))}
          </div>
          <p className="explication">
            ⚠️ Ce score est un <strong>filtre d'apprentissage</strong> basé sur
            les données passées (dividendes, volumes) — pas une prédiction ni un
            conseil. Une entreprise bien classée peut décevoir demain.
            💡 Pour un portefeuille diversifié, pioche parmi les <strong>★
            champions de secteur</strong> : 3-4 sociétés de secteurs différents
            (ex. une banque + un télécom + une énergie) résistent mieux qu'un
            portefeuille 100 % bancaire.
          </p>
        </details>
      )}

      {/* Formulaire d'achat */}
      <form className="simulateur-form" onSubmit={acheter}>
        <label className="champ">
          <span>Action</span>
          <select value={symbole} onChange={(e) => setSymbole(e.target.value)}>
            {actions.map((a) => (
              <option key={a.symbole} value={a.symbole}>
                {a.symbole} — {a.nom}
              </option>
            ))}
          </select>
        </label>
        <label className="champ champ-nombre">
          <span>Quantité</span>
          <input
            type="number"
            min="1"
            value={quantite}
            onChange={(e) => setQuantite(Number(e.target.value))}
          />
        </label>
        <label className="champ champ-nombre">
          <span>Frais de courtage (%)</span>
          <input type="number" min="0" max="100" step="0.01" value={fraisAchat} onChange={(e) => setFraisAchat(Number(e.target.value))} />
        </label>
        <div className="champ">
          <span>&nbsp;</span>
          <button className="btn" disabled={enCours || !coutEstime || soldeInsuffisant}>
            {enCours
              ? "⏳…"
              : soldeInsuffisant
              ? `Solde insuffisant (${formatFCFA(coutAvecFrais)})`
              : coutEstime
              ? `🛒 Acheter (${formatFCFA(coutAvecFrais)})`
              : "🛒 Acheter"}
          </button>
        </div>
      </form>
      {erreur && <p className="info erreur">{erreur}</p>}

      {positions.length === 0 && portefeuille.transactions.length === 0 ? (
        <div className="info">
          <p>
            Ton portefeuille est vide. Choisis une action ci-dessus et fais ton
            premier achat fictif ! 💡 Conseil de départ : 2-3 actions{" "}
            <Link to="/">bien notées en liquidité 🟢 et en rendement</Link>.
          </p>
        </div>
      ) : (
        <>
          {/* Cartes de synthese */}
          <div className="cartes">
            <div className="carte">
              <div className="carte-titre">Valeur globale</div>
              <div className="carte-valeur">{formatFCFA(portefeuille.valeur_globale)}</div>
              <div className="carte-detail">actions + liquidités disponibles</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Liquidités</div>
              <div className="carte-valeur">{formatFCFA(portefeuille.solde_especes)}</div>
              <div className="carte-detail">disponibles pour de nouveaux achats</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Nombre d’actions détenues</div>
              <div className="carte-valeur">{nombreTotalActions.toLocaleString("fr-FR")}</div>
              <div className="carte-detail">
                réparties entre {positions.length} entreprise{positions.length > 1 ? "s" : ""}
              </div>
            </div>
            <div className="carte">
              <div className="carte-titre">💸 Total investi</div>
              <div className="carte-valeur">{formatFCFA(portefeuille.total_investi)}</div>
              <div className="carte-sous">≈ {formatEUR(enEuros(portefeuille.total_investi))}</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Plus-value réalisée</div>
              <div className={"carte-valeur " + (portefeuille.plus_value_realisee > 0 ? "hausse" : portefeuille.plus_value_realisee < 0 ? "baisse" : "")}>{formatFCFA(portefeuille.plus_value_realisee)}</div>
              <div className="carte-detail">sur les ventes déjà effectuées</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Plus-value latente</div>
              <div className={"carte-valeur " + (portefeuille.plus_value_latente > 0 ? "hausse" : portefeuille.plus_value_latente < 0 ? "baisse" : "")}>{formatFCFA(portefeuille.plus_value_latente)}</div>
              <div className="carte-detail">sur les positions encore détenues</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Frais et fiscalité</div>
              <div className="carte-valeur">{formatFCFA(portefeuille.frais_totaux + portefeuille.fiscalite_totale)}</div>
              <div className="carte-detail">courtage {formatFCFA(portefeuille.frais_totaux)} · fiscalité {formatFCFA(portefeuille.fiscalite_totale)}</div>
            </div>
            <div className="carte">
              <div className="carte-titre">📊 Valeur actuelle</div>
              <div className="carte-valeur">{formatFCFA(portefeuille.valeur_totale)}</div>
              <div className="carte-sous">≈ {formatEUR(enEuros(portefeuille.valeur_totale))}</div>
            </div>
            <div className="carte">
              <div className="carte-titre">± Plus / moins-value</div>
              <div className={"carte-valeur " + (gain > 0 ? "hausse" : gain < 0 ? "baisse" : "")}>
                {gain >= 0 ? "+" : ""}
                {formatFCFA(gain)}
              </div>
              <div className="carte-detail">
                {portefeuille.plus_value_pct != null &&
                  `${gain >= 0 ? "+" : ""}${portefeuille.plus_value_pct.toFixed(2)} % · ≈ ${formatEUR(enEuros(gain))}`}
              </div>
            </div>
            <div className="carte">
              <div className="carte-titre">💰 Dividendes annuels estimés</div>
              <div className="carte-valeur hausse">
                {formatFCFA(portefeuille.dividendes_annuels)}
              </div>
              <div className="carte-detail">≈ {formatEUR(enEuros(portefeuille.dividendes_annuels))} · avant impôts</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Performance totale avec dividendes</div>
              <div className={"carte-valeur " + (portefeuille.performance_totale > 0 ? "hausse" : portefeuille.performance_totale < 0 ? "baisse" : "")}>
                {portefeuille.performance_totale >= 0 ? "+" : ""}{portefeuille.performance_totale_pct?.toFixed(2)} %
              </div>
              <div className="carte-detail">{formatFCFA(portefeuille.dividendes_recus)} de dividendes connus inclus</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Rendement annualisé</div>
              <div className="carte-valeur">{portefeuille.rendement_annualise == null ? "Historique insuffisant" : `${portefeuille.rendement_annualise.toFixed(2)} %`}</div>
              <div className="carte-detail">disponible après 30 jours</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Volatilité annualisée</div>
              <div className="carte-valeur">{portefeuille.volatilite_annualisee == null ? "Historique insuffisant" : `${portefeuille.volatilite_annualisee.toFixed(2)} %`}</div>
              <div className="carte-detail">calculée sur au moins 20 variations quotidiennes</div>
            </div>
            <div className="carte">
              <div className="carte-titre">Concentration maximale</div>
              <div className="carte-valeur">{portefeuille.concentration_max_pct?.toFixed(2)} %</div>
              <div className="carte-detail">poids de la plus grande position · HHI {portefeuille.indice_concentration?.toFixed(0)}</div>
            </div>
          </div>

          <h2>Répartition et concentration</h2>
          <div className="grille-repartition">
            <Repartition titre="Par secteur" donnees={portefeuille.repartition_secteurs} />
            <Repartition titre="Par pays" donnees={portefeuille.repartition_pays} />
          </div>
          {portefeuille.concentration_max_pct > 40 && <div className="alerte">⚠️ Une seule position représente plus de 40 % du portefeuille. Une baisse de cette action aurait un impact important sur l’ensemble.</div>}
          <p className="explication">
            Les dividendes reçus utilisent uniquement les exercices connus postérieurs à l’année d’achat.
            C’est une estimation prudente tant que les dates historiques de paiement ne sont pas disponibles.
            Le rendement annualisé exige 30 jours d’historique et la volatilité au moins 20 variations.
          </p>

          {/* Graphique d'evolution */}
          <h2>Évolution de la valeur du portefeuille</h2>
          {historique.length < 2 ? (
            <p className="info">
              📈 La courbe démarre aujourd'hui ({historique[0]?.jour}). Chaque
              soir à 18h30, le scraping ajoute un point : reviens dans quelques
              jours pour voir ta première évolution !
            </p>
          ) : (
            <div className="graphique">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={historique}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="jour" />
                  <YAxis domain={["auto", "auto"]} width={90} />
                  <Tooltip formatter={(v) => formatFCFA(v)} />
                  <ReferenceLine
                    y={portefeuille.total_investi}
                    stroke="#9ca3af"
                    strokeDasharray="6 4"
                    label={{ value: "investi", position: "left", fontSize: 11 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="valeur"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={false}
                    name="Valeur"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          <h2>Estimation des dividendes par entreprise</h2>
          <p className="explication">
            Estimation brute calculée avec le dernier dividende connu. Elle ne constitue pas
            une promesse de paiement : l’entreprise peut augmenter, réduire ou supprimer son dividende.
          </p>
          <div className="table-scroll">
            <table className="tableau">
              <thead>
                <tr>
                  <th>Entreprise</th>
                  <th className="num">Actions détenues</th>
                  <th className="num">Dividende estimé/action</th>
                  <th className="num">Exercice utilisé</th>
                  <th className="num">Rendement estimé</th>
                  <th>Détachement annoncé</th>
                  <th className="num">Dividende annuel estimé</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => {
                  return (
                    <tr key={position.id}>
                      <td>
                        <Link to={`/action/${position.symbole}`} className="symbole">
                          {position.symbole}
                        </Link>{" "}<span className="carte-detail">{position.nom}</span>
                        <div className="dividende-alertes">
                          {position.dividende_donnee_ancienne && <span className="badge-dividende ancien">Donnée ancienne</span>}
                          {position.dividende_potentiellement_exceptionnel && <span className="badge-dividende exceptionnel">Rendement exceptionnel à vérifier</span>}
                        </div>
                      </td>
                      <td className="num">{position.quantite.toLocaleString("fr-FR")}</td>
                      <td className="num">
                        {position.dividende_par_action == null ? "Non disponible" : formatFCFA(position.dividende_par_action)}
                      </td>
                      <td className="num">{position.annee_dividende ?? "—"}</td>
                      <td className="num">{position.rendement_dividende_pct == null ? "—" : `${position.rendement_dividende_pct.toFixed(2)} %`}</td>
                      <td>{position.date_detachement_annoncee || "Non annoncée"}</td>
                      <td className="num hausse">
                        {position.dividende_annuel == null ? "Non disponible" : formatFCFA(position.dividende_annuel)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <th>Total</th>
                  <th className="num">{nombreTotalActions.toLocaleString("fr-FR")}</th>
                  <th></th>
                  <th></th>
                  <th></th>
                  <th></th>
                  <th className="num hausse">{formatFCFA(portefeuille.dividendes_annuels)}</th>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Tableau des positions */}
          <h2>Performance face au BRVM Composite</h2>
          <p className="explication">Comparaison en base 100, hors dividendes, avec neutralisation des nouveaux apports.</p>
          {portefeuille.comparaison_indice?.length < 2 ? <p className="info">La comparaison sera disponible après plusieurs séances communes entre le portefeuille et l’indice.</p> : (
            <div className="graphique">
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={portefeuille.comparaison_indice}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="jour" />
                  <YAxis domain={["auto", "auto"]} width={55} />
                  <Tooltip formatter={(v) => Number(v).toFixed(2)} />
                  <Legend />
                  <ReferenceLine y={100} stroke="#9ca3af" strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="portefeuille" stroke="#2563eb" strokeWidth={3} dot={false} name="Portefeuille" />
                  <Line type="monotone" dataKey="indice" stroke="#16a34a" strokeWidth={2} dot={false} name={portefeuille.indice_reference} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Tableau des positions */}
          <h2>Mes positions</h2>
          <div className="table-scroll table-scroll-principal"><table className="tableau">
            <thead>
              <tr>
                <th>Action</th>
                <th className="num">Qté</th>
                <th className="num" title="Prix de revient moyen pondéré, frais d'achat inclus">PRMP</th>
                <th className="num">Cours actuel</th>
                <th className="num">Investi</th>
                <th className="num">Valeur</th>
                <th className="num" title="Ce que tu gagnerais/perdrais si tu vendais maintenant">+/-</th>
                <th className="num" title="Dividendes annuels estimes sur cette position">Div/an</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/action/${p.symbole}`} className="symbole">
                      {p.symbole}
                    </Link>{" "}
                    <span className="carte-detail">({p.jour_achat})</span>
                  </td>
                  <td className="num">{p.quantite}</td>
                  <td className="num">{formatFCFA(p.prix_achat)}</td>
                  <td className="num">{formatFCFA(p.cours_actuel)}</td>
                  <td className="num">{formatFCFA(p.investi)}</td>
                  <td className="num">{formatFCFA(p.valeur_actuelle)}</td>
                  <td
                    className={
                      "num " +
                      (p.plus_value > 0 ? "hausse" : p.plus_value < 0 ? "baisse" : "")
                    }
                  >
                    {p.plus_value != null
                      ? `${p.plus_value >= 0 ? "+" : ""}${formatFCFA(p.plus_value)} (${p.plus_value_pct >= 0 ? "+" : ""}${p.plus_value_pct.toFixed(2)}%)`
                      : "-"}
                  </td>
                  <td className="num hausse">
                    {p.dividende_annuel != null
                      ? formatFCFA(p.dividende_annuel)
                      : "-"}
                  </td>
                  <td><div className="actions-position">
                    <button
                      className="btn-mini-acheter"
                      disabled={enCours}
                      onClick={() => ouvrirOperation("AJOUT", p)}
                      title={`Ajouter des actions ${p.symbole}`}
                    >
                      + Ajouter
                    </button>
                    <button className="btn-vendre" onClick={() => ouvrirOperation("VENTE", p)}>
                      Vendre
                    </button>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table></div>
          <div className="titre-actions journal-entete">
            <h2>Journal des transactions</h2>
            <a className="btn lien-btn" href={exportTransactionsCsv(portefeuilleActif)}>Exporter le journal complet</a>
          </div>
          <div className="table-scroll"><table className="tableau">
            <thead><tr><th>Date</th><th>Type</th><th>Action</th><th className="num">Quantité</th><th className="num">Prix</th><th className="num">Frais</th><th className="num">Fiscalité</th><th className="num">Montant net</th><th className="num">Plus-value réalisée</th></tr></thead>
            <tbody>{portefeuille.transactions.map((t) => <tr key={t.id}><td>{t.jour}</td><td><span className={`transaction-badge ${t.type.toLowerCase()}`}>{t.type}</span></td><td>{t.symbole}</td><td className="num">{t.quantite}</td><td className="num">{formatFCFA(t.prix)}</td><td className="num">{formatFCFA(t.frais_courtage)}</td><td className="num">{formatFCFA(t.fiscalite)}</td><td className="num">{formatFCFA(t.montant_net)}</td><td className={"num " + (t.gain_realise > 0 ? "hausse" : t.gain_realise < 0 ? "baisse" : "")}>{t.gain_realise == null ? "—" : formatFCFA(t.gain_realise)}</td></tr>)}</tbody>
          </table></div>

          <div className="titre-actions journal-entete">
            <div><h2>Journal de trésorerie</h2><p className="explication">Dépôts et retraits effectués sur ce portefeuille.</p></div>
          </div>
          {mouvementsAvecSolde.length === 0 ? <p className="info">Aucun mouvement de trésorerie enregistré.</p> : <div className="table-scroll">
            <table className="tableau tableau-tresorerie">
              <thead><tr><th>Date</th><th>Type</th><th className="num">Montant</th><th className="num">Solde après mouvement</th></tr></thead>
              <tbody>{mouvementsAvecSolde.map((m) => <tr key={m.id}>
                <td>{new Date(`${m.cree_le}Z`).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" })}</td>
                <td><span className={`transaction-badge ${m.type === "DEPOT" ? "achat" : "vente"}`}>{m.type === "DEPOT" ? "Dépôt" : "Retrait"}</span></td>
                <td className={`num ${m.type === "DEPOT" ? "hausse" : "baisse"}`}>{m.type === "DEPOT" ? "+" : "−"}{formatFCFA(m.montant)}</td>
                <td className="num">{m.solde_apres == null ? "Historique antérieur" : formatFCFA(m.solde_apres)}</td>
              </tr>)}</tbody>
            </table>
          </div>}
          <p className="explication">
            Les achats et ventes fictifs sont enregistrés au dernier cours de clôture connu.
            Les frais saisis sont inclus dans le PRMP, les ventes alimentent les liquidités
            disponibles et le journal conserve l’historique complet des opérations.
          </p>
        </>
      )}
      {operation && <OperationModal
        operation={operation} quantite={operationQuantite} setQuantite={setOperationQuantite}
        montant={operationMontant} setMontant={setOperationMontant}
        frais={operationFrais} setFrais={setOperationFrais}
        fiscalite={operationFiscalite} setFiscalite={setOperationFiscalite}
        solde={portefeuille.solde_especes} enCours={enCours} erreur={erreur}
        onClose={() => setOperation(null)} onSubmit={confirmerOperation}
      />}
      {gestionPortefeuille && <GestionPortefeuilleModal
        gestion={gestionPortefeuille}
        onClose={() => setGestionPortefeuille(null)}
        onValider={async (valeur) => {
          setErreur(null);
          try {
            if (gestionPortefeuille.type === "CREER") {
              const cree = await creerPortefeuille(valeur);
              localStorage.setItem("portefeuille-actif", cree.id);
              await charger(cree.id);
            } else if (gestionPortefeuille.type === "RENOMMER") {
              await renommerPortefeuille(gestionPortefeuille.portefeuille.id, valeur);
              await charger(gestionPortefeuille.portefeuille.id);
            } else {
              await supprimerPortefeuille(gestionPortefeuille.portefeuille.id);
              localStorage.removeItem("portefeuille-actif");
              await charger(null);
            }
            setGestionPortefeuille(null);
          } catch (e) { setErreur(e.message); }
        }}
      />}
    </>
  );
}

function GestionPortefeuilleModal({ gestion, onClose, onValider }) {
  const suppression = gestion.type === "SUPPRIMER";
  const [valeur, setValeur] = useState(gestion.type === "RENOMMER" ? gestion.portefeuille?.nom ?? "" : "");
  const attendu = gestion.portefeuille?.nom ?? "";
  const valide = valeur.trim() && (!suppression || valeur.trim() === attendu);
  return <div className="modal-fond" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <section className="operation-modal" role="dialog" aria-modal="true">
      <button className="modal-fermer" onClick={onClose} aria-label="Fermer">×</button>
      <div className="operation-etiquette">Gestion du portefeuille</div>
      <h2>{gestion.type === "CREER" ? "Créer un portefeuille" : gestion.type === "RENOMMER" ? "Renommer le portefeuille" : "Supprimer le portefeuille"}</h2>
      {suppression && <p className="alerte">Cette action supprimera définitivement les positions, transactions et mouvements de trésorerie de <strong>{attendu}</strong>. Saisis son nom pour confirmer.</p>}
      <label className="champ"><span>{suppression ? `Saisir « ${attendu} »` : "Nom du portefeuille"}</span><input autoFocus value={valeur} onChange={(e) => setValeur(e.target.value)} /></label>
      <div className="modal-actions"><button className="btn-secondaire" onClick={onClose}>Annuler</button><button className={suppression ? "btn-vendre" : "btn"} disabled={!valide} onClick={() => onValider(valeur.trim())}>{suppression ? "Supprimer définitivement" : gestion.type === "CREER" ? "Créer" : "Enregistrer"}</button></div>
    </section>
  </div>;
}

function OperationModal({ operation, quantite, setQuantite, montant, setMontant, frais, setFrais, fiscalite, setFiscalite, solde, enCours, erreur, onClose, onSubmit }) {
  const { type, position } = operation;
  const estEspeces = type === "DEPOT" || type === "RETRAIT";
  const estVente = type === "VENTE";
  const cours = position?.cours_actuel ?? 0;
  const brut = estEspeces ? montant : quantite * cours;
  const fraisMontant = estEspeces ? 0 : brut * frais / 100;
  const totalAchat = brut + fraisMontant;
  const avantImpot = brut - fraisMontant;
  const gainTaxable = estVente ? Math.max(avantImpot - quantite * position.prix_achat, 0) : 0;
  const impot = gainTaxable * fiscalite / 100;
  const netVente = avantImpot - impot;
  const invalide = estEspeces
    ? montant <= 0 || (type === "RETRAIT" && montant > solde)
    : quantite <= 0 || !Number.isInteger(quantite) || (estVente && quantite > position.quantite) || (type === "AJOUT" && totalAchat > solde);
  const titres = { DEPOT: "Déposer des liquidités", RETRAIT: "Retirer des liquidités", AJOUT: `Ajouter des actions ${position?.symbole}`, VENTE: `Vendre des actions ${position?.symbole}` };
  const resultat = type === "DEPOT" ? solde + montant : type === "RETRAIT" ? solde - montant : estVente ? netVente : totalAchat;
  const libelleResultat = type === "DEPOT" ? "Nouveau solde" : type === "RETRAIT" ? "Solde restant" : estVente ? "Produit net estimé" : "Total à débiter";

  return <div className="modal-fond" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <section className="operation-modal" role="dialog" aria-modal="true" aria-labelledby="operation-titre">
      <button className="modal-fermer" onClick={onClose} aria-label="Fermer">×</button>
      <div className="operation-etiquette">Opération fictive · FCFA</div>
      <h2 id="operation-titre">{titres[type]}</h2>
      <p className="explication">Solde disponible : <strong>{formatFCFA(solde)}</strong></p>
      <form onSubmit={onSubmit}>
        {estEspeces ? <label className="champ"><span>Montant (FCFA)</span><input autoFocus type="number" min="1" step="1" value={montant} onChange={(e) => setMontant(Number(e.target.value))} /></label> : <>
          <div className="operation-cours"><span>Cours utilisé</span><strong>{formatFCFA(cours)}</strong></div>
          <label className="champ"><span>Quantité {estVente && `(maximum ${position.quantite})`}</span><input autoFocus type="number" min="1" max={estVente ? position.quantite : undefined} step="1" value={quantite} onChange={(e) => setQuantite(Number(e.target.value))} /></label>
          <label className="champ"><span>Frais de courtage (%)</span><input type="number" min="0" max="100" step="0.01" value={frais} onChange={(e) => setFrais(Number(e.target.value))} /></label>
          {estVente && <label className="champ"><span>Fiscalité sur la plus-value (%)</span><input type="number" min="0" max="100" step="0.01" value={fiscalite} onChange={(e) => setFiscalite(Number(e.target.value))} /></label>}
        </>}
        <div className="operation-recap"><span>{libelleResultat}</span><strong>{formatFCFA(resultat)}</strong>{!estEspeces && <small>dont {formatFCFA(fraisMontant)} de frais{estVente ? ` et ${formatFCFA(impot)} de fiscalité estimée` : ""}</small>}</div>
        {invalide && <p className="modal-erreur">{type === "RETRAIT" || type === "AJOUT" ? "Liquidités insuffisantes pour cette opération." : "Vérifie la quantité saisie."}</p>}
        {erreur && <p className="modal-erreur">{erreur}</p>}
        <div className="modal-actions"><button type="button" className="btn-secondaire" onClick={onClose}>Annuler</button><button className="btn" disabled={invalide || enCours}>{enCours ? "Enregistrement…" : type === "DEPOT" ? "Confirmer le dépôt" : type === "RETRAIT" ? "Confirmer le retrait" : estVente ? "Confirmer la vente" : "Confirmer l’achat"}</button></div>
      </form>
    </section>
  </div>;
}

function Repartition({ titre, donnees }) {
  return <div className="repartition-carte">
    <h3>{titre}</h3>
    <ResponsiveContainer width="100%" height={240}>
      <PieChart><Pie data={donnees} dataKey="valeur" nameKey="libelle" innerRadius={48} outerRadius={78} paddingAngle={2}>{donnees.map((d, i) => <Cell key={d.libelle} fill={COULEURS[i % COULEURS.length]} />)}</Pie><Tooltip formatter={(v) => formatFCFA(v)} /></PieChart>
    </ResponsiveContainer>
    <div className="legende-repartition">{donnees.map((d, i) => <div key={d.libelle}><span style={{ background: COULEURS[i % COULEURS.length] }} />{d.libelle}<strong>{d.pourcentage.toFixed(1)} %</strong></div>)}</div>
  </div>;
}
