"""
Scraper de la BRVM (Bourse Regionale des Valeurs Mobilieres).

Les cotations sont directement dans le HTML de la page officielle
https://www.brvm.org/fr/cours-actions/0 (pas de JavaScript).
On telecharge la page, on parse le tableau principal et on renvoie
une liste de dictionnaires, un par action.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

URL = "https://www.brvm.org/fr/cours-actions/0"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


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
    """Recupere la liste des actions cotees a la BRVM avec leurs cours.

    Retourne une liste de dicts :
    {symbole, nom, volume, cours_veille, cours_ouverture,
     cours_cloture, variation}
    """
    reponse = requests.get(URL, headers=HEADERS, timeout=30)
    reponse.raise_for_status()
    reponse.encoding = "utf-8"

    soup = BeautifulSoup(reponse.text, "lxml")

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
