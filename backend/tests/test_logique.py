"""Tests des regles metier pures : pays, liquidite, tendance des dividendes."""
from __future__ import annotations

from datetime import date, timedelta

from app.main import _indicateurs_techniques, _tendance_dividendes, classer_liquidite, pays_depuis_symbole
from app.models import Cotation, Dividende


# ------------------------------------------------------- pays_depuis_symbole
def test_pays_suffixe_simple():
    assert pays_depuis_symbole("BOAC") == "Côte d'Ivoire"
    assert pays_depuis_symbole("BOAB") == "Bénin"
    assert pays_depuis_symbole("SNTS") == "Sénégal"
    assert pays_depuis_symbole("BOAM") == "Mali"
    assert pays_depuis_symbole("BOAN") == "Niger"
    assert pays_depuis_symbole("ORGT") == "Togo"


def test_pays_suffixe_bf_prioritaire():
    # 'BF' (2 lettres) doit etre teste avant 'F' : ONTBF = Burkina, pas 'F'
    assert pays_depuis_symbole("ONTBF") == "Burkina Faso"
    assert pays_depuis_symbole("CBIBF") == "Burkina Faso"


# --------------------------------------------------------- classer_liquidite
def test_liquidite_seuils():
    assert classer_liquidite(5000) == "haute"
    assert classer_liquidite(1000) == "haute"
    assert classer_liquidite(999) == "moyenne"
    assert classer_liquidite(100) == "moyenne"
    assert classer_liquidite(99) == "faible"
    assert classer_liquidite(0) == "faible"
    assert classer_liquidite(None) is None


# ------------------------------------------------------ _tendance_dividendes
def _serie(*montants_par_annee):
    return [
        Dividende(symbole="X", annee=annee, montant=montant)
        for annee, montant in montants_par_annee
    ]


def test_tendance_hausse_regulier():
    serie = _serie((2022, 273), (2023, 353), (2024, 468), (2025, 585))
    assert _tendance_dividendes(serie) == "hausse"


def test_tendance_stable():
    serie = _serie((2022, 100), (2023, 100), (2024, 102))
    assert _tendance_dividendes(serie) == "stable"


def test_tendance_baisse():
    serie = _serie((2022, 200), (2023, 150), (2024, 120))
    assert _tendance_dividendes(serie) == "baisse"


def test_tendance_irreguliere():
    # Ca monte au total mais avec une baisse en route -> irregulier
    serie = _serie((2022, 100), (2023, 60), (2024, 180))
    assert _tendance_dividendes(serie) == "irregulier"


def test_tendance_historique_trop_court():
    assert _tendance_dividendes(_serie((2025, 100))) is None
    assert _tendance_dividendes([]) is None


def test_indicateurs_techniques_sur_60_seances():
    cours = [Cotation(symbole="TEST", jour=date(2026, 1, 1) + timedelta(days=i),
                      cours_cloture=100 + i, volume=1000 + i)
             for i in range(60)]
    indicateurs = _indicateurs_techniques(cours)
    assert indicateurs.moyenne_mobile_20 == 149.5
    assert indicateurs.moyenne_mobile_50 == 134.5
    assert indicateurs.rsi_14 == 100.0
    assert indicateurs.volume_moyen_20 == 1049.5
    assert indicateurs.volatilite_20 is not None
    assert len(indicateurs.points) == 60
