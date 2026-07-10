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
from .models import Cotation, Detachement, Dividende, Societe
from .schemas import (
    ActionDetailOut,
    ActionOut,
    CotationOut,
    DetachementOut,
    DividendeOut,
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

# Autorise le front React (Vite tourne sur le port 5173) a appeler l'API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
