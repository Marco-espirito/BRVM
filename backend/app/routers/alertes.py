"""Routes des alertes (creer/lister/supprimer/evaluer) et rafraichissement
manuel des donnees (reserve a l'administrateur)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..alertes import TYPES, TYPES_SEUIL, evaluer_alertes, initialiser_alerte
from ..auth import utilisateur_courant
from ..db import SessionLocal, get_db
from ..ingest import (
    enregistrer_cotations,
    enregistrer_dividendes,
    enregistrer_indices,
)
from ..models import Alerte, EvenementAlerte, Societe, Utilisateur
from ..schemas import AlerteIn, AlerteOut, EvenementAlerteOut

router = APIRouter(tags=["alertes"])


@router.post("/refresh")
def refresh(utilisateur: Utilisateur = Depends(utilisateur_courant)):
    """Declenche un scraping : cotations du jour + dividendes."""
    administrateurs = {e.strip().lower() for e in os.getenv("BRVM_ADMIN_EMAILS", "").split(",") if e.strip()}
    if os.getenv("BRVM_ALLOW_USER_REFRESH", "0") != "1" and utilisateur.email not in administrateurs:
        raise HTTPException(status_code=403, detail="Rafraîchissement réservé à l'administrateur")
    n = enregistrer_cotations()
    nb_indices = enregistrer_indices()
    nb_hist, nb_proch = enregistrer_dividendes()
    db = SessionLocal()
    try:
        nb_alertes = len(evaluer_alertes(db))
    finally:
        db.close()
    return {
        "actions_enregistrees": n,
        "indices_enregistres": nb_indices,
        "dividendes_historique": nb_hist,
        "detachements_a_venir": nb_proch,
        "alertes_declenchees": nb_alertes,
    }


@router.get("/alertes", response_model=list[AlerteOut])
def liste_alertes(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    return db.query(Alerte).filter_by(utilisateur_id=utilisateur.id).order_by(Alerte.creee_le.desc()).all()


@router.post("/alertes", response_model=AlerteOut)
def creer_alerte(entree: AlerteIn, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    symbole = entree.symbole.upper()
    if db.get(Societe, symbole) is None:
        raise HTTPException(status_code=404, detail="Action introuvable")
    if entree.type not in TYPES:
        raise HTTPException(status_code=400, detail="Type d'alerte invalide")
    if entree.type in TYPES_SEUIL and (entree.seuil is None or entree.seuil <= 0):
        raise HTTPException(status_code=400, detail="Seuil positif requis")
    if entree.email and ("@" not in entree.email or len(entree.email) > 254):
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide")
    alerte = Alerte(symbole=symbole, type=entree.type, seuil=entree.seuil,
                    email=entree.email.strip() if entree.email else None, active=True,
                    utilisateur_id=utilisateur.id)
    db.add(alerte)
    db.flush()
    initialiser_alerte(db, alerte)
    db.commit()
    db.refresh(alerte)
    return alerte


@router.delete("/alertes/{alerte_id}")
def supprimer_alerte(alerte_id: int, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    alerte = db.query(Alerte).filter_by(id=alerte_id, utilisateur_id=utilisateur.id).first()
    if alerte is None:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    db.query(EvenementAlerte).filter_by(alerte_id=alerte_id).delete()
    db.delete(alerte)
    db.commit()
    return {"supprimee": alerte_id}


@router.post("/alertes/evaluer", response_model=list[EvenementAlerteOut])
def verifier_alertes(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    evaluer_alertes(db, utilisateur.id)
    return (db.query(EvenementAlerte).join(Alerte, Alerte.id == EvenementAlerte.alerte_id)
            .filter(Alerte.utilisateur_id == utilisateur.id, EvenementAlerte.lue.is_(False))
            .order_by(EvenementAlerte.cree_le).all())


@router.post("/alertes/evenements/{evenement_id}/lire")
def marquer_evenement_lu(evenement_id: int, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    evenement = (db.query(EvenementAlerte).join(Alerte, Alerte.id == EvenementAlerte.alerte_id)
                 .filter(EvenementAlerte.id == evenement_id, Alerte.utilisateur_id == utilisateur.id).first())
    if evenement is None:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    evenement.lue = True
    db.commit()
    return {"lue": evenement_id}
