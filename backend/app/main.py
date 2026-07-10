"""API FastAPI du BRVM Explorer.

Routes :
  GET /              -> petit message de sante
  POST /refresh      -> scrape la BRVM et enregistre les cotations du jour
  GET /actions       -> liste des actions avec leur dernier cours
  GET /actions/{sym} -> detail d'une action + historique (pour le graphique)
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import get_db
from .ingest import creer_tables, enregistrer_cotations, enregistrer_dividendes
from .models import Cotation, Detachement, Dividende, Position, Societe
from .schemas import (
    AchatIn,
    ActionDetailOut,
    ActionOut,
    CotationOut,
    DetachementOut,
    DividendeOut,
    PointValeur,
    PortefeuilleOut,
    PositionOut,
    TopActionOut,
)

app = FastAPI(title="BRVM Explorer", version="0.1.0")

# Le suffixe du symbole BRVM indique le pays d'origine de la societe :
# BOAC = BOA Cote d'Ivoire, BOAS = BOA Senegal, ONTBF = Onatel Burkina...
_PAYS_SUFFIXE = {
    "BF": "Burkina Faso",
    "C": "Côte d'Ivoire",
    "B": "Bénin",
    "S": "Sénégal",
    "M": "Mali",
    "N": "Niger",
    "T": "Togo",
}


def pays_depuis_symbole(symbole: str) -> str:
    if symbole.endswith("BF"):  # suffixe 2 lettres, a tester en premier
        return _PAYS_SUFFIXE["BF"]
    return _PAYS_SUFFIXE.get(symbole[-1], "Autre")


def classer_liquidite(volume_moyen: float | None) -> str | None:
    """Classement simple base sur le volume moyen quotidien echange."""
    if volume_moyen is None:
        return None
    if volume_moyen >= 1000:
        return "haute"
    if volume_moyen >= 100:
        return "moyenne"
    return "faible"

# Autorise le front React a appeler l'API. Vite prend 5173 par defaut mais
# bascule sur 5174/5175... si le port est occupe : on tolere tous les ports
# de localhost (app locale uniquement, aucun risque).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    creer_tables()


@app.get("/")
def racine():
    return {"message": "BRVM Explorer API. Voir /docs pour la documentation."}


@app.post("/refresh")
def refresh():
    """Declenche un scraping : cotations du jour + dividendes."""
    n = enregistrer_cotations()
    nb_hist, nb_proch = enregistrer_dividendes()
    return {
        "actions_enregistrees": n,
        "dividendes_historique": nb_hist,
        "detachements_a_venir": nb_proch,
    }


@app.get("/actions", response_model=list[ActionOut])
def liste_actions(db: Session = Depends(get_db)):
    """Toutes les actions avec leur cotation la plus recente."""
    # Pour chaque symbole, on cherche le jour le plus recent.
    dernier_jour = (
        db.query(Cotation.symbole, func.max(Cotation.jour).label("jour"))
        .group_by(Cotation.symbole)
        .subquery()
    )
    lignes = (
        db.query(Societe, Cotation)
        .join(Cotation, Cotation.symbole == Societe.symbole)
        .join(
            dernier_jour,
            (Cotation.symbole == dernier_jour.c.symbole)
            & (Cotation.jour == dernier_jour.c.jour),
        )
        .order_by(Societe.symbole)
        .all()
    )

    # Dernier dividende connu par societe (annee la plus recente avec montant)
    derniers_dividendes: dict[str, Dividende] = {}
    for d in db.query(Dividende).order_by(Dividende.annee).all():
        if d.montant is not None:
            derniers_dividendes[d.symbole] = d  # ecrase -> garde la + recente

    # Volume moyen par societe sur tout l'historique : plus l'historique
    # grandit, plus la mesure de liquidite devient fiable.
    volumes_moyens: dict[str, float] = {
        symbole: moyenne
        for symbole, moyenne in db.query(
            Cotation.symbole, func.avg(Cotation.volume)
        )
        .group_by(Cotation.symbole)
        .all()
        if moyenne is not None
    }

    resultat = []
    for s, c in lignes:
        div = derniers_dividendes.get(s.symbole)
        rendement = None
        if div is not None and c.cours_cloture:
            # Rendement recalcule sur le cours d'aujourd'hui, pas celui
            # de l'epoque du versement : c'est ce que TOI tu toucherais.
            rendement = round(div.montant / c.cours_cloture * 100, 2)
        resultat.append(
            ActionOut(
                symbole=s.symbole,
                nom=s.nom,
                cours_cloture=c.cours_cloture,
                variation=c.variation,
                volume=c.volume,
                dernier_jour=c.jour,
                dividende=div.montant if div else None,
                annee_dividende=div.annee if div else None,
                rendement=rendement,
                pays=pays_depuis_symbole(s.symbole),
                secteur=s.secteur,
                volume_moyen=volumes_moyens.get(s.symbole),
                liquidite=classer_liquidite(volumes_moyens.get(s.symbole)),
            )
        )
    return resultat


@app.get("/actions/{symbole}", response_model=ActionDetailOut)
def detail_action(symbole: str, db: Session = Depends(get_db)):
    """Detail d'une action + tout son historique de cours."""
    societe = db.get(Societe, symbole.upper())
    if societe is None:
        raise HTTPException(status_code=404, detail="Action introuvable")

    historique = (
        db.query(Cotation)
        .filter_by(symbole=societe.symbole)
        .order_by(Cotation.jour)
        .all()
    )
    dividendes = (
        db.query(Dividende)
        .filter_by(symbole=societe.symbole)
        .order_by(Dividende.annee.desc())
        .all()
    )
    detachement = db.get(Detachement, societe.symbole)

    return ActionDetailOut(
        symbole=societe.symbole,
        nom=societe.nom,
        historique=[CotationOut.model_validate(c) for c in historique],
        dividendes=[DividendeOut.model_validate(d) for d in dividendes],
        prochain_detachement=(
            DetachementOut.model_validate(detachement) if detachement else None
        ),
    )


