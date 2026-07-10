"""Recupere les cotations et les enregistre en base (upsert par jour)."""
from __future__ import annotations

from datetime import date

from .db import Base, SessionLocal, engine
from .models import Cotation, Detachement, Dividende, Societe
from .scraper.brvm import fetch_cotations
from .scraper.dividendes import fetch_dividendes


def creer_tables() -> None:
    """Cree les tables si elles n'existent pas encore."""
    Base.metadata.create_all(bind=engine)


def enregistrer_cotations() -> int:
    """Scrape la BRVM et enregistre une cotation par action pour aujourd'hui.

    Retourne le nombre d'actions traitees. Si on relance le meme jour,
    la cotation du jour est mise a jour (pas de doublon).
    """
    creer_tables()
    actions = fetch_cotations()
    aujourdhui = date.today()

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


def enregistrer_dividendes() -> tuple[int, int]:
    """Scrape Sika Finance et enregistre dividendes + prochains detachements.

    Retourne (nb lignes historique, nb detachements). On ne garde que les
    societes deja connues en base (celles cotees a la BRVM).
    """
    creer_tables()
    historique, prochains = fetch_dividendes()

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
    nb_hist, nb_proch = enregistrer_dividendes()
    print(f"{nb_hist} dividendes (historique) et {nb_proch} detachements a venir")
