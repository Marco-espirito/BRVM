"""
Scraper des secteurs officiels de la BRVM.

La BRVM classe ses actions en 7 secteurs, chacun ayant sa propre page de
cotations (meme tableau que la page principale, filtre par secteur) :
https://www.brvm.org/fr/cours-actions/194 ... 200

On visite chaque page et on note quels symboles y figurent.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from .brvm import HEADERS

# id de page -> nom du secteur (classification officielle BRVM)
SECTEURS = {
    194: "Consommation de base",
    195: "Consommation discrétionnaire",
    196: "Énergie",
    197: "Industriels",
    198: "Services financiers",
    199: "Services publics",
    200: "Télécommunications",
}

URL_MODELE = "https://www.brvm.org/fr/cours-actions/{id}"


def _symboles_de_la_page(html: str) -> list[str]:
    """Extrait les symboles du tableau de cotations d'une page secteur."""
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        entetes = [th.get_text(strip=True) for th in table.find_all("th")]
        if entetes and entetes[0] == "Symbole":
            return [
                cellules[0].get_text(strip=True)
                for ligne in table.find_all("tr")
                if len(cellules := ligne.find_all("td")) >= 7
            ]
    return []


def fetch_secteurs() -> dict[str, str]:
    """Retourne {symbole: nom_du_secteur} pour toutes les actions cotees."""
    mapping: dict[str, str] = {}
    for page_id, nom_secteur in SECTEURS.items():
        reponse = requests.get(
            URL_MODELE.format(id=page_id), headers=HEADERS, timeout=30
        )
        reponse.raise_for_status()
        reponse.encoding = "utf-8"
        for symbole in _symboles_de_la_page(reponse.text):
            mapping[symbole] = nom_secteur
    return mapping


if __name__ == "__main__":
    # Test rapide : python -m app.scraper.secteurs
    data = fetch_secteurs()
    print(f"{len(data)} societes classees\n")
    par_secteur: dict[str, list[str]] = {}
    for symbole, secteur in data.items():
        par_secteur.setdefault(secteur, []).append(symbole)
    for secteur, symboles in sorted(par_secteur.items()):
        print(f"{secteur:32} ({len(symboles)}) : {', '.join(sorted(symboles))}")
