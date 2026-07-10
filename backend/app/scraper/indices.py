"""Scraping des indices de reference sur la page officielle BRVM."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .brvm import HEADERS, SESSION, _to_float

URL = "https://www.brvm.org/fr/indices"
NOMS = {
    "BRVM-30": "BRVM-30",
    "BRVM - COMPOSITE": "BRVM-COMPOSITE",
}


def fetch_indices() -> list[dict]:
    reponse = SESSION.get(URL, headers=HEADERS, timeout=30)
    reponse.raise_for_status()
    reponse.encoding = "utf-8"
    return parse_indices(reponse.text)


def parse_indices(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    resultat = []
    for ligne in soup.find_all("tr"):
        cellules = [c.get_text(" ", strip=True) for c in ligne.find_all("td")]
        if len(cellules) < 4 or cellules[0] not in NOMS:
            continue
        cloture = _to_float(cellules[2])
        if cloture is not None:
            resultat.append({
                "code": NOMS[cellules[0]],
                "cloture": cloture,
                "variation": _to_float(cellules[3]),
            })
    if len(resultat) != 2:
        raise RuntimeError("Indices BRVM-30 et BRVM Composite introuvables")
    return resultat
