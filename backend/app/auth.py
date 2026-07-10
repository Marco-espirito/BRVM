"""Authentification locale par mot de passe et session opaque HttpOnly."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .db import get_db
from .models import SessionUtilisateur, Utilisateur

COOKIE = "brvm_session"
ITERATIONS = 600_000


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hacher_mot_de_passe(mot_de_passe: str, sel_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), bytes.fromhex(sel_hex), ITERATIONS).hex()


def verifier_mot_de_passe(mot_de_passe: str, utilisateur: Utilisateur) -> bool:
    return hmac.compare_digest(hacher_mot_de_passe(mot_de_passe, utilisateur.sel), utilisateur.mot_de_passe_hash)


def creer_session(db: Session, utilisateur: Utilisateur, response: Response) -> None:
    db.query(SessionUtilisateur).filter(SessionUtilisateur.expire_le < _utcnow()).delete()
    jeton = secrets.token_urlsafe(32)
    expiration = _utcnow() + timedelta(days=30)
    db.add(SessionUtilisateur(utilisateur_id=utilisateur.id,
                              jeton_hash=hashlib.sha256(jeton.encode()).hexdigest(),
                              expire_le=expiration))
    db.commit()
    response.set_cookie(COOKIE, jeton, max_age=30 * 24 * 3600, httponly=True,
                        secure=os.getenv("COOKIE_SECURE", "0") == "1",
                        samesite="lax", path="/")


def supprimer_session(db: Session, jeton: str | None, response: Response) -> None:
    if jeton:
        db.query(SessionUtilisateur).filter_by(
            jeton_hash=hashlib.sha256(jeton.encode()).hexdigest()).delete()
        db.commit()
    response.delete_cookie(COOKIE, path="/")


def utilisateur_courant(brvm_session: str | None = Cookie(default=None),
                        db: Session = Depends(get_db)) -> Utilisateur:
    if not brvm_session:
        raise HTTPException(status_code=401, detail="Authentification requise")
    ligne = db.query(SessionUtilisateur).filter_by(
        jeton_hash=hashlib.sha256(brvm_session.encode()).hexdigest()).first()
    if not ligne or ligne.expire_le < _utcnow():
        raise HTTPException(status_code=401, detail="Session expirée")
    utilisateur = db.get(Utilisateur, ligne.utilisateur_id)
    if not utilisateur:
        raise HTTPException(status_code=401, detail="Compte introuvable")
    return utilisateur
