"""Logique d'analyse pure : classification (pays, liquidite), performances,
comparaison aux indices et indicateurs techniques. Aucune route ici — ces
fonctions sont appelees par les routers et testees directement."""
from __future__ import annotations

from datetime import timedelta
from math import sqrt
from statistics import stdev

from sqlalchemy.orm import Session

from ..models import Cotation, Dividende, IndiceCotation
from ..schemas import (
    ComparaisonPointOut,
    IndicateursTechniquesOut,
    PerformanceOut,
    PointTechniqueOut,
)

# Le suffixe du symbole BRVM indique le pays d'origine de la societe :
# BOAC = BOA Cote d'Ivoire, BOAS = BOA Senegal, ONTBF = Onatel Burkina...
_PAYS_SUFFIXE = {
    "BF": "Burkina Faso",
    "C": "Côte d'Ivoire",
    "B": "Bénin",
    "S": "Sénégal",
    "M": "Mali",
    "N": "Niger",
    "T": "Togo",
}


def pays_depuis_symbole(symbole: str) -> str:
    if symbole.endswith("BF"):  # suffixe 2 lettres, a tester en premier
        return _PAYS_SUFFIXE["BF"]
    return _PAYS_SUFFIXE.get(symbole[-1], "Autre")


def classer_liquidite(volume_moyen: float | None) -> str | None:
    """Classement simple base sur le volume moyen quotidien echange."""
    if volume_moyen is None:
        return None
    if volume_moyen >= 1000:
        return "haute"
    if volume_moyen >= 100:
        return "moyenne"
    return "faible"


def annees_consecutives(annees: list[int]) -> int:
    if not annees:
        return 0
    uniques = sorted(set(annees), reverse=True)
    total = 1
    for recente, ancienne in zip(uniques, uniques[1:]):
        if recente - ancienne != 1:
            break
        total += 1
    return total


def tendance_dividendes(serie: list[Dividende]) -> str | None:
    """Qualifie l'evolution du dividende sur les annees connues."""
    montants = [d.montant for d in sorted(serie, key=lambda d: d.annee)]
    if len(montants) < 2:
        return None
    evolution = (montants[-1] - montants[0]) / montants[0] * 100
    jamais_baisse = all(b >= a for a, b in zip(montants, montants[1:]))
    if jamais_baisse and evolution > 5:
        return "hausse"
    if abs(evolution) <= 5:
        return "stable"
    if evolution < 0:
        return "baisse"
    return "irregulier"


def calculer_performances(cours: list[Cotation]) -> PerformanceOut:
    if not cours:
        return PerformanceOut()
    dernier = cours[-1]

    def variation(delta: timedelta) -> float | None:
        cible = dernier.jour - delta
        anciens = [c for c in cours if c.jour <= cible]
        if not anciens or not anciens[-1].cours_cloture:
            return None
        return round((dernier.cours_cloture / anciens[-1].cours_cloture - 1) * 100, 2)

    debut = dernier.jour - timedelta(days=364)
    fenetre = [c for c in cours if c.jour >= debut]
    valeurs = [c.cours_cloture for c in fenetre if c.cours_cloture is not None]
    return PerformanceOut(
        variation_7j=variation(timedelta(days=7)),
        variation_30j=variation(timedelta(days=30)),
        variation_6m=variation(timedelta(days=182)),
        variation_1a=variation(timedelta(days=365)),
        plus_haut_52s=max(valeurs) if valeurs else None,
        plus_bas_52s=min(valeurs) if valeurs else None,
        debut_52s=fenetre[0].jour if fenetre else None,
        fin_52s=dernier.jour,
    )


