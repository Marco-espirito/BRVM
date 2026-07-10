"""Tests du parsing des scrapers — la partie qui casse en premier quand
un site change sa structure HTML. Les fixtures reproduisent la structure
reelle de brvm.org et sikafinance.com au 2026-07-10."""
from __future__ import annotations

from app.scraper.brvm import _to_float, parse_cotations
from app.scraper.dividendes import parse_dividendes
from app.scraper.secteurs import _symboles_de_la_page

from conftest import lire_fixture


# ---------------------------------------------------------------- _to_float
def test_to_float_formats_francais():
    # La BRVM utilise espace (parfois insecable) pour les milliers,
    # virgule pour les decimales.
    assert _to_float("3 150") == 3150.0
    assert _to_float("31\xa0000") == 31000.0
    assert _to_float("1,59") == 1.59
    assert _to_float("-0,32") == -0.32
    assert _to_float("7,11 %") == 7.11


def test_to_float_valeurs_vides():
    assert _to_float("") is None
    assert _to_float("-") is None
    assert _to_float(None) is None
    assert _to_float("A préciser") is None


# ---------------------------------------------------------- parse_cotations
def test_parse_cotations():
    actions = parse_cotations(lire_fixture("cotations.html"))
    assert len(actions) == 3

    snts = actions[0]
    assert snts["symbole"] == "SNTS"
    assert snts["nom"] == "SONATEL SENEGAL"
    assert snts["cours_cloture"] == 30900.0
    assert snts["variation"] == -0.32
    assert snts["volume"] == 1739.0

    # Cellule '-' (pas de cours d'ouverture) -> None, pas un crash
    slbc = actions[2]
    assert slbc["cours_ouverture"] is None


def test_parse_cotations_page_inattendue():
    # Si la structure change (plus de tableau 'Symbole'), on veut une
    # erreur explicite plutot qu'une liste vide silencieuse.
    import pytest

    with pytest.raises(RuntimeError):
        parse_cotations("<html><body><p>rien ici</p></body></html>")


# --------------------------------------------------------- parse_dividendes
def test_parse_dividendes_historique():
    historique, _ = parse_dividendes(lire_fixture("dividendes.html"))

    boab = [h for h in historique if h["symbole"] == "BOAB"]
    assert [h["annee"] for h in boab] == [2022, 2023, 2024, 2025]
    assert boab[-1]["montant"] == 585.0
    assert boab[-1]["rendement"] == 15.88

    # SDSC n'a pas de dividende 2025 ('-') -> l'annee est simplement absente
    sdsc = [h for h in historique if h["symbole"] == "SDSC"]
    assert [h["annee"] for h in sdsc] == [2022, 2023, 2024]


def test_parse_dividendes_prochains_detachements():
    _, prochains = parse_dividendes(lire_fixture("dividendes.html"))
    assert len(prochains) == 2

    bicb = prochains[0]
    # Le symbole vient du lien /marches/cotation_BICB.bj
    assert bicb["symbole"] == "BICB"
    assert bicb["date_detachement"] == "13/07/2026"
    assert bicb["montant"] == 254.6

    # Date non encore connue : conservee telle quelle, montant parse quand meme
    stbc = prochains[1]
    assert stbc["symbole"] == "STBC"
    assert stbc["montant"] == 1707.2


# ------------------------------------------------------------------ secteurs
def test_parse_page_secteur():
    # Les pages sectorielles ont la meme structure que la page principale :
    # on doit en extraire les symboles.
    symboles = _symboles_de_la_page(lire_fixture("cotations.html"))
    assert symboles == ["SNTS", "BOAB", "SLBC"]
