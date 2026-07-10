"""Tables de la base : Societe (une action) et Cotation (un cours par jour)."""
from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
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


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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

    recupere_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    societe: Mapped["Societe"] = relationship(back_populates="cotations")


class IndiceCotation(Base):
    """Niveau de cloture quotidien d'un indice de reference BRVM."""

    __tablename__ = "indices_cotations"
    __table_args__ = (
        UniqueConstraint("code", "jour", name="uq_indice_code_jour"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, index=True)
    jour: Mapped[date] = mapped_column(Date, nullable=False)
    cloture: Mapped[float] = mapped_column(Float, nullable=False)
    variation: Mapped[float | None] = mapped_column(Float)


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


class Transaction(Base):
    """Achat ou vente fictive conservee dans le journal comptable."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbole: Mapped[str] = mapped_column(String, ForeignKey("societes.symbole"), index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # ACHAT | VENTE
    quantite: Mapped[int] = mapped_column(Integer, nullable=False)
    prix: Mapped[float] = mapped_column(Float, nullable=False)
    jour: Mapped[date] = mapped_column(Date, nullable=False)
    frais_courtage: Mapped[float] = mapped_column(Float, default=0)
    fiscalite: Mapped[float] = mapped_column(Float, default=0)
    montant_net: Mapped[float] = mapped_column(Float, nullable=False)
    gain_realise: Mapped[float | None] = mapped_column(Float)
    creee_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    portefeuille_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("portefeuilles_utilisateur.id"), index=True)


class Utilisateur(Base):
    __tablename__ = "utilisateurs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    nom: Mapped[str] = mapped_column(String, nullable=False)
    mot_de_passe_hash: Mapped[str] = mapped_column(String, nullable=False)
    sel: Mapped[str] = mapped_column(String, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PortefeuilleUtilisateur(Base):
    __tablename__ = "portefeuilles_utilisateur"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id"), index=True)
    nom: Mapped[str] = mapped_column(String, nullable=False)
    solde_especes: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MouvementEspeces(Base):
    """Dépôt ou retrait fictif de liquidités dans un portefeuille."""

    __tablename__ = "mouvements_especes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portefeuille_id: Mapped[int] = mapped_column(Integer, ForeignKey("portefeuilles_utilisateur.id"), index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # DEPOT | RETRAIT
    montant: Mapped[float] = mapped_column(Float, nullable=False)
    solde_apres: Mapped[float | None] = mapped_column(Float)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SessionUtilisateur(Base):
    __tablename__ = "sessions_utilisateur"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id"), index=True)
    jeton_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    expire_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FavoriUtilisateur(Base):
    __tablename__ = "favoris_utilisateur"
    __table_args__ = (UniqueConstraint("utilisateur_id", "symbole", name="uq_favori_utilisateur_symbole"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id"), index=True)
    symbole: Mapped[str] = mapped_column(String, ForeignKey("societes.symbole"))


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


class Alerte(Base):
    """Regle d'alerte persistante pour une action."""

    __tablename__ = "alertes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbole: Mapped[str] = mapped_column(String, ForeignKey("societes.symbole"), index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    seuil: Mapped[float | None] = mapped_column(Float)
    email: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    etat: Mapped[str | None] = mapped_column(String)
    creee_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    utilisateur_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("utilisateurs.id"), index=True)


class EvenementAlerte(Base):
    """Notification produite par une regle d'alerte."""

    __tablename__ = "evenements_alertes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alerte_id: Mapped[int] = mapped_column(Integer, ForeignKey("alertes.id"), index=True)
    titre: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    lue: Mapped[bool] = mapped_column(Boolean, default=False)
