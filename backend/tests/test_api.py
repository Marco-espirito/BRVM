"""Tests de l'API sur une base de demo (3 actions, 2 jours de cotations)."""
from __future__ import annotations


# ------------------------------------------------------------------ /actions
def test_liste_actions(client):
    actions = client.get("/actions").json()
    assert len(actions) == 3

    boab = next(a for a in actions if a["symbole"] == "BOAB")
    assert boab["cours_cloture"] == 8790.0
    assert boab["pays"] == "Bénin"
    assert boab["secteur"] == "Services financiers"
    assert boab["liquidite"] == "haute"
    # Dernier dividende connu (2025 : 585) + rendement recalcule sur le
    # cours actuel : 585 / 8790 * 100 = 6.66 %
    assert boab["dividende"] == 585.0
    assert boab["annee_dividende"] == 2025
    assert boab["rendement"] == 6.66

    # SLBC : pas de dividende connu, volume 18 -> liquidite faible
    slbc = next(a for a in actions if a["symbole"] == "SLBC")
    assert slbc["dividende"] is None
    assert slbc["rendement"] is None
    assert slbc["liquidite"] == "faible"


# ------------------------------------------------------------ /actions/{sym}
def test_detail_action(client):
    detail = client.get("/actions/BOAB").json()
    assert detail["nom"] == "BANK OF AFRICA BENIN"
    assert len(detail["historique"]) == 2  # 2 jours de cotations
    # Dividendes tries du plus recent au plus ancien
    assert [d["annee"] for d in detail["dividendes"]] == [2025, 2024, 2023, 2022]
    assert detail["prochain_detachement"]["date_detachement"] == "15/08/2026"


def test_detail_action_minuscules(client):
    # Le symbole est normalise en majuscules
    assert client.get("/actions/boab").status_code == 200


def test_detail_action_inconnue(client):
    assert client.get("/actions/XXXX").status_code == 404


# -------------------------------------------------------------- /top-actions
def test_top_actions_classement(client):
    top = client.get("/top-actions").json()
    assert len(top) == 3
    # BOAB (bon rendement + liquide + dividende en hausse) doit dominer,
    # SLBC (illiquide, pas de dividende) doit etre dernier.
    assert top[0]["symbole"] == "BOAB"
    assert top[-1]["symbole"] == "SLBC"
    assert top[0]["score"] > top[-1]["score"]
    assert top[0]["tendance_dividende"] == "hausse"
    # Chaque action est la meilleure de son secteur (secteurs tous differents)
    assert all(t["meilleur_du_secteur"] for t in top)
    # Le score est explique
    assert any("Rendement" in r for r in top[0]["raisons"])


def test_top_actions_limit(client):
    assert len(client.get("/top-actions?limit=2").json()) == 2


# ------------------------------------------------------------- /portefeuille
def test_portefeuille_cycle_achat_vente(client):
    # Portefeuille vide au depart
    p = client.get("/portefeuille").json()
    assert p["positions"] == []
    assert p["total_investi"] == 0

    # Achat fictif : 10 BOAB au dernier cours connu (8790)
    r = client.post(
        "/portefeuille/positions", json={"symbole": "BOAB", "quantite": 10}
    )
    assert r.status_code == 200
    position = r.json()
    assert position["prix_achat"] == 8790.0
    assert position["investi"] == 87900.0
    # 10 actions x 585 FCFA de dividende annuel estime
    assert position["dividende_annuel"] == 5850.0

    # Le portefeuille reflete l'achat + l'historique jour par jour
    p = client.get("/portefeuille").json()
    assert p["total_investi"] == 87900.0
    assert len(p["positions"]) == 1
    assert p["historique"][-1]["valeur"] == 87900.0

    # Vente fictive -> portefeuille de nouveau vide
    assert client.delete(f"/portefeuille/positions/{position['id']}").status_code == 200
    assert client.get("/portefeuille").json()["positions"] == []


def test_portefeuille_achats_invalides(client):
    assert (
        client.post("/portefeuille/positions", json={"symbole": "XXXX", "quantite": 5})
        .status_code == 404
    )
    assert (
        client.post("/portefeuille/positions", json={"symbole": "BOAB", "quantite": 0})
        .status_code == 400
    )
    assert client.delete("/portefeuille/positions/99999").status_code == 404
