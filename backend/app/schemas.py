"""Schemas Pydantic : la forme des reponses JSON de l'API."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CotationOut(BaseModel):
    jour: date
    volume: float | None
    cours_veille: float | None
    cours_ouverture: float | None
    cours_cloture: float | None
    variation: float | None

    class Config:
        from_attributes = True


class DividendeOut(BaseModel):
    annee: int
    montant: float | None
    rendement: float | None

    class Config:
        from_attributes = True


class DetachementOut(BaseModel):
    date_detachement: str
    montant: float | None
    rendement: float | None

    class Config:
        from_attributes = True


class ActionOut(BaseModel):
    """Une action avec sa derniere cotation connue (vue liste)."""

    symbole: str
    nom: str
    cours_cloture: float | None
    variation: float | None
    volume: float | None
    dernier_jour: date | None
    # Dividendes : dernier dividende annuel connu + rendement recalcule
    # sur le cours actuel (montant / cours * 100).
    dividende: float | None = None
    annee_dividende: int | None = None
    rendement: float | None = None
    # Pays d'origine (deduit du suffixe du symbole)
    pays: str | None = None
    # Liquidite : volume moyen sur l'historique + classement simple
    volume_moyen: float | None = None
    liquidite: str | None = None  # "haute" | "moyenne" | "faible"


class ActionDetailOut(BaseModel):
    """Une action avec tout son historique (vue detail + graphique)."""

    symbole: str
    nom: str
    historique: list[CotationOut]
    dividendes: list[DividendeOut] = []
    prochain_detachement: DetachementOut | None = None