def _tendance_dividendes(serie: list[Dividende]) -> str | None:
    """Qualifie l'evolution du dividende sur les annees connues."""
    montants = [d.montant for d in sorted(serie, key=lambda d: d.annee)]
    if len(montants) < 2:
        return None
    evolution = (montants[-1] - montants[0]) / montants[0] * 100
    jamais_baisse = all(b >= a for a, b in zip(montants, montants[1:]))
    if jamais_baisse and evolution > 5:
        return "hausse"
    if abs(evolution) <= 5:
        return "stable"
    if evolution < 0:
        return "baisse"
    return "irregulier"


@app.get("/top-actions", response_model=list[TopActionOut])
def top_actions(limit: int = 10, db: Session = Depends(get_db)):
    """Top 10 pedagogique pour un debutant 'rendement long terme'.

    Score sur 100, volontairement simple et transparent :
      - 40 pts : rendement du dividende (plafonne a 8 % ; un rendement > 15 %
        est suspect = dividende exceptionnel, peu de points)
      - 30 pts : liquidite (peut-on recuperer son argent facilement ?)
      - 30 pts : historique du dividende (regularite + tendance)

    Le top est DIVERSIFIE : d'abord la meilleure action de chaque secteur
    officiel BRVM, puis les meilleurs scores restants pour completer a 10.
    Ce n'est PAS un conseil d'investissement : c'est un filtre d'apprentissage.
    """
    actions = liste_actions(db)

    # Historique des dividendes par societe (pour la tendance)
    divs_par_symbole: dict[str, list[Dividende]] = {}
    for d in db.query(Dividende).filter(Dividende.montant.isnot(None)).all():
        divs_par_symbole.setdefault(d.symbole, []).append(d)

    resultats = []
    for a in actions:
        raisons: list[str] = []

        # --- Rendement (40 pts) ---
        if a.rendement is None:
            pts_rendement = 0.0
            raisons.append("Pas de dividende connu (0/40)")
        elif a.rendement > 15:
            pts_rendement = 10.0
            raisons.append(
                f"⚠️ Rendement {a.rendement:.1f} % : dividende probablement exceptionnel (10/40)"
            )
        else:
            pts_rendement = min(a.rendement, 8.0) / 8.0 * 40.0
            raisons.append(f"Rendement {a.rendement:.2f} % ({pts_rendement:.0f}/40)")

        # --- Liquidite (30 pts) ---
        pts_liquidite = {"haute": 30.0, "moyenne": 15.0, "faible": 0.0}.get(
            a.liquidite or "", 0.0
        )
        emoji = {"haute": "🟢", "moyenne": "🟡", "faible": "🔴"}.get(a.liquidite or "", "")
        raisons.append(f"Liquidité {a.liquidite or 'inconnue'} {emoji} ({pts_liquidite:.0f}/30)")

        # --- Historique du dividende (30 pts) ---
        serie = divs_par_symbole.get(a.symbole, [])
        tendance = _tendance_dividendes(serie)
        pts_regularite = min(len(serie), 4) / 4.0 * 10.0
        pts_tendance = {"hausse": 20.0, "stable": 14.0, "irregulier": 7.0, "baisse": 0.0}.get(
            tendance or "", 0.0
        )
        libelle = {
            "hausse": "en hausse régulière 🌱",
            "stable": "stable ⚖️",
            "irregulier": "irrégulier 🎢",
            "baisse": "en baisse 📉",
        }.get(tendance or "", "historique trop court")
        raisons.append(
            f"Dividende {libelle}, versé {len(serie)} année(s) ({pts_tendance + pts_regularite:.0f}/30)"
        )

        resultats.append(
            TopActionOut(
                rang=0,
                symbole=a.symbole,
                nom=a.nom,
                pays=a.pays,
                secteur=a.secteur,
                cours_cloture=a.cours_cloture,
                rendement=a.rendement,
                liquidite=a.liquidite,
                tendance_dividende=tendance,
                score=round(pts_rendement + pts_liquidite + pts_tendance + pts_regularite, 1),
                raisons=raisons,
            )
        )

    resultats.sort(key=lambda r: -r.score)

    # Diversification : la meilleure action de chaque secteur d'abord...
    top: list[TopActionOut] = []
    secteurs_pris: set[str] = set()
    for r in resultats:
        if r.secteur and r.secteur not in secteurs_pris:
            r.meilleur_du_secteur = True
            secteurs_pris.add(r.secteur)
            top.append(r)
    # ... puis les meilleurs scores restants pour completer.
    limit = max(1, min(limit, len(resultats)))
    for r in resultats:
        if len(top) >= limit:
            break
        if r not in top:
            top.append(r)

    top.sort(key=lambda r: -r.score)
    for i, r in enumerate(top[:limit], start=1):
        r.rang = i
    return top[:limit]


