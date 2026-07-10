"""Simulation de strategies passees (backtest) : selection des candidats a une
date de depart et deroule d'un panier jusqu'a la derniere seance."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Cotation, Dividende, Societe
from ..schemas import LigneBacktestOut, PointBacktestOut
from .analyse import annees_consecutives


def candidats_backtest(db: Session, depart: date) -> list[dict]:
    resultat = []
    societes = db.query(Societe).all()
    for s in societes:
        cours = db.query(Cotation).filter(Cotation.symbole == s.symbole, Cotation.jour == depart,
                                          Cotation.cours_cloture.isnot(None)).first()
        if not cours or not cours.cours_cloture:
            continue
        divs = db.query(Dividende).filter(Dividende.symbole == s.symbole,
            Dividende.annee < depart.year, Dividende.montant.isnot(None)).order_by(Dividende.annee).all()
        dernier_div = divs[-1].montant if divs else 0
        rendement = dernier_div / cours.cours_cloture * 100
        volume = db.query(func.avg(Cotation.volume)).filter(
            Cotation.symbole == s.symbole, Cotation.jour <= depart).scalar() or 0
        liquidite = 30 if volume >= 1000 else 15 if volume >= 100 else 0
        consecutives = annees_consecutives([d.annee for d in divs])
        regularite = min(consecutives, 4) / 4 * 30
        rendement_pts = min(rendement, 8) / 8 * 40 if rendement <= 15 else 10
        resultat.append({"symbole": s.symbole, "secteur": s.secteur,
                         "cours": cours.cours_cloture, "rendement": rendement,
                         "score": rendement_pts + liquidite + regularite})
    return resultat


def simuler_backtest(db: Session, nom: str, description: str, panier: list[dict],
                     depart: date, fin: date, capital: float, frais_pct: float) -> LigneBacktestOut:
    allocation = capital / len(panier)
    positions, cash, frais_achat = {}, capital, 0.0
    for c in panier:
        cout_unitaire = c["cours"] * (1 + frais_pct / 100)
        quantite = int(allocation // cout_unitaire)
        brut, frais = quantite * c["cours"], quantite * c["cours"] * frais_pct / 100
        positions[c["symbole"]] = quantite
        cash -= brut + frais
        frais_achat += frais
    cotations = db.query(Cotation).filter(Cotation.symbole.in_(positions),
        Cotation.jour >= depart, Cotation.jour <= fin).order_by(Cotation.jour).all()
    jours = sorted({c.jour for c in cotations})
    cours_jour = {(c.symbole, c.jour): c.cours_cloture for c in cotations if c.cours_cloture}
    derniers = {}
    dividendes_par_annee = {}
    for d in db.query(Dividende).filter(Dividende.symbole.in_(positions),
            Dividende.annee >= depart.year, Dividende.annee <= fin.year,
            Dividende.montant.isnot(None)).all():
        dividendes_par_annee.setdefault(d.annee, 0)
        dividendes_par_annee[d.annee] += positions[d.symbole] * d.montant
    points, dividendes_cumules, annee_precedente = [], 0.0, depart.year
    for jour in jours:
        for symbole in positions:
            if (symbole, jour) in cours_jour: derniers[symbole] = cours_jour[(symbole, jour)]
        if jour.year > annee_precedente:
            dividendes_cumules += dividendes_par_annee.get(annee_precedente, 0)
            annee_precedente = jour.year
        valeur = cash + dividendes_cumules + sum(q * derniers.get(s, next(c["cours"] for c in panier if c["symbole"] == s)) for s, q in positions.items())
        points.append(PointBacktestOut(jour=jour, valeur=round(valeur, 2)))
    dividendes_cumules += dividendes_par_annee.get(fin.year, 0)
    valeur_titres = sum(q * derniers.get(s, 0) for s, q in positions.items())
    frais_vente = valeur_titres * frais_pct / 100
    final = cash + dividendes_cumules + valeur_titres - frais_vente
    return LigneBacktestOut(
        strategie=nom, description=description, symboles=list(positions),
        capital_initial=capital, montant_investi=capital - cash,
        valeur_finale=round(final, 2), dividendes=round(dividendes_cumules, 2),
        frais=round(frais_achat + frais_vente, 2),
        performance_pct=round((final / capital - 1) * 100, 2), points=points,
    )
