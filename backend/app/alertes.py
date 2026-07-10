"""Evaluation des alertes et envoi optionnel par SMTP."""
from __future__ import annotations

import os
import smtplib
from datetime import date, datetime
from email.message import EmailMessage

from sqlalchemy.orm import Session

from .models import Alerte, Cotation, Detachement, Dividende, EvenementAlerte

TYPES_SEUIL = {"cours_superieur", "cours_inferieur", "rendement_superieur", "rappel_detachement"}
TYPES = TYPES_SEUIL | {"nouveau_dividende", "detachement"}


def etat_courant(db: Session, alerte: Alerte) -> tuple[str, str | None, str | None]:
    cotation = db.query(Cotation).filter_by(symbole=alerte.symbole).order_by(Cotation.jour.desc()).first()
    dividende = db.query(Dividende).filter(
        Dividende.symbole == alerte.symbole, Dividende.montant.isnot(None)
    ).order_by(Dividende.annee.desc()).first()
    if alerte.type == "cours_superieur":
        actif = bool(cotation and cotation.cours_cloture is not None and cotation.cours_cloture >= alerte.seuil)
        return str(actif), f"Cours de {alerte.symbole} au-dessus de {alerte.seuil:,.0f} FCFA", f"Dernier cours : {cotation.cours_cloture:,.0f} FCFA" if actif else None
    if alerte.type == "cours_inferieur":
        actif = bool(cotation and cotation.cours_cloture is not None and cotation.cours_cloture <= alerte.seuil)
        return str(actif), f"Cours de {alerte.symbole} sous {alerte.seuil:,.0f} FCFA", f"Dernier cours : {cotation.cours_cloture:,.0f} FCFA" if actif else None
    if alerte.type == "rendement_superieur":
        rendement = (dividende.montant / cotation.cours_cloture * 100) if dividende and cotation and cotation.cours_cloture else None
        actif = rendement is not None and rendement >= alerte.seuil
        return str(actif), f"Rendement de {alerte.symbole} supérieur à {alerte.seuil:.2f} %", f"Rendement estimé : {rendement:.2f} %" if actif else None
    if alerte.type == "rappel_detachement":
        detachement = db.get(Detachement, alerte.symbole)
        try:
            jour = datetime.strptime(detachement.date_detachement, "%d/%m/%Y").date() if detachement else None
        except ValueError:
            jour = None
        restant = (jour - date.today()).days if jour else None
        actif = restant is not None and 0 <= restant <= alerte.seuil
        return str(actif), f"Détachement proche pour {alerte.symbole}", f"Détachement dans {restant} jour(s), le {detachement.date_detachement}" if actif else None
    if alerte.type == "nouveau_dividende":
        signature = f"{dividende.annee}:{dividende.montant}" if dividende else "aucun"
        return signature, f"Nouveau dividende pour {alerte.symbole}", f"{dividende.montant:,.0f} FCFA par action au titre de {dividende.annee}" if dividende else None
    detachement = db.get(Detachement, alerte.symbole)
    signature = f"{detachement.date_detachement}:{detachement.montant}" if detachement else "aucun"
    return signature, f"Détachement annoncé pour {alerte.symbole}", f"Date : {detachement.date_detachement} — {detachement.montant or 0:,.0f} FCFA par action" if detachement else None


def initialiser_alerte(db: Session, alerte: Alerte) -> None:
    etat, _, _ = etat_courant(db, alerte)
    alerte.etat = "False" if alerte.type in TYPES_SEUIL else etat


def evaluer_alertes(db: Session, utilisateur_id: int | None = None) -> list[EvenementAlerte]:
    nouveaux = []
    requete = db.query(Alerte).filter_by(active=True)
    if utilisateur_id is not None:
        requete = requete.filter_by(utilisateur_id=utilisateur_id)
    for alerte in requete.all():
        etat, titre, message = etat_courant(db, alerte)
        declenche = (etat == "True" and alerte.etat != "True") if alerte.type in TYPES_SEUIL else (alerte.etat is not None and etat != alerte.etat and etat != "aucun")
        if declenche and message:
            evenement = EvenementAlerte(alerte_id=alerte.id, titre=titre, message=message)
            db.add(evenement)
            db.flush()
            nouveaux.append(evenement)
            if alerte.email:
                try:
                    envoyer_email(alerte.email, titre, message)
                except (OSError, smtplib.SMTPException):
                    # L'evenement reste disponible dans le navigateur meme si
                    # le serveur SMTP est temporairement indisponible.
                    pass
        alerte.etat = etat
    db.commit()
    return nouveaux


def envoyer_email(destinataire: str, titre: str, message: str) -> bool:
    host = os.getenv("SMTP_HOST")
    expediteur = os.getenv("SMTP_FROM")
    if not host or not expediteur:
        return False
    courriel = EmailMessage()
    courriel["Subject"] = f"BRVM Explorer — {titre}"
    courriel["From"] = expediteur
    courriel["To"] = destinataire
    courriel.set_content(message)
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if os.getenv("SMTP_TLS", "1") == "1":
            smtp.starttls()
        utilisateur = os.getenv("SMTP_USER")
        if utilisateur:
            smtp.login(utilisateur, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(courriel)
    return True