# --------------------------------------------------------------------------
# Portefeuille virtuel (paper trading) : achats FICTIFS au dernier cours
# connu, pour apprendre a suivre un portefeuille. Aucun ordre reel.
# --------------------------------------------------------------------------


def _dernier_cours(db: Session, symbole: str) -> Cotation | None:
    return (
        db.query(Cotation)
        .filter_by(symbole=symbole)
        .order_by(Cotation.jour.desc())
        .first()
    )


@app.post("/portefeuille/positions", response_model=PositionOut)
def acheter(achat: AchatIn, db: Session = Depends(get_db)):
    """Achat fictif : enregistre une position au dernier cours connu."""
    societe = db.get(Societe, achat.symbole.upper())
    if societe is None:
        raise HTTPException(status_code=404, detail="Action introuvable")
    if achat.quantite <= 0:
        raise HTTPException(status_code=400, detail="Quantité invalide")
    cotation = _dernier_cours(db, societe.symbole)
    if cotation is None or cotation.cours_cloture is None:
        raise HTTPException(status_code=400, detail="Pas de cours disponible")

    position = Position(
        symbole=societe.symbole,
        quantite=achat.quantite,
        prix_achat=cotation.cours_cloture,
        jour_achat=cotation.jour,
    )
    db.add(position)
    db.commit()
    db.refresh(position)
    return _position_out(db, position)


