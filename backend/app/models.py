"""Tables de la base : Societe (une action) et Cotation (un cours par jour)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Societe(Base):
    """Une entreprise cotee a la BRVM (identifiee par son symbole)."""

    __tablename__ = "societes"

    symbole: Mapped[str] = mapped_column(String, primary_key=True)
    nom: Mapped[str] = mapped_column(String, nullable=False)
    secteur: Mapped[str | None] = mapped_column(String)  # classification BRVM

    cotations: Mapped[list["Cotation"]] = relationship(
        back_populates="societe", cascade="all, delete-orphan"
    )


class Cotation(Base):
    """Le cours d'une action pour une journee donnee (l'historique)."""

    __tablename__ = "cotations"
    __table_args__ = (
        UniqueConstraint("symbole", "jour", name="uq_cotation_symbole_jour"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbole: Mapped[str] = mapped_column(ForeignKey("societes.symbole"))
    jour: Mapped[date] = mapped_column(Date, nullable=False)

    volume: Mapped[float | None] = mapped_column(Float)
    cours_veille: Mapped[float | None] = mapped_column(Float)
    cours_ouverture: Mapped[float | None] = mapped_column(Float)
    cours_cloture: Mapped[float | None] = mapped_column(Float)
    variation: Mapped[float | None] = mapped_column(Float)

    recupere_le: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    societe: Mapped["Societe"] = relationship(back_populates="cotations")


class Position(Base):
    """Ligne du portefeuille virtuel : un achat FICTIF d'actions.

    Aucun ordre reel n'est passe nulle part : c'est un simulateur pour
    apprendre a suivre un portefeuille dans le temps.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbole: Mapped[str] = mapped_column(
        String, ForeignKey("societes.symbole"), index=True
    )
    quantite: Mapped[int] = mapped_column(Integer, nullable=False)
    prix_achat: Mapped[float] = mapped_column(Float, nullable=False)  # FCFA
    jour_achat: Mapped[date] = mapped_column(Date, nullable=False)


class Dividende(Base):
    """Dividende verse par une societe pour une annee donnee (historique)."""

    __tablename__ = "dividendes"
    __table_args__ = (
        UniqueConstraint("symbole", "annee", name="uq_dividende_symbole_annee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbole: Mapped[str] = mapped_column(String, index=True)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    montant: Mapped[float | None] = mapped_column(Float)     # FCFA par action
    rendement: Mapped[float | None] = mapped_column(Float)   # % (source Sika)


class Detachement(Base):
    """Prochain detachement de dividende annonce pour une societe.

    Pour toucher le dividende, il faut detenir l'action AVANT cette date.
    """

    __tablename__ = "detachements"

    symbole: Mapped[str] = mapped_column(String, primary_key=True)
    date_detachement: Mapped[str] = mapped_column(String)  # '13/07/2026' ou 'A preciser'
    montant: Mapped[float | None] = mapped_column(Float)
    rendement: Mapped[float | None] = mapped_column(Float)
