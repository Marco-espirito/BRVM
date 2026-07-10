"""Routes des actions cotees : statut des donnees, liste enrichie, detail
(historique + performances + indicateurs) et Top 10 diversifie."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Cotation, Detachement, Dividende, Societe
from ..schemas import (
    ActionDetailOut,
    ActionOut,
    CotationOut,
    DetachementOut,
    DividendeOut,
    StatutDonneesOut,
    TopActionOut,
)
from ..services.analyse import (
    annees_consecutives,
    calculer_performances,
    classer_liquidite,
    comparaison_indices,
    indicateurs_techniques,
    pays_depuis_symbole,
    tendance_dividendes,
)

router = APIRouter(tags=["actions"])


@router.get("/donnees/statut", response_model=StatutDonneesOut)
def statut_donnees(db: Session = Depends(get_db)):
    """Fraîcheur et couverture du dernier jeu de cotations enregistré."""
    derniere_seance = db.query(func.max(Cotation.jour)).scalar()
    total = db.query(func.count(Societe.symbole)).scalar() or 0
    if derniere_seance is None:
        return StatutDonneesOut(actions_total=total)
    couvertes = db.query(func.count(func.distinct(Cotation.symbole))).filter(
        Cotation.jour == derniere_seance
    ).scalar() or 0
    recupere_le = db.query(func.max(Cotation.recupere_le)).filter(
        Cotation.jour == derniere_seance
    ).scalar()
    age = max((date.today() - derniere_seance).days, 0)
    couverture_complete = total == 0 or couvertes / total >= 0.9
    statut = "a_jour" if age <= 3 and couverture_complete else "a_verifier" if age <= 7 else "ancien"
    return StatutDonneesOut(
        derniere_seance=derniere_seance, recupere_le=recupere_le,
        actions_couvertes=couvertes, actions_total=total,
        age_jours=age, statut=statut,
    )


@router.get("/actions", response_model=list[ActionOut])
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
    divs_par_symbole: dict[str, list[int]] = {}
    for d in db.query(Dividende).filter(Dividende.montant.isnot(None)).all():
        divs_par_symbole.setdefault(d.symbole, []).append(d.annee)

    historiques_cours: dict[str, list[Cotation]] = {}
    for cotation in db.query(Cotation).filter(Cotation.cours_cloture.isnot(None)).order_by(Cotation.jour).all():
        historiques_cours.setdefault(cotation.symbole, []).append(cotation)
    variations_30j: dict[str, float | None] = {}
    for s, c in lignes:
        cible = c.jour - timedelta(days=30)
        ancien = next((x for x in reversed(historiques_cours.get(s.symbole, []))
                       if x.jour <= cible), None)
        variations_30j[s.symbole] = (
            round((c.cours_cloture / ancien.cours_cloture - 1) * 100, 2)
            if ancien and ancien.cours_cloture and c.cours_cloture else None
        )

    resultat = []
    for s, c in lignes:
        div = derniers_dividendes.get(s.symbole)
        rendement = None
        if div is not None and c.cours_cloture:
            # Rendement recalcule sur le cours d'aujourd'hui, pas celui
            # de l'epoque du versement : c'est ce que TOI tu toucherais.
            rendement = round(div.montant / c.cours_cloture * 100, 2)
        consecutives = annees_consecutives(divs_par_symbole.get(s.symbole, []))
        regularite = "forte" if consecutives >= 4 else "moyenne" if consecutives >= 2 else "faible"
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
                secteur=s.secteur,
                volume_moyen=volumes_moyens.get(s.symbole),
                liquidite=classer_liquidite(volumes_moyens.get(s.symbole)),
                variation_30j=variations_30j[s.symbole],
                regularite_dividende=regularite,
                annees_dividende_consecutives=consecutives,
            )
        )
    return resultat


@router.get("/actions/{symbole}", response_model=ActionDetailOut)
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

    cours_valides = [c for c in historique if c.cours_cloture is not None]
    performances = calculer_performances(cours_valides)
    comparaison = comparaison_indices(db, cours_valides)
    indicateurs = indicateurs_techniques(cours_valides)

    return ActionDetailOut(
        symbole=societe.symbole,
        nom=societe.nom,
        historique=[CotationOut.model_validate(c) for c in historique],
        dividendes=[DividendeOut.model_validate(d) for d in dividendes],
        prochain_detachement=(
            DetachementOut.model_validate(detachement) if detachement else None
        ),
        performances=performances,
        comparaison_indices=comparaison,
        indicateurs_techniques=indicateurs,
    )


@router.get("/top-actions", response_model=list[TopActionOut])
def top_actions(limit: int = 10, db: Session = Depends(get_db)):
    """Top 10 pedagogique pour un debutant 'rendement long terme'.

    Score sur 100, volontairement simple et transparent :
      - 40 pts : rendement du dividende (plafonne a 8 % ; un rendement > 15 %
        est suspect = dividende exceptionnel, peu de points)
      - 30 pts : liquidite (peut-on recuperer son argent facilement ?)
      - 30 pts : historique du dividende (regularite + tendance)

    Le top est DIVERSIFIE : d'abord la meilleure action de chaque secteur
    officiel BRVM, puis les meilleurs scores restants pour completer a 10.
    Ce n'est PAS un conseil d'investissement : c'est un filtre d'apprentissage.
    """
    actions = liste_actions(db)

    # Historique des dividendes par societe (pour la tendance)
    divs_par_symbole: dict[str, list[Dividende]] = {}
    for d in db.query(Dividende).filter(Dividende.montant.isnot(None)).all():
        divs_par_symbole.setdefault(d.symbole, []).append(d)

    resultats = []
    for a in actions:
        raisons: list[str] = []

        # --- Rendement (40 pts) ---
        if a.rendement is None:
            pts_rendement = 0.0
            raisons.append("Pas de dividende connu (0/40)")
        elif a.rendement > 15:
            pts_rendement = 10.0
            raisons.append(
                f"⚠️ Rendement {a.rendement:.1f} % : dividende probablement exceptionnel (10/40)"
            )
        else:
            pts_rendement = min(a.rendement, 8.0) / 8.0 * 40.0
            raisons.append(f"Rendement {a.rendement:.2f} % ({pts_rendement:.0f}/40)")

        # --- Liquidite (30 pts) ---
        pts_liquidite = {"haute": 30.0, "moyenne": 15.0, "faible": 0.0}.get(
            a.liquidite or "", 0.0
        )
        emoji = {"haute": "🟢", "moyenne": "🟡", "faible": "🔴"}.get(a.liquidite or "", "")
        raisons.append(f"Liquidité {a.liquidite or 'inconnue'} {emoji} ({pts_liquidite:.0f}/30)")

        # --- Historique du dividende (30 pts) ---
        serie = divs_par_symbole.get(a.symbole, [])
        tendance = tendance_dividendes(serie)
        pts_regularite = min(len(serie), 4) / 4.0 * 10.0
        pts_tendance = {"hausse": 20.0, "stable": 14.0, "irregulier": 7.0, "baisse": 0.0}.get(
            tendance or "", 0.0
        )
        libelle = {
            "hausse": "en hausse régulière 🌱",
            "stable": "stable ⚖️",
            "irregulier": "irrégulier 🎢",
            "baisse": "en baisse 📉",
        }.get(tendance or "", "historique trop court")
        raisons.append(
            f"Dividende {libelle}, versé {len(serie)} année(s) ({pts_tendance + pts_regularite:.0f}/30)"
        )

        resultats.append(
            TopActionOut(
                rang=0,
                symbole=a.symbole,
                nom=a.nom,
                pays=a.pays,
                secteur=a.secteur,
                cours_cloture=a.cours_cloture,
                rendement=a.rendement,
                liquidite=a.liquidite,
                tendance_dividende=tendance,
                score=round(pts_rendement + pts_liquidite + pts_tendance + pts_regularite, 1),
                raisons=raisons,
            )
        )

    resultats.sort(key=lambda r: -r.score)

    # Diversification : la meilleure action de chaque secteur d'abord...
    top: list[TopActionOut] = []
    secteurs_pris: set[str] = set()
    for r in resultats:
        if r.secteur and r.secteur not in secteurs_pris:
            r.meilleur_du_secteur = True
            secteurs_pris.add(r.secteur)
            top.append(r)
    # ... puis les meilleurs scores restants pour completer.
    limit = max(1, min(limit, len(resultats)))
    for r in resultats:
        if len(top) >= limit:
            break
        if r not in top:
            top.append(r)

    top.sort(key=lambda r: -r.score)
    for i, r in enumerate(top[:limit], start=1):
        r.rang = i
    return top[:limit]
