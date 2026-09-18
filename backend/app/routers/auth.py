"""Routes d'authentification : inscription, connexion (avec anti-bruteforce),
deconnexion, profil et changement de mot de passe."""
from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import time
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..auth import (
    creer_session,
    hacher_mot_de_passe,
    supprimer_session,
    utilisateur_courant,
    verifier_mot_de_passe,
)
from ..db import get_db
from ..models import (
    Alerte,
    PortefeuilleUtilisateur,
    ReinitialisationMotDePasse,
    SessionUtilisateur,
    Transaction,
    Utilisateur,
    utcnow,
)
from ..schemas import (
    ChangementMotDePasseIn,
    CompteIn,
    ConnexionIn,
    DemandeReinitialisationIn,
    ProfilIn,
    ReinitialisationMotDePasseIn,
    UtilisateurOut,
)

router = APIRouter(tags=["auth"])

# email -> horodatages des echecs recents (fenetre glissante anti-bruteforce)
_ECHECS_CONNEXION: dict[str, list[float]] = {}


def _envoyer_lien_reinitialisation(destinataire: str, lien: str) -> bool:
    from ..alertes import envoyer_email

    message = (
        "Une réinitialisation du mot de passe BRVM Explorer a été demandée.\n\n"
        f"Choisis un nouveau mot de passe ici : {lien}\n\n"
        "Ce lien expire dans 30 minutes et ne peut être utilisé qu'une fois. "
        "Ignore ce message si tu n'es pas à l'origine de la demande."
    )
    return envoyer_email(destinataire, "Réinitialisation du mot de passe", message)


