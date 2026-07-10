"""Tests du cycle 'git scraping' : export JSON (cloud) -> import (local).

Les fetchers reseau sont remplaces par des donnees en dur : on teste le
format des fichiers et le cablage, pas les sites externes.
"""
from __future__ import annotations

import json
from datetime import date

import app.cloud_ingest as cloud_ingest
import app.import_data as import_data

ACTIONS = [
    {
        "symbole": "BOAB", "nom": "BANK OF AFRICA BENIN", "volume": 4648.0,
        "cours_veille": 8800.0, "cours_ouverture": 8795.0,
        "cours_cloture": 8790.0, "variation": -0.11,
    }
]
HISTORIQUE = [{"symbole": "BOAB", "annee": 2025, "montant": 585.0, "rendement": 15.88}]
PROCHAINS = [
    {"symbole": "BOAB", "date_detachement": "15/08/2026", "montant": 585.0,
     "rendement": 6.6}
]
SECTEURS = {"BOAB": "Services financiers"}
INDICES = [
    {"code": "BRVM-COMPOSITE", "cloture": 470.48, "variation": 1.42},
    {"code": "BRVM-30", "cloture": 222.20, "variation": 2.05},
]


def _simuler_scrapers(monkeypatch):
    monkeypatch.setattr(cloud_ingest, "fetch_cotations_et_date", lambda: (ACTIONS, date(2026, 7, 10)))
    monkeypatch.setattr(cloud_ingest, "fetch_indices", lambda: INDICES)
    monkeypatch.setattr(
        cloud_ingest, "fetch_dividendes", lambda: (HISTORIQUE, PROCHAINS)
    )
    monkeypatch.setattr(cloud_ingest, "fetch_secteurs", lambda: SECTEURS)


def test_export_ecrit_les_fichiers_attendus(tmp_path, monkeypatch):
    _simuler_scrapers(monkeypatch)

    bilan = cloud_ingest.exporter_tout(tmp_path, jour=date(2026, 7, 10))

    assert bilan == {
        "jour": "2026-07-10", "cotations": 1, "dividendes": 1,
        "detachements": 1, "secteurs": 1, "indices": 2,
    }

    # Un fichier de cotations par jour, nomme par la date
    contenu = json.loads(
        (tmp_path / "cotations" / "2026-07-10.json").read_text(encoding="utf-8")
    )
    assert contenu["jour"] == "2026-07-10"
    assert contenu["actions"] == ACTIONS
    assert contenu["indices"] == INDICES

    dividendes = json.loads((tmp_path / "dividendes.json").read_text(encoding="utf-8"))
    assert dividendes["historique"] == HISTORIQUE
    assert dividendes["prochains"] == PROCHAINS

    assert json.loads((tmp_path / "secteurs.json").read_text(encoding="utf-8")) == SECTEURS


def test_import_relit_les_fichiers_et_stocke(tmp_path, monkeypatch):
    _simuler_scrapers(monkeypatch)
    cloud_ingest.exporter_tout(tmp_path, jour=date(2026, 7, 10))

    # On intercepte les fonctions de stockage : le test verifie le cablage
    # JSON -> stocker_* sans toucher a la base partagee des autres tests.
    appels = {}
    monkeypatch.setattr(
        import_data, "stocker_cotations",
        lambda actions, jour: appels.setdefault("cotations", (actions, jour)) and len(actions) or len(actions),
    )
    monkeypatch.setattr(
        import_data, "stocker_dividendes",
        lambda h, p: appels.setdefault("dividendes", (h, p)) and (len(h), len(p)) or (len(h), len(p)),
    )
    monkeypatch.setattr(
        import_data, "stocker_secteurs",
        lambda m: appels.setdefault("secteurs", m) and len(m) or len(m),
    )
    monkeypatch.setattr(
        import_data, "stocker_indices",
        lambda valeurs, jour: appels.setdefault("indices", (valeurs, jour)) and len(valeurs) or len(valeurs),
    )

    bilan = import_data.importer_tout(tmp_path)

    assert bilan["jours_importes"] == 1
    assert appels["cotations"] == (ACTIONS, date(2026, 7, 10))
    assert appels["indices"] == (INDICES, date(2026, 7, 10))
    assert appels["dividendes"] == (HISTORIQUE, PROCHAINS)
    assert appels["secteurs"] == SECTEURS
