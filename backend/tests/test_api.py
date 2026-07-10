"""Tests de l'API sur une base de demo (3 actions, 2 jours de cotations)."""
from __future__ import annotations

import pytest


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
    assert boab["regularite_dividende"] == "forte"
    assert boab["annees_dividende_consecutives"] == 4
    assert boab["variation_30j"] is None

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
    assert detail["performances"]["plus_haut_52s"] == 8800.0
    assert detail["performances"]["plus_bas_52s"] == 8790.0
    assert detail["performances"]["variation_7j"] is None
    assert detail["indicateurs_techniques"]["moyenne_mobile_20"] is None
    assert detail["indicateurs_techniques"]["rsi_14"] is None
    assert len(detail["indicateurs_techniques"]["points"]) == 2


def test_detail_action_minuscules(client):
    # Le symbole est normalise en majuscules
    assert client.get("/actions/boab").status_code == 200


def test_detail_action_inconnue(client):
    assert client.get("/actions/XXXX").status_code == 404


def test_calendrier_dividendes_et_rappel(client):
    calendrier = client.get("/dividendes/calendrier")
    assert calendrier.status_code == 200
    evenement = next(e for e in calendrier.json()["evenements"] if e["symbole"] == "BOAB")
    assert evenement["date_detachement"] == "2026-08-15"
    assert evenement["date_paiement"] is None
    assert evenement["montant"] == 585.0
    rappel = client.post("/alertes", json={
        "symbole": "BOAB", "type": "rappel_detachement", "seuil": 60
    })
    assert rappel.status_code == 200
    alertes = client.post("/alertes/evaluer").json()
    assert any(e["alerte_id"] == rappel.json()["id"] for e in alertes)
    assert client.delete(f"/alertes/{rappel.json()['id']}").status_code == 200


def test_backtest_trois_strategies(client):
    reponse = client.post("/backtest", json={
        "date_depart": "2026-07-09", "capital": 1_000_000,
        "frais_pct": 1, "taille_panier": 3,
    })
    assert reponse.status_code == 200
    resultat = reponse.json()
    assert resultat["date_depart_effective"] == "2026-07-09"
    assert resultat["date_fin"] == "2026-07-10"
    assert {s["strategie"] for s in resultat["strategies"]} == {
        "Rendement", "Score", "Diversification"
    }
    assert all(len(s["symboles"]) == 3 for s in resultat["strategies"])
    assert all(s["frais"] > 0 for s in resultat["strategies"])
    assert len(resultat["limites"]) >= 4


def test_backtest_date_sans_periode(client):
    assert client.post("/backtest", json={
        "date_depart": "2026-07-10", "capital": 1_000_000
    }).status_code == 400


def test_compte_portefeuilles_et_watchlist(client):
    assert client.get("/auth/moi").json()["email"].endswith("@example.com")
    portefeuilles = client.get("/mes-portefeuilles").json()
    assert len(portefeuilles) == 1
    second = client.post("/mes-portefeuilles", json={"nom": "Long terme"})
    assert second.status_code == 200
    assert len(client.get("/mes-portefeuilles").json()) == 2
    assert client.put("/watchlist/BOAB").status_code == 200
    assert client.get("/watchlist").json() == ["BOAB"]
    assert client.delete("/watchlist/BOAB").status_code == 200
    assert client.get("/watchlist").json() == []


def test_renommer_et_supprimer_un_portefeuille(client):
    premier = client.get("/mes-portefeuilles").json()[0]
    assert client.delete(f"/mes-portefeuilles/{premier['id']}").status_code == 400

    second = client.post("/mes-portefeuilles", json={"nom": "Projet"}).json()
    renomme = client.put(f"/mes-portefeuilles/{second['id']}", json={"nom": "Projet long terme"})
    assert renomme.status_code == 200
    assert renomme.json()["nom"] == "Projet long terme"

    assert client.post(f"/portefeuille/especes?portefeuille_id={second['id']}", json={
        "type": "DEPOT", "montant": 100_000,
    }).status_code == 200
    assert client.post("/portefeuille/positions", json={
        "symbole": "BOAB", "quantite": 1, "portefeuille_id": second["id"],
    }).status_code == 200
    assert client.delete(f"/mes-portefeuilles/{second['id']}").status_code == 200
    assert client.get(f"/portefeuille?portefeuille_id={second['id']}").status_code == 404
    assert len(client.get("/mes-portefeuilles").json()) == 1


