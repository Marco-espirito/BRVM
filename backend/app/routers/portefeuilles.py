"""Routes de gestion des portefeuilles (creer/renommer/supprimer) et de la
watchlist. Le contenu d'un portefeuille (positions, especes) est dans trading."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import utilisateur_courant
from ..db import get_db
from ..models import (
    FavoriUtilisateur,
    MouvementEspeces,
    PortefeuilleUtilisateur,
    Societe,
    Transaction,
    Utilisateur,
)
from ..schemas import PortefeuilleUtilisateurIn, PortefeuilleUtilisateurOut
from ..services.portefeuille import selection_portefeuille

router = APIRouter(tags=["portefeuilles"])


@router.get("/mes-portefeuilles", response_model=list[PortefeuilleUtilisateurOut])
def mes_portefeuilles(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    return db.query(PortefeuilleUtilisateur).filter_by(utilisateur_id=utilisateur.id).order_by(PortefeuilleUtilisateur.cree_le).all()


@router.post("/mes-portefeuilles", response_model=PortefeuilleUtilisateurOut)
def creer_portefeuille(entree: PortefeuilleUtilisateurIn, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    if not entree.nom.strip(): raise HTTPException(status_code=400, detail="Nom requis")
    p = PortefeuilleUtilisateur(utilisateur_id=utilisateur.id, nom=entree.nom.strip())
    db.add(p); db.commit(); db.refresh(p); return p


@router.put("/mes-portefeuilles/{portefeuille_id}", response_model=PortefeuilleUtilisateurOut)
def renommer_portefeuille(portefeuille_id: int, entree: PortefeuilleUtilisateurIn,
                          utilisateur: Utilisateur = Depends(utilisateur_courant),
                          db: Session = Depends(get_db)):
    portefeuille = selection_portefeuille(db, utilisateur, portefeuille_id)
    nom = entree.nom.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Nom requis")
    portefeuille.nom = nom
    db.commit(); db.refresh(portefeuille)
    return portefeuille


@router.delete("/mes-portefeuilles/{portefeuille_id}")
def supprimer_portefeuille(portefeuille_id: int,
                           utilisateur: Utilisateur = Depends(utilisateur_courant),
                           db: Session = Depends(get_db)):
    portefeuille = selection_portefeuille(db, utilisateur, portefeuille_id)
    nombre = db.query(PortefeuilleUtilisateur).filter_by(utilisateur_id=utilisateur.id).count()
    if nombre <= 1:
        raise HTTPException(status_code=400, detail="Le dernier portefeuille ne peut pas être supprimé")
    db.query(Transaction).filter_by(portefeuille_id=portefeuille.id).delete()
    db.query(MouvementEspeces).filter_by(portefeuille_id=portefeuille.id).delete()
    db.delete(portefeuille)
    db.commit()
    return {"supprime": portefeuille_id}


@router.get("/watchlist", response_model=list[str])
def watchlist(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    return [f.symbole for f in db.query(FavoriUtilisateur).filter_by(utilisateur_id=utilisateur.id).all()]


@router.put("/watchlist/{symbole}")
def ajouter_favori(symbole: str, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    symbole = symbole.upper()
    if not db.get(Societe, symbole): raise HTTPException(status_code=404, detail="Action introuvable")
    if not db.query(FavoriUtilisateur).filter_by(utilisateur_id=utilisateur.id, symbole=symbole).first():
        db.add(FavoriUtilisateur(utilisateur_id=utilisateur.id, symbole=symbole)); db.commit()
    return {"ajoute": symbole}


@router.delete("/watchlist/{symbole}")
def retirer_favori(symbole: str, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    db.query(FavoriUtilisateur).filter_by(utilisateur_id=utilisateur.id, symbole=symbole.upper()).delete(); db.commit()
    return {"retire": symbole.upper()}
