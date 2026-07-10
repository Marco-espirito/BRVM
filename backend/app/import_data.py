"""Importe dans la base locale les JSON commites par le cron GitHub Actions.

    git pull
    python -m app.import_data

Idempotent : tout est en upsert, on peut relancer sans creer de doublons.
Typiquement utile quand le PC est reste eteint plusieurs jours : le cloud a
continue de scraper, l'import rattrape l'historique manquant d'un coup.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .cloud_ingest import DATA_DIR
from .ingest import stocker_cotations, stocker_dividendes, stocker_indices, stocker_secteurs


def importer_tout(data_dir: Path = DATA_DIR) -> dict:
    """Lit data/ et remplit la base locale. Retourne un petit bilan."""
    bilan = {"jours_importes": 0, "cotations": 0, "dividendes": 0, "secteurs": 0}

    # 1) Cotations : un fichier par jour de bourse, dans l'ordre chronologique
    for fichier in sorted((data_dir / "cotations").glob("*.json")):
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        nb = stocker_cotations(
            contenu["actions"], date.fromisoformat(contenu["jour"])
        )
        bilan["jours_importes"] += 1
        bilan["cotations"] += nb
        if contenu.get("indices"):
            stocker_indices(contenu["indices"], date.fromisoformat(contenu["jour"]))

    # 2) Dividendes + prochains detachements
    fichier_div = data_dir / "dividendes.json"
    if fichier_div.exists():
        contenu = json.loads(fichier_div.read_text(encoding="utf-8"))
        nb_hist, _ = stocker_dividendes(contenu["historique"], contenu["prochains"])
        bilan["dividendes"] = nb_hist

    # 3) Secteurs
    fichier_secteurs = data_dir / "secteurs.json"
    if fichier_secteurs.exists():
        mapping = json.loads(fichier_secteurs.read_text(encoding="utf-8"))
        bilan["secteurs"] = stocker_secteurs(mapping)

    return bilan


if __name__ == "__main__":
    b = importer_tout()
    print(
        f"{b['jours_importes']} jour(s) de cotations importes "
        f"({b['cotations']} lignes), {b['dividendes']} dividendes, "
        f"{b['secteurs']} societes classees par secteur"
    )
