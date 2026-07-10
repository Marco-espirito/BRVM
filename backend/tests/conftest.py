"""Configuration des tests : base SQLite isolee + donnees de demo.

IMPORTANT : BRVM_DB_PATH doit etre defini AVANT d'importer app.*, car
app.db lit cette variable au moment de l'import pour creer l'engine.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import date
from pathlib import Path

# Base temporaire, propre a chaque session de tests
_TMP_DIR = tempfile.mkdtemp(prefix="brvm-tests-")
os.environ["BRVM_DB_PATH"] = str(Path(_TMP_DIR) / "test.db")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Cotation, Detachement, Dividende, Societe

FIXTURES = Path(__file__).parent / "fixtures"


def lire_fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def base_de_demo():
    """Cree les tables et seme un petit marche de 3 actions realistes."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.add_all(
            [
                # Une banque liquide au dividende en hausse (le bon eleve)
                Societe(symbole="BOAB", nom="BANK OF AFRICA BENIN",
                        secteur="Services financiers"),
                # Un telecom moyen
                Societe(symbole="SNTS", nom="SONATEL SENEGAL",
                        secteur="Télécommunications"),
                # Une action illiquide sans dividende connu (le piege)
                Societe(symbole="SLBC", nom="SOLIBRA COTE D'IVOIRE",
                        secteur="Consommation de base"),
            ]
        )
        for jour, boab, snts, slbc in [
            (date(2026, 7, 9), 8800.0, 31000.0, 40100.0),
            (date(2026, 7, 10), 8790.0, 30900.0, 40100.0),
        ]:
            db.add_all(
                [
                    Cotation(symbole="BOAB", jour=jour, cours_cloture=boab,
                             variation=-0.11, volume=4648),
                    Cotation(symbole="SNTS", jour=jour, cours_cloture=snts,
                             variation=-0.32, volume=769),
                    Cotation(symbole="SLBC", jour=jour, cours_cloture=slbc,
                             variation=0.0, volume=18),
                ]
            )
        db.add_all(
            [
                Dividende(symbole="BOAB", annee=2022, montant=273, rendement=10.3),
                Dividende(symbole="BOAB", annee=2023, montant=353, rendement=11.87),
                Dividende(symbole="BOAB", annee=2024, montant=468, rendement=14.72),
                Dividende(symbole="BOAB", annee=2025, montant=585, rendement=15.88),
                Dividende(symbole="SNTS", annee=2024, montant=1740, rendement=5.5),
                Detachement(symbole="BOAB", date_detachement="15/08/2026",
                            montant=585, rendement=6.6),
            ]
        )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def client():
    client = TestClient(app)
    identifiant = uuid.uuid4().hex
    reponse = client.post("/auth/inscription", json={
        "email": f"test-{identifiant}@example.com",
        "mot_de_passe": "mot-de-passe-test-solide",
        "nom": "Test",
    })
    assert reponse.status_code == 200
    depot = client.post("/portefeuille/especes", json={
        "type": "DEPOT", "montant": 10_000_000,
    })
    assert depot.status_code == 200
    return client