def comparaison_indices(db: Session, cours: list[Cotation]) -> list[ComparaisonPointOut]:
    if not cours:
        return []
    debut = cours[-1].jour - timedelta(days=365)
    actions = [c for c in cours if c.jour >= debut]
    indices = db.query(IndiceCotation).filter(
        IndiceCotation.jour >= debut,
        IndiceCotation.jour <= cours[-1].jour,
    ).order_by(IndiceCotation.jour).all()
    par_code = {}
    for i in indices:
        par_code.setdefault(i.code, {})[i.jour] = i.cloture
    if not indices:
        return []

    jours = sorted({c.jour for c in actions} | {i.jour for i in indices})
    action_jour = {c.jour: c.cours_cloture for c in actions}
    derniers = {"action": None, "BRVM-COMPOSITE": None, "BRVM-30": None}
    bases = {}
    resultat = []
    for jour in jours:
        if jour in action_jour:
            derniers["action"] = action_jour[jour]
        for code in ("BRVM-COMPOSITE", "BRVM-30"):
            if jour in par_code.get(code, {}):
                derniers[code] = par_code[code][jour]
        if any(v is None for v in derniers.values()):
            continue
        for cle, valeur in derniers.items():
            bases.setdefault(cle, valeur)
        resultat.append(ComparaisonPointOut(
            jour=jour,
            action=round(derniers["action"] / bases["action"] * 100, 2),
            brvm_composite=round(derniers["BRVM-COMPOSITE"] / bases["BRVM-COMPOSITE"] * 100, 2),
            brvm_30=round(derniers["BRVM-30"] / bases["BRVM-30"] * 100, 2),
        ))
    return resultat


def indicateurs_techniques(cours: list[Cotation]) -> IndicateursTechniquesOut:
    """Indicateurs descriptifs, sans generation de signal d'investissement."""
    if not cours:
        return IndicateursTechniquesOut(explications=["Aucun cours disponible."])
    clotures = [c.cours_cloture for c in cours]
    points = []
    for i, c in enumerate(cours):
        mm20 = sum(clotures[i - 19:i + 1]) / 20 if i >= 19 else None
        mm50 = sum(clotures[i - 49:i + 1]) / 50 if i >= 49 else None
        points.append(PointTechniqueOut(
            jour=c.jour, cours=c.cours_cloture,
            moyenne_mobile_20=round(mm20, 2) if mm20 is not None else None,
            moyenne_mobile_50=round(mm50, 2) if mm50 is not None else None,
        ))
    variations = [(b / a - 1) for a, b in zip(clotures, clotures[1:]) if a]
    rsi = None
    if len(clotures) >= 15:
        changements = [b - a for a, b in zip(clotures[-15:-1], clotures[-14:])]
        gains = sum(max(v, 0) for v in changements) / 14
        pertes = sum(max(-v, 0) for v in changements) / 14
        rsi = 100.0 if pertes == 0 else 100 - 100 / (1 + gains / pertes)
    volatilite = stdev(variations[-20:]) * sqrt(252) * 100 if len(variations) >= 20 else None
    volumes = [c.volume for c in cours[-20:] if c.volume is not None]
    volume_moyen = sum(volumes) / len(volumes) if volumes else None
    mm20, mm50 = points[-1].moyenne_mobile_20, points[-1].moyenne_mobile_50
    dernier = clotures[-1]
    explications = []
    if mm20 is None:
        explications.append("La moyenne mobile 20 nécessite encore davantage de séances.")
    else:
        position = "au-dessus" if dernier > mm20 else "en dessous" if dernier < mm20 else "au niveau"
        explications.append(f"Le cours se situe {position} de sa moyenne des 20 dernières séances : cela décrit la tendance récente, sans prédire sa poursuite.")
    if mm50 is None:
        explications.append("La moyenne mobile 50 apparaîtra après 50 cours de clôture.")
    elif mm20 is not None:
        relation = "supérieure" if mm20 > mm50 else "inférieure" if mm20 < mm50 else "proche"
        explications.append(f"La moyenne 20 séances est {relation} à la moyenne 50 séances, ce qui situe le mouvement récent par rapport à la tendance plus longue.")
    if rsi is None:
        explications.append("Le RSI nécessite au moins 15 cours de clôture.")
    elif rsi >= 70:
        explications.append("Le RSI est élevé : les hausses récentes ont dominé, mais cela ne signifie pas automatiquement que le cours va baisser.")
    elif rsi <= 30:
        explications.append("Le RSI est faible : les baisses récentes ont dominé, sans garantir un rebond.")
    else:
        explications.append("Le RSI se situe dans une zone intermédiaire : hausses et baisses récentes sont relativement équilibrées.")
    if volatilite is not None:
        explications.append("La volatilité annualisée mesure l'amplitude des variations, pas leur direction : plus elle est élevée, plus le cours a été irrégulier.")
    return IndicateursTechniquesOut(
        moyenne_mobile_20=mm20, moyenne_mobile_50=mm50,
        rsi_14=round(rsi, 2) if rsi is not None else None,
        volatilite_20=round(volatilite, 2) if volatilite is not None else None,
        volume_moyen_20=round(volume_moyen, 2) if volume_moyen is not None else None,
        points=points, explications=explications,
    )