def test_portefeuilles_isoles(client):
    premier = client.get("/mes-portefeuilles").json()[0]["id"]
    second = client.post("/mes-portefeuilles", json={"nom": "Test isolé"}).json()["id"]
    assert client.post(f"/portefeuille/especes?portefeuille_id={second}", json={
        "type": "DEPOT", "montant": 100_000
    }).status_code == 200
    assert client.post("/portefeuille/positions", json={
        "symbole": "BOAB", "quantite": 2, "portefeuille_id": second
    }).status_code == 200
    assert client.get(f"/portefeuille?portefeuille_id={premier}").json()["positions"] == []
    assert client.get(f"/portefeuille?portefeuille_id={second}").json()["positions"][0]["quantite"] == 2


def test_routes_sensibles_exigent_authentification():
    from fastapi.testclient import TestClient
    from app.main import app
    anonyme = TestClient(app)
    assert anonyme.post("/refresh").status_code == 401
    assert anonyme.get("/alertes").status_code == 401
    assert anonyme.post("/alertes/evaluer").status_code == 401
    assert anonyme.get("/portefeuille").status_code == 401


def test_modifier_profil_et_mot_de_passe(client):
    email = client.get("/auth/moi").json()["email"]
    profil = client.put("/auth/profil", json={"nom": "Nouveau nom"})
    assert profil.status_code == 200
    assert profil.json()["nom"] == "Nouveau nom"

    assert client.post("/auth/mot-de-passe", json={
        "mot_de_passe_actuel": "incorrect",
        "nouveau_mot_de_passe": "nouveau-mot-de-passe-solide",
    }).status_code == 400
    changement = client.post("/auth/mot-de-passe", json={
        "mot_de_passe_actuel": "mot-de-passe-test-solide",
        "nouveau_mot_de_passe": "nouveau-mot-de-passe-solide",
    })
    assert changement.status_code == 200
    assert client.post("/auth/deconnexion").status_code == 200
    assert client.post("/auth/connexion", json={
        "email": email, "mot_de_passe": "mot-de-passe-test-solide",
    }).status_code == 401
    assert client.post("/auth/connexion", json={
        "email": email, "mot_de_passe": "nouveau-mot-de-passe-solide",
    }).status_code == 200


def test_refresh_reserve_administrateur(client):
    assert client.post("/refresh").status_code == 403


def test_alertes_isolees_entre_utilisateurs(client):
    alerte = client.post("/alertes", json={
        "symbole": "BOAB", "type": "cours_superieur", "seuil": 10000
    }).json()
    assert client.post("/auth/deconnexion").status_code == 200
    assert client.post("/auth/inscription", json={
        "email": f"second-{alerte['id']}@example.com",
        "mot_de_passe": "autre-mot-de-passe-solide",
        "nom": "Second",
    }).status_code == 200
    assert client.get("/alertes").json() == []
    assert client.delete(f"/alertes/{alerte['id']}").status_code == 404


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
    assert p["repartition_secteurs"] == [{
        "libelle": "Services financiers", "valeur": 87900.0, "pourcentage": 100.0
    }]
    assert p["repartition_pays"][0]["pourcentage"] == 100.0
    assert p["concentration_max_pct"] == 100.0
    assert p["indice_concentration"] == 10000.0
    assert p["performance_totale_pct"] == 0.0
    assert p["rendement_annualise"] is None
    assert p["volatilite_annualisee"] is None

    # Vente fictive -> portefeuille de nouveau vide
    assert client.delete(f"/portefeuille/positions/{position['id']}").status_code == 200
    assert client.get("/portefeuille").json()["positions"] == []


def test_tresorerie_depot_retrait_et_limites(client):
    portefeuille = client.get("/portefeuille").json()
    solde_initial = portefeuille["solde_especes"]
    assert portefeuille["valeur_globale"] == solde_initial

    depot = client.post("/portefeuille/especes", json={
        "type": "DEPOT", "montant": 50_000,
    })
    assert depot.status_code == 200
    assert depot.json()["solde_especes"] == solde_initial + 50_000

    retrait = client.post("/portefeuille/especes", json={
        "type": "RETRAIT", "montant": 20_000,
    })
    assert retrait.status_code == 200
    assert retrait.json()["solde_especes"] == solde_initial + 30_000
    journal = client.get("/portefeuille").json()["mouvements_especes"]
    assert journal[0]["type"] == "RETRAIT"
    assert journal[0]["montant"] == 20_000
    assert journal[0]["solde_apres"] == solde_initial + 30_000

    impossible = client.post("/portefeuille/especes", json={
        "type": "RETRAIT", "montant": solde_initial + 30_001,
    })
    assert impossible.status_code == 400
    assert "insuffisantes" in impossible.json()["detail"]


