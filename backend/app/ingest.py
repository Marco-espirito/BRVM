"""Recupere les cotations et les enregistre en base (upsert par jour)."""
from __future__ import annotations

import os
from datetime import date

from sqlalchemy import text

from .db import Base, SessionLocal, engine
from .models import (Alerte, Cotation, Detachement, Dividende, IndiceCotation,
                     PortefeuilleUtilisateur, Position, Societe, Transaction, Utilisateur)
from .scraper.brvm import fetch_cotations_et_date
from .scraper.indices import fetch_indices
from .scraper.dividendes import fetch_dividendes
from .scraper.secteurs import fetch_secteurs


def creer_tables() -> None:
    """Cree les tables si elles n'existent pas encore (+ mini-migrations)."""
    Base.metadata.create_all(bind=engine)
    # create_all n'ajoute pas les colonnes aux tables existantes : on
    # ajoute 'secteur' a la main si la base date d'avant cette colonne.
    with engine.connect() as conn:
        colonnes = [
            ligne[1]
            for ligne in conn.execute(text("PRAGMA table_info(societes)"))
        ]
        if "secteur" not in colonnes:
            conn.execute(text("ALTER TABLE societes ADD COLUMN secteur VARCHAR"))
            conn.commit()
        colonnes_transactions = [ligne[1] for ligne in conn.execute(text("PRAGMA table_info(transactions)"))]
        if colonnes_transactions and "portefeuille_id" not in colonnes_transactions:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN portefeuille_id INTEGER"))
            conn.commit()
        colonnes_alertes = [ligne[1] for ligne in conn.execute(text("PRAGMA table_info(alertes)"))]
        if colonnes_alertes and "utilisateur_id" not in colonnes_alertes:
            conn.execute(text("ALTER TABLE alertes ADD COLUMN utilisateur_id INTEGER"))
            conn.commit()
        colonnes_portefeuilles = [ligne[1] for ligne in conn.execute(text("PRAGMA table_info(portefeuilles_utilisateur)"))]
        if colonnes_portefeuilles and "solde_especes" not in colonnes_portefeuilles:
            conn.execute(text("ALTER TABLE portefeuilles_utilisateur ADD COLUMN solde_especes FLOAT NOT NULL DEFAULT 0"))
            conn.commit()
        colonnes_mouvements = [ligne[1] for ligne in conn.execute(text("PRAGMA table_info(mouvements_especes)"))]
        if colonnes_mouvements and "solde_apres" not in colonnes_mouvements:
            conn.execute(text("ALTER TABLE mouvements_especes ADD COLUMN solde_apres FLOAT"))
            conn.commit()
    db = SessionLocal()
    try:
        if db.query(Transaction).count() == 0:
            for p in db.query(Position).all():
                brut = p.quantite * p.prix_achat
                db.add(Transaction(symbole=p.symbole, type="ACHAT", quantite=p.quantite,
                                   prix=p.prix_achat, jour=p.jour_achat,
                                   frais_courtage=0, fiscalite=0, montant_net=brut))
            db.commit()
        if os.getenv("BRVM_CLAIM_LEGACY_DATA", "0") == "1" and db.query(Utilisateur).count() == 1:
            utilisateur = db.query(Utilisateur).one()
            portefeuille = db.query(PortefeuilleUtilisateur).filter_by(
                utilisateur_id=utilisateur.id).order_by(PortefeuilleUtilisateur.cree_le).first()
            if portefeuille:
                db.query(Transaction).filter(Transaction.portefeuille_id.is_(None)).update(
                    {"portefeuille_id": portefeuille.id})
            db.query(Alerte).filter(Alerte.utilisateur_id.is_(None)).update(
                {"utilisateur_id": utilisateur.id})
            db.commit()
    finally:
        db.close()


def enregistrer_cotations() -> int:
    """Scrape la BRVM et enregistre les cotations d'aujourd'hui."""
    actions, jour_marche = fetch_cotations_et_date()
    return stocker_cotations(actions, jour_marche)


def enregistrer_indices() -> int:
    return stocker_indices(fetch_indices(), date.today())


def stocker_indices(indices: list[dict], jour: date) -> int:
    creer_tables()
    db = SessionLocal()
    try:
        for valeur in indices:
            ligne = db.query(IndiceCotation).filter_by(
                code=valeur["code"], jour=jour
            ).one_or_none()
            if ligne is None:
                ligne = IndiceCotation(code=valeur["code"], jour=jour,
                                       cloture=valeur["cloture"])
                db.add(ligne)
            ligne.cloture = valeur["cloture"]
            ligne.variation = valeur.get("variation")
        db.commit()
        return len(indices)
    finally:
        db.close()


