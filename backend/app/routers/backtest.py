"""Route du backtest : compare 3 strategies (rendement, score, diversification)
sur l'historique reellement collecte par l'application."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Cotation
from ..schemas import BacktestIn, BacktestOut
from ..services.backtest import candidats_backtest, simuler_backtest

router = APIRouter(tags=["backtest"])


@router.post("/backtest", response_model=BacktestOut)
def backtester(entree: BacktestIn, db: Session = Depends(get_db)):
    if entree.capital <= 0 or not 0 <= entree.frais_pct <= 100:
        raise HTTPException(status_code=400, detail="Capital ou frais invalides")
    taille = max(2, min(entree.taille_panier, 10))
    premiere = db.query(func.min(Cotation.jour)).scalar()
    derniere = db.query(func.max(Cotation.jour)).scalar()
    if not premiere or not derniere:
        raise HTTPException(status_code=400, detail="Aucun historique disponible")
    depart = db.query(func.min(Cotation.jour)).filter(Cotation.jour >= entree.date_depart).scalar()
    if depart is None or depart >= derniere:
        raise HTTPException(status_code=400, detail="La date doit précéder la dernière séance disponible")

    candidats = candidats_backtest(db, depart)
    if len(candidats) < 2:
        raise HTTPException(status_code=400, detail="Pas assez d'actions cotées à cette date")
    rendement = sorted(candidats, key=lambda c: -c["rendement"])[:taille]
    score = sorted(candidats, key=lambda c: -c["score"])[:taille]
    diversification = []
    secteurs = set()
    for c in sorted(candidats, key=lambda c: -c["score"]):
        secteur = c["secteur"] or "Non classé"
        if secteur not in secteurs:
            diversification.append(c); secteurs.add(secteur)
        if len(diversification) >= taille:
            break
    for c in sorted(candidats, key=lambda c: -c["score"]):
        if len(diversification) >= taille: break
        if c not in diversification: diversification.append(c)

    definitions = [
        ("Rendement", "Meilleurs rendements estimés à la date de départ", rendement),
        ("Score", "Rendement, liquidité et historique du dividende", score),
        ("Diversification", "Meilleur score de chaque secteur avant complément", diversification),
    ]
    lignes = [simuler_backtest(db, nom, description, panier, depart, derniere,
                               entree.capital, entree.frais_pct)
              for nom, description, panier in definitions]
    return BacktestOut(
        date_depart_demandee=entree.date_depart, date_depart_effective=depart,
        date_fin=derniere, historique_disponible_depuis=premiere, strategies=lignes,
        limites=[
            "L'historique commence seulement à la première date collectée par l'application.",
            "Les dividendes sont rattachés à leur exercice, faute de date historique exacte de paiement.",
            "Les achats et la vente finale utilisent les cours de clôture, sans carnet d'ordres ni glissement.",
            "Les stratégies n'utilisent que les dividendes antérieurs au départ, mais les résultats passés ne prédisent pas les résultats futurs.",
        ],
    )