@router.post("/auth/inscription", response_model=UtilisateurOut)
def inscription(entree: CompteIn, response: Response, db: Session = Depends(get_db)):
    email = entree.email.strip().lower()
    if "@" not in email or not 10 <= len(entree.mot_de_passe) <= 128:
        raise HTTPException(status_code=400, detail="E-mail invalide ou mot de passe inférieur à 10 caractères")
    if db.query(Utilisateur).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Ce compte existe déjà")
    sel = secrets.token_hex(16)
    utilisateur = Utilisateur(email=email, nom=entree.nom.strip() or "Investisseur",
                              sel=sel, mot_de_passe_hash=hacher_mot_de_passe(entree.mot_de_passe, sel))
    db.add(utilisateur); db.flush()
    portefeuille = PortefeuilleUtilisateur(utilisateur_id=utilisateur.id, nom="Mon portefeuille")
    db.add(portefeuille); db.flush()
    # Le premier compte local recupere les transactions historiques non attribuees.
    if os.getenv("BRVM_CLAIM_LEGACY_DATA", "0") == "1" and db.query(Utilisateur).count() == 1:
        db.query(Transaction).filter(Transaction.portefeuille_id.is_(None)).update({"portefeuille_id": portefeuille.id})
        db.query(Alerte).filter(Alerte.utilisateur_id.is_(None)).update({"utilisateur_id": utilisateur.id})
    db.commit(); creer_session(db, utilisateur, response)
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@router.post("/auth/connexion", response_model=UtilisateurOut)
def connexion(entree: ConnexionIn, response: Response, db: Session = Depends(get_db)):
    if not 1 <= len(entree.mot_de_passe) <= 128:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    email = entree.email.strip().lower()
    maintenant = time.monotonic()
    echecs = [instant for instant in _ECHECS_CONNEXION.get(email, []) if maintenant - instant < 900]
    _ECHECS_CONNEXION[email] = echecs
    if len(echecs) >= 5:
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessaie dans 15 minutes.")
    utilisateur = db.query(Utilisateur).filter_by(email=email).first()
    if utilisateur is None:
        hacher_mot_de_passe(entree.mot_de_passe, "00" * 16)
        echecs.append(maintenant)
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    if not verifier_mot_de_passe(entree.mot_de_passe, utilisateur):
        echecs.append(maintenant)
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    _ECHECS_CONNEXION.pop(email, None)
    creer_session(db, utilisateur, response)
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@router.post("/auth/mot-de-passe-oublie")
def demander_reinitialisation(entree: DemandeReinitialisationIn,
                              db: Session = Depends(get_db)):
    """Réponse identique pour tous les e-mails afin d'empêcher leur énumération."""
    email = entree.email.strip().lower()
    utilisateur = db.query(Utilisateur).filter_by(email=email).first()
    reponse = {"message": "Si ce compte existe, un lien de réinitialisation a été envoyé."}
    if utilisateur is None:
        return reponse

    maintenant = utcnow()
    db.query(ReinitialisationMotDePasse).filter(
        ReinitialisationMotDePasse.utilisateur_id == utilisateur.id,
        ReinitialisationMotDePasse.utilise_le.is_(None),
    ).delete(synchronize_session=False)
    jeton = secrets.token_urlsafe(32)
    db.add(ReinitialisationMotDePasse(
        utilisateur_id=utilisateur.id,
        jeton_hash=hashlib.sha256(jeton.encode()).hexdigest(),
        expire_le=maintenant + timedelta(minutes=30),
    ))
    db.commit()
    base_frontend = os.getenv("BRVM_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    lien = f"{base_frontend}/?reset_token={quote(jeton)}"
    envoye = False
    try:
        envoye = _envoyer_lien_reinitialisation(utilisateur.email, lien)
    except (OSError, smtplib.SMTPException):
        pass
    if not envoye and os.getenv("BRVM_ALLOW_DEV_RESET_LINK", "0") == "1":
        reponse["lien_developpement"] = lien
    return reponse


@router.post("/auth/reinitialiser-mot-de-passe")
def reinitialiser_mot_de_passe(entree: ReinitialisationMotDePasseIn,
                               db: Session = Depends(get_db)):
    if not 10 <= len(entree.nouveau_mot_de_passe) <= 128:
        raise HTTPException(status_code=400, detail="Le mot de passe doit contenir au moins 10 caractères")
    jeton_hash = hashlib.sha256(entree.jeton.encode()).hexdigest()
    demande = db.query(ReinitialisationMotDePasse).filter_by(
        jeton_hash=jeton_hash, utilise_le=None
    ).first()
    maintenant = utcnow()
    if demande is None or demande.expire_le <= maintenant:
        raise HTTPException(status_code=400, detail="Ce lien est invalide ou a expiré")
    utilisateur = db.get(Utilisateur, demande.utilisateur_id)
    if utilisateur is None:
        raise HTTPException(status_code=400, detail="Ce lien est invalide ou a expiré")
    utilisateur.sel = secrets.token_hex(16)
    utilisateur.mot_de_passe_hash = hacher_mot_de_passe(
        entree.nouveau_mot_de_passe, utilisateur.sel
    )
    demande.utilise_le = maintenant
    db.query(SessionUtilisateur).filter_by(utilisateur_id=utilisateur.id).delete(
        synchronize_session=False
    )
    db.commit()
    return {"modifie": True, "message": "Mot de passe modifié. Tu peux maintenant te connecter."}


@router.post("/auth/deconnexion")
def deconnexion(response: Response, utilisateur: Utilisateur = Depends(utilisateur_courant),
                brvm_session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    supprimer_session(db, brvm_session, response)
    return {"deconnecte": True}


@router.get("/auth/moi", response_model=UtilisateurOut)
def moi(utilisateur: Utilisateur = Depends(utilisateur_courant)):
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@router.put("/auth/profil", response_model=UtilisateurOut)
def modifier_profil(entree: ProfilIn,
                    utilisateur: Utilisateur = Depends(utilisateur_courant),
                    db: Session = Depends(get_db)):
    nom = entree.nom.strip()
    if not nom or len(nom) > 100:
        raise HTTPException(status_code=400, detail="Nom invalide")
    utilisateur.nom = nom
    db.commit(); db.refresh(utilisateur)
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@router.post("/auth/mot-de-passe")
def changer_mot_de_passe(entree: ChangementMotDePasseIn,
                         utilisateur: Utilisateur = Depends(utilisateur_courant),
                         brvm_session: str | None = Cookie(default=None),
                         db: Session = Depends(get_db)):
    if not verifier_mot_de_passe(entree.mot_de_passe_actuel, utilisateur):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if not 10 <= len(entree.nouveau_mot_de_passe) <= 128:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit contenir au moins 10 caractères")
    utilisateur.sel = secrets.token_hex(16)
    utilisateur.mot_de_passe_hash = hacher_mot_de_passe(entree.nouveau_mot_de_passe, utilisateur.sel)
    jeton_courant = hashlib.sha256(brvm_session.encode()).hexdigest() if brvm_session else None
    requete = db.query(SessionUtilisateur).filter_by(utilisateur_id=utilisateur.id)
    if jeton_courant:
        requete = requete.filter(SessionUtilisateur.jeton_hash != jeton_courant)
    requete.delete(synchronize_session=False)
    db.commit()
    return {"modifie": True, "autres_sessions_revoquees": True}