def stocker_cotations(actions: list[dict], jour: date) -> int:
    """Enregistre des cotations pour un jour donne (upsert : idempotent).

    Utilise par le scraping direct ET par l'import des donnees JSON
    produites par le cron GitHub Actions.
    """
    creer_tables()
    aujourdhui = jour

    db = SessionLocal()
    try:
        for a in actions:
            # 1) societe (cree si nouvelle, sinon met le nom a jour)
            societe = db.get(Societe, a["symbole"])
            if societe is None:
                societe = Societe(symbole=a["symbole"], nom=a["nom"])
                db.add(societe)
            else:
                societe.nom = a["nom"]

            # 2) cotation du jour (upsert)
            cotation = (
                db.query(Cotation)
                .filter_by(symbole=a["symbole"], jour=aujourdhui)
                .one_or_none()
            )
            if cotation is None:
                cotation = Cotation(symbole=a["symbole"], jour=aujourdhui)
                db.add(cotation)

            cotation.volume = a["volume"]
            cotation.cours_veille = a["cours_veille"]
            cotation.cours_ouverture = a["cours_ouverture"]
            cotation.cours_cloture = a["cours_cloture"]
            cotation.variation = a["variation"]

        db.commit()
        return len(actions)
    finally:
        db.close()


def enregistrer_secteurs() -> int:
    """Scrape les 7 pages sectorielles BRVM et met a jour les societes."""
    return stocker_secteurs(fetch_secteurs())


def stocker_secteurs(mapping: dict[str, str]) -> int:
    """Applique un mapping symbole -> secteur aux societes connues."""
    creer_tables()
    db = SessionLocal()
    try:
        nb = 0
        for societe in db.query(Societe).all():
            secteur = mapping.get(societe.symbole)
            if secteur:
                societe.secteur = secteur
                nb += 1
        db.commit()
        return nb
    finally:
        db.close()


def enregistrer_dividendes() -> tuple[int, int]:
    """Scrape Sika Finance et enregistre dividendes + detachements."""
    historique, prochains = fetch_dividendes()
    return stocker_dividendes(historique, prochains)


def stocker_dividendes(
    historique: list[dict], prochains: list[dict]
) -> tuple[int, int]:
    """Enregistre dividendes + prochains detachements (upsert).

    Retourne (nb lignes historique, nb detachements). On ne garde que les
    societes deja connues en base (celles cotees a la BRVM).
    """
    creer_tables()

    db = SessionLocal()
    try:
        symboles_connus = {s.symbole for s in db.query(Societe).all()}

        # 1) Historique par annee (upsert symbole+annee)
        nb_hist = 0
        for h in historique:
            if h["symbole"] not in symboles_connus:
                continue
            ligne = (
                db.query(Dividende)
                .filter_by(symbole=h["symbole"], annee=h["annee"])
                .one_or_none()
            )
            if ligne is None:
                ligne = Dividende(symbole=h["symbole"], annee=h["annee"])
                db.add(ligne)
            ligne.montant = h["montant"]
            ligne.rendement = h["rendement"]
            nb_hist += 1

        # 2) Prochains detachements : on remplace tout (liste courte, mouvante)
        db.query(Detachement).delete()
        nb_proch = 0
        for p in prochains:
            if p["symbole"] not in symboles_connus:
                continue
            db.add(
                Detachement(
                    symbole=p["symbole"],
                    date_detachement=p["date_detachement"],
                    montant=p["montant"],
                    rendement=p["rendement"],
                )
            )
            nb_proch += 1

        db.commit()
        return nb_hist, nb_proch
    finally:
        db.close()


if __name__ == "__main__":
    n = enregistrer_cotations()
    print(f"{n} cotations enregistrees pour le {date.today()}")
    nb_indices = enregistrer_indices()
    print(f"{nb_indices} indices de reference enregistres")
    nb_hist, nb_proch = enregistrer_dividendes()
    print(f"{nb_hist} dividendes (historique) et {nb_proch} detachements a venir")
    nb_secteurs = enregistrer_secteurs()
    print(f"{nb_secteurs} societes classees par secteur")
    from .alertes import evaluer_alertes
    db = SessionLocal()
    try:
        print(f"{len(evaluer_alertes(db))} alerte(s) declenchee(s)")
    finally:
        db.close()
