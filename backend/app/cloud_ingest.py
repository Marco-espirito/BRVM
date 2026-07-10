"""Scraping 'cloud' : recupere tout et ecrit des JSON dans data/ (racine du
repo). Concu pour tourner dans le cron GitHub Actions, qui committe ensuite
les fichiers — le depot devient la memoire du projet, plus besoin d'un PC
allume ('git scraping').

    python -m app.cloud_ingest

Fichiers produits :
  data/cotations/YYYY-MM-DD.json  (un par jour de bourse)
  data/dividendes.json            (historique + prochains detachements)
  data/secteurs.json              (mapping symbole -> secteur)
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .scraper.brvm import fetch_cotations_et_date
from .scraper.indices import fetch_indices
from .scraper.dividendes import fetch_dividendes
from .scraper.secteurs import fetch_secteurs

# <repo>/backend/app/cloud_ingest.py -> <repo>/data
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    temporaire.replace(chemin)


def exporter_tout(data_dir: Path = DATA_DIR, jour: date | None = None) -> dict:
    """Scrape cotations + dividendes + secteurs et ecrit les JSON."""
    actions, jour_marche = fetch_cotations_et_date()
    jour = jour or jour_marche
    indices = fetch_indices()
    _ecrire(
        data_dir / "cotations" / f"{jour.isoformat()}.json",
        {"jour": jour.isoformat(), "actions": actions, "indices": indices},
    )

    historique, prochains = fetch_dividendes()
    _ecrire(
        data_dir / "dividendes.json",
        {"historique": historique, "prochains": prochains},
    )

    fichier_secteurs = data_dir / "secteurs.json"
    if not fichier_secteurs.exists() or jour.weekday() == 0:
        secteurs = fetch_secteurs()
        _ecrire(fichier_secteurs, secteurs)
    else:
        secteurs = json.loads(fichier_secteurs.read_text(encoding="utf-8"))

    return {
        "jour": jour.isoformat(),
        "cotations": len(actions),
        "indices": len(indices),
        "dividendes": len(historique),
        "detachements": len(prochains),
        "secteurs": len(secteurs),
    }


if __name__ == "__main__":
    bilan = exporter_tout()
    print(
        f"[{bilan['jour']}] {bilan['cotations']} cotations, "
        f"{bilan['dividendes']} dividendes, {bilan['detachements']} detachements, "
        f"{bilan['secteurs']} secteurs -> {DATA_DIR}"
    )
