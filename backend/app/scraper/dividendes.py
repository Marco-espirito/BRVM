"""
Scraper des dividendes BRVM depuis Sika Finance.

La page https://www.sikafinance.com/marches/dividendes contient :
  - un tableau "calendrier" (id=tbdDiv)  : les prochains detachements de
    dividendes (date, societe, montant, rendement)
  - un tableau "historique" (id=tblDiv2) : les dividendes verses par annee
    (Div. 2022, Rend. 2022, Div. 2023, ...)

Bonus precieux : chaque societe est un lien du type
/marches/cotation_BICB.bj -> on en extrait le symbole BRVM (BICB).
"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from .brvm import HEADERS, _to_float

URL = "https://www.sikafinance.com/marches/dividendes"

# /marches/cotation_BOABF.bf -> BOABF
_RE_SYMBOLE = re.compile(r"cotation_([A-Za-z0-9]+)\.")


def _symbole_depuis_ligne(tr) -> str | None:
    """Extrait le symbole BRVM du lien contenu dans une ligne de tableau."""
    lien = tr.find("a", href=True)
    if lien is None:
        return None
    m = _RE_SYMBOLE.search(lien["href"])
    return m.group(1).upper() if m else None


def fetch_dividendes() -> tuple[list[dict], list[dict]]:
    """Retourne (historique, prochains).

    historique : [{symbole, annee, montant, rendement}]  (un par annee connue)
    prochains  : [{symbole, date_detachement, montant, rendement}]
    """
    reponse = requests.get(URL, headers=HEADERS, timeout=30)
    reponse.raise_for_status()
    soup = BeautifulSoup(reponse.text, "lxml")

    # --- 1) Historique par annee (tblDiv2) -------------------------------
    historique: list[dict] = []
    table_hist = soup.find("table", id="tblDiv2")
    if table_hist is not None:
        lignes = table_hist.find_all("tr")
        # L'entete contient 'Div. 2022', 'Rend. 2022', ... -> on lit les annees
        entetes = [c.get_text(strip=True) for c in lignes[0].find_all(["th", "td"])]
        annees = [int(h.split()[-1]) for h in entetes if h.startswith("Div.")]

        for tr in lignes[1:]:
            symbole = _symbole_depuis_ligne(tr)
            if symbole is None:
                continue
            cellules = [td.get_text(strip=True) for td in tr.find_all("td")]
            # cellules = [nom, div_a1, rend_a1, div_a2, rend_a2, ...]
            valeurs = cellules[1:]
            for i, annee in enumerate(annees):
                montant = _to_float(valeurs[2 * i]) if 2 * i < len(valeurs) else None
                rendement = (
                    _to_float(valeurs[2 * i + 1]) if 2 * i + 1 < len(valeurs) else None
                )
                if montant is not None:
                    historique.append(
                        {
                            "symbole": symbole,
                            "annee": annee,
                            "montant": montant,
                            "rendement": rendement,
                        }
                    )

    # --- 2) Prochains detachements (tbdDiv) ------------------------------
    prochains: list[dict] = []
    table_cal = soup.find("table", id="tbdDiv")
    if table_cal is not None:
        for tr in table_cal.find_all("tr")[1:]:
            symbole = _symbole_depuis_ligne(tr)
            if symbole is None:
                continue
            cellules = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cellules) < 4:
                continue
            date_detachement, _nom, montant, rendement = cellules[:4]
            prochains.append(
                {
                    "symbole": symbole,
                    "date_detachement": date_detachement,
                    "montant": _to_float(montant),
                    "rendement": _to_float(rendement),
                }
            )

    return historique, prochains


if __name__ == "__main__":
    # Test rapide : python -m app.scraper.dividendes
    hist, proch = fetch_dividendes()
    print(f"{len(hist)} lignes d'historique, {len(proch)} prochains detachements\n")
    print("Exemples historique :")
    for h in hist[:6]:
        print("  ", h)
    print("Exemples prochains detachements :")
    for p in proch[:6]:
        print("  ", p)
