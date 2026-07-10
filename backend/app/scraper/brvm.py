"""
Scraper de la BRVM (Bourse Regionale des Valeurs Mobilieres).

Les cotations sont directement dans le HTML de la page officielle
https://www.brvm.org/fr/cours-actions/0 (pas de JavaScript).
On telecharge la page, on parse le tableau principal et on renvoie
une liste de dictionnaires, un par action.
"""
from __future__ import annotations

import requests
import re
import unicodedata
from datetime import date
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://www.brvm.org/fr/cours-actions/0"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
)))


def _to_float(texte: str) -> float | None:
    """'3 150' -> 3150.0  |  '1,59' -> 1.59  |  '' -> None

    La BRVM utilise l'espace (parfois insecable) comme separateur de
    milliers et la virgule comme separateur decimal.
    """
    if texte is None:
        return None
    nettoye = (
        texte.replace("\xa0", "")   # espace insecable
        .replace(" ", "")            # espace normal
        .replace("%", "")
        .replace(",", ".")           # virgule decimale -> point
        .strip()
    )
    if nettoye in ("", "-"):
        return None
    try:
        return float(nettoye)
    except ValueError:
        return None


def fetch_cotations() -> list[dict]:
    """Telecharge la page officielle et retourne les cotations parsees."""
    reponse = SESSION.get(URL, headers=HEADERS, timeout=30)
    reponse.raise_for_status()
    reponse.encoding = "utf-8"
    actions = parse_cotations(reponse.text)
    if len(actions) < 40:
        raise RuntimeError(f"Seulement {len(actions)} actions trouvées : ingestion annulée")
    return actions


def fetch_cotations_et_date() -> tuple[list[dict], date]:
    """Retourne les cours et la date de séance affichée par la BRVM."""
    reponse = SESSION.get(URL, headers=HEADERS, timeout=30)
    reponse.raise_for_status()
    reponse.encoding = "utf-8"
    actions = parse_cotations(reponse.text)
    if len(actions) < 40:
        raise RuntimeError(f"Seulement {len(actions)} actions trouvées : ingestion annulée")
    return actions, extraire_date_marche(reponse.text)


def extraire_date_marche(html: str) -> date:
    texte = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    normalise = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    zone = normalise[normalise.find("derniere mise a jour"):]
    mois = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
            "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
            "octobre": 10, "novembre": 11, "decembre": 12}
    motif = r"(\d{1,2})\s+(" + "|".join(mois) + r")\s*,?\s*(\d{4})"
    correspondance = re.search(motif, zone)
    if not correspondance:
        raise RuntimeError("Date de séance BRVM introuvable : aucune donnée ne sera datée artificiellement.")
    jour, nom_mois, annee = correspondance.groups()
    return date(int(annee), mois[nom_mois], int(jour))


def parse_cotations(html: str) -> list[dict]:
    """Parse le HTML de la page des cours et retourne les actions.

    Retourne une liste de dicts :
    {symbole, nom, volume, cours_veille, cours_ouverture,
     cours_cloture, variation}
    """
    soup = BeautifulSoup(html, "lxml")

    # Le bon tableau est celui dont les entetes commencent par "Symbole".
    table_actions = None
    for table in soup.find_all("table"):
        entetes = [th.get_text(strip=True) for th in table.find_all("th")]
        if entetes and entetes[0] == "Symbole":
            table_actions = table
            break

    if table_actions is None:
        raise RuntimeError(
            "Tableau des cotations introuvable : la structure de la page "
            "BRVM a peut-etre change."
        )

    actions: list[dict] = []
    for ligne in table_actions.find_all("tr"):
        cellules = [td.get_text(strip=True) for td in ligne.find_all("td")]
        if len(cellules) < 7:
            continue  # ligne d'entete ou ligne vide
        symbole, nom, volume, veille, ouverture, cloture, variation = cellules[:7]
        actions.append(
            {
                "symbole": symbole,
                "nom": nom,
                "volume": _to_float(volume),
                "cours_veille": _to_float(veille),
                "cours_ouverture": _to_float(ouverture),
                "cours_cloture": _to_float(cloture),
                "variation": _to_float(variation),
            }
        )
    return actions


if __name__ == "__main__":
    # Test rapide : python -m app.scraper.brvm
    data = fetch_cotations()
    print(f"{len(data)} actions recuperees\n")
    for a in data[:10]:
        print(
            f"{a['symbole']:6} {a['nom'][:35]:35} "
            f"cloture={a['cours_cloture']:>10} var={a['variation']}%"
        )