def test_achat_debite_et_vente_credite_les_liquidites(client):
    avant = client.get("/portefeuille").json()["solde_especes"]
    achat = client.post("/portefeuille/positions", json={
        "symbole": "BOAB", "quantite": 10, "frais_courtage_pct": 1,
    })
    assert achat.status_code == 200
    cout = 10 * 8790 * 1.01
    apres_achat = client.get("/portefeuille").json()
    assert apres_achat["solde_especes"] == pytest.approx(avant - cout)
    assert apres_achat["valeur_globale"] == pytest.approx(
        apres_achat["valeur_totale"] + apres_achat["solde_especes"]
    )

    position = achat.json()
    vente = client.post(f"/portefeuille/positions/{position['id']}/vendre", json={
        "quantite": 4, "frais_courtage_pct": 1, "fiscalite_pct": 0,
    })
    assert vente.status_code == 200
    produit_net = 4 * 8790 * 0.99
    assert client.get("/portefeuille").json()["solde_especes"] == pytest.approx(
        avant - cout + produit_net
    )


def test_achat_refuse_si_liquidites_insuffisantes(client):
    portefeuille_id = client.post("/mes-portefeuilles", json={
        "nom": "Sans liquidités"
    }).json()["id"]
    reponse = client.post("/portefeuille/positions", json={
        "symbole": "BOAB", "quantite": 1, "portefeuille_id": portefeuille_id,
    })
    assert reponse.status_code == 400
    assert "Liquidités insuffisantes" in reponse.json()["detail"]


def test_position_expose_la_source_du_dividende(client):
    position = client.post("/portefeuille/positions", json={
        "symbole": "BOAB", "quantite": 2,
    }).json()
    assert position["dividende_par_action"] == 585
    assert position["annee_dividende"] == 2025
    assert position["rendement_dividende_pct"] == pytest.approx(6.66)
    assert position["date_detachement_annoncee"] == "15/08/2026"
    assert position["dividende_donnee_ancienne"] is False
    assert position["dividende_potentiellement_exceptionnel"] is False


def test_statut_donnees_indique_date_et_couverture(client):
    statut = client.get("/donnees/statut")
    assert statut.status_code == 200
    resultat = statut.json()
    assert resultat["derniere_seance"] == "2026-07-10"
    assert resultat["actions_couvertes"] == 3
    assert resultat["actions_total"] == 3
    assert resultat["statut"] in {"a_jour", "a_verifier", "ancien"}


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


def test_prmp_vente_partielle_frais_et_export(client):
    achat = client.post("/portefeuille/positions", json={
        "symbole": "SNTS", "quantite": 10, "frais_courtage_pct": 1
    })
    assert achat.status_code == 200
    position = achat.json()
    assert position["prix_achat"] == 31209.0  # 30 900 + 1 % de frais
    vente = client.post(f"/portefeuille/positions/{position['id']}/vendre", json={
        "quantite": 5, "frais_courtage_pct": 1, "fiscalite_pct": 30
    })
    assert vente.status_code == 200
    assert vente.json()["gain_realise"] == -3090.0
    p = client.get("/portefeuille").json()
    snts = next(x for x in p["positions"] if x["symbole"] == "SNTS")
    assert snts["quantite"] == 5
    assert snts["prix_achat"] == 31209.0  # le PRMP ne change pas a la vente
    assert p["frais_totaux"] == 4635.0
    assert p["plus_value_realisee"] == -3090.0
    export = client.get("/portefeuille/export.csv")
    assert export.status_code == 200
    assert "journal-complet-brvm.csv" in export.headers["content-disposition"]
    assert "SNTS" in export.content.decode("utf-8-sig")
    assert "Trésorerie" in export.content.decode("utf-8-sig")
    assert client.delete(f"/portefeuille/positions/{snts['id']}").status_code == 200


def test_cycle_alerte_cours(client):
    creation = client.post("/alertes", json={
        "symbole": "BOAB", "type": "cours_inferieur", "seuil": 9000
    })
    assert creation.status_code == 200
    alerte = creation.json()
    assert alerte["symbole"] == "BOAB"
    evenements = client.post("/alertes/evaluer").json()
    assert any(e["alerte_id"] == alerte["id"] for e in evenements)
    # Pas de second evenement tant que le cours reste sous le seuil.
    assert len(client.post("/alertes/evaluer").json()) == len(evenements)
    assert client.delete(f"/alertes/{alerte['id']}").status_code == 200


def test_alerte_invalide(client):
    assert client.post("/alertes", json={
        "symbole": "BOAB", "type": "cours_superieur", "seuil": None
    }).status_code == 400
    assert client.post("/alertes", json={
        "symbole": "XXXX", "type": "detachement"
    }).status_code == 404