@app.delete("/portefeuille/positions/{position_id}")
def vendre(position_id: int, db: Session = Depends(get_db)):
    """Vente fictive : supprime la position du portefeuille."""
    position = db.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=404, detail="Position introuvable")
    db.delete(position)
    db.commit()
    return {"vendu": position_id}


def _position_out(db: Session, p: Position) -> PositionOut:
    societe = db.get(Societe, p.symbole)
    cotation = _dernier_cours(db, p.symbole)
    cours = cotation.cours_cloture if cotation else None
    investi = p.quantite * p.prix_achat
    valeur = p.quantite * cours if cours is not None else None

    dernier_div = (
        db.query(Dividende)
        .filter(Dividende.symbole == p.symbole, Dividende.montant.isnot(None))
        .order_by(Dividende.annee.desc())
        .first()
    )

    return PositionOut(
        id=p.id,
        symbole=p.symbole,
        nom=societe.nom if societe else p.symbole,
        quantite=p.quantite,
        prix_achat=p.prix_achat,
        jour_achat=p.jour_achat,
        cours_actuel=cours,
        investi=investi,
        valeur_actuelle=valeur,
        plus_value=valeur - investi if valeur is not None else None,
        plus_value_pct=(
            (valeur - investi) / investi * 100 if valeur is not None and investi else None
        ),
        dividende_annuel=(
            p.quantite * dernier_div.montant if dernier_div else None
        ),
    )


@app.get("/portefeuille", response_model=PortefeuilleOut)
def portefeuille(db: Session = Depends(get_db)):
    """Le portefeuille complet + sa valeur totale jour par jour."""
    positions = db.query(Position).order_by(Position.jour_achat).all()
    sorties = [_position_out(db, p) for p in positions]

    total_investi = sum(s.investi for s in sorties)
    valeur_totale = sum(s.valeur_actuelle or s.investi for s in sorties)
    plus_value = valeur_totale - total_investi
    dividendes_annuels = sum(s.dividende_annuel or 0 for s in sorties)

    # Valeur du portefeuille jour par jour : pour chaque jour de cotation
    # depuis le premier achat, somme (quantite x dernier cours connu) des
    # positions deja achetees ce jour-la.
    historique: list[PointValeur] = []
    if positions:
        symboles = {p.symbole for p in positions}
        cotations = (
            db.query(Cotation)
            .filter(Cotation.symbole.in_(symboles))
            .order_by(Cotation.jour)
            .all()
        )
        jours = sorted({c.jour for c in cotations})
        cours_du_jour: dict[tuple, float] = {
            (c.symbole, c.jour): c.cours_cloture
            for c in cotations
            if c.cours_cloture is not None
        }
        derniers: dict[str, float] = {}
        premier_achat = min(p.jour_achat for p in positions)
        for jour in jours:
            for s in symboles:
                if (s, jour) in cours_du_jour:
                    derniers[s] = cours_du_jour[(s, jour)]
            if jour < premier_achat:
                continue
            valeur_jour = sum(
                p.quantite * derniers.get(p.symbole, p.prix_achat)
                for p in positions
                if p.jour_achat <= jour
            )
            historique.append(PointValeur(jour=jour, valeur=valeur_jour))

    return PortefeuilleOut(
        positions=sorties,
        total_investi=total_investi,
        valeur_totale=valeur_totale,
        plus_value=plus_value,
        plus_value_pct=(plus_value / total_investi * 100) if total_investi else None,
        dividendes_annuels=dividendes_annuels,
        historique=historique,
    )
