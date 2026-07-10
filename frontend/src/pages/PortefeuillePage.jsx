import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import {
  getActions,
  getPortefeuille,
  getTopActions,
  acheterPosition,
  vendrePosition,
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

export default function PortefeuillePage() {
  const [portefeuille, setPortefeuille] = useState(null);
  const [actions, setActions] = useState([]);
  const [top, setTop] = useState([]);
  const [erreur, setErreur] = useState(null);
  const [symbole, setSymbole] = useState("");
  const [quantite, setQuantite] = useState(10);
  const [enCours, setEnCours] = useState(false);

  async function charger() {
    try {
      const [p, a, t] = await Promise.all([
        getPortefeuille(),
        getActions(),
        getTopActions(),
      ]);
      setPortefeuille(p);
      setActions(a);
      setTop(t);
      if (!symbole && a.length) setSymbole(a[0].symbole);
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

  async function acheter(e) {
    e.preventDefault();
    if (!symbole || quantite <= 0) return;
    setEnCours(true);
    setErreur(null);
    try {
      await acheterPosition(symbole, quantite);
      await charger();
    } catch (e2) {
      setErreur(e2.message);
    } finally {
      setEnCours(false);
    }
  }

  async function vendre(position) {
    if (
      !window.confirm(
        `Vendre (fictivement) tes ${position.quantite} actions ${position.symbole} ?`
      )
    )
      return;
    await vendrePosition(position.id);
    await charger();
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
  const gain = portefeuille.plus_value;

  return (
    <>
      <h1>💼 Mon portefeuille virtuel</h1>
      <p className="explication" style={{ marginBottom: 16 }}>
        Achète des actions <strong>fictivement</strong> au cours du jour, comme
        si c'était réel : ton portefeuille évolue ensuite avec les vrais cours
        de la BRVM, jour après jour. Zéro risque, 100 % apprentissage — aucun
        ordre réel n'est passé.
      </p>

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
        <div className="champ">
          <span>&nbsp;</span>
          <button className="btn" disabled={enCours || !coutEstime}>
            {enCours
              ? "⏳…"
              : coutEstime
              ? `🛒 Acheter (${formatEUR(enEuros(coutEstime))})`
              : "🛒 Acheter"}
          </button>
        </div>
      </form>
      {erreur && <p className="info erreur">{erreur}</p>}

      {positions.length === 0 ? (
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
              <div className="carte-titre">💸 Total investi</div>
              <div className="carte-valeur">{formatFCFA(portefeuille.total_investi)}</div>
              <div className="carte-sous">≈ {formatEUR(enEuros(portefeuille.total_investi))}</div>
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
                {formatEUR(enEuros(gain))}
              </div>
              <div className="carte-detail">
                {portefeuille.plus_value_pct != null &&
                  `${gain >= 0 ? "+" : ""}${portefeuille.plus_value_pct.toFixed(2)} % — compte seulement si tu vends !`}
              </div>
            </div>
            <div className="carte">
              <div className="carte-titre">💰 Dividendes annuels estimés</div>
              <div className="carte-valeur hausse">
                {formatEUR(enEuros(portefeuille.dividendes_annuels))}
              </div>
              <div className="carte-detail">avant impôts, au rythme actuel des sociétés</div>
            </div>
          </div>

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

          {/* Tableau des positions */}
          <h2>Mes positions</h2>
          <table className="tableau">
            <thead>
              <tr>
                <th>Action</th>
                <th className="num">Qté</th>
                <th className="num" title="Cours au moment de ton achat fictif">Prix d'achat</th>
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
                  <td className="num">{formatEUR(enEuros(p.investi))}</td>
                  <td className="num">{formatEUR(enEuros(p.valeur_actuelle))}</td>
                  <td
                    className={
                      "num " +
                      (p.plus_value > 0 ? "hausse" : p.plus_value < 0 ? "baisse" : "")
                    }
                  >
                    {p.plus_value != null
                      ? `${p.plus_value >= 0 ? "+" : ""}${formatEUR(enEuros(p.plus_value))} (${p.plus_value_pct >= 0 ? "+" : ""}${p.plus_value_pct.toFixed(2)}%)`
                      : "-"}
                  </td>
                  <td className="num hausse">
                    {p.dividende_annuel != null
                      ? formatEUR(enEuros(p.dividende_annuel))
                      : "-"}
                  </td>
                  <td>
                    <button className="btn-vendre" onClick={() => vendre(p)}>
                      Vendre
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="explication">
            💡 Règle du jeu : les achats se font au dernier cours de clôture
            connu, sans frais de courtage (dans la vraie vie, une SGI prendrait
            ~1 %). « Vendre » retire simplement la ligne — l'app ne garde pas
            (encore) l'historique des ventes.
          </p>
        </>
      )}
    </>
  );
}
