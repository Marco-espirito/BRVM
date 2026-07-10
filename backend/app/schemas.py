"""Schemas Pydantic : la forme des reponses JSON de l'API."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CotationOut(BaseModel):
    jour: date
    volume: float | None
    cours_veille: float | None
    cours_ouverture: float | None
    cours_cloture: float | None
    variation: float | None

    model_config = ConfigDict(from_attributes=True)


class DividendeOut(BaseModel):
    annee: int
    montant: float | None
    rendement: float | None

    model_config = ConfigDict(from_attributes=True)


class DetachementOut(BaseModel):
    date_detachement: str
    montant: float | None
    rendement: float | None

    model_config = ConfigDict(from_attributes=True)


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
    # Secteur officiel BRVM (Services financiers, Energie...)
    secteur: str | None = None
    # Liquidite : volume moyen sur l'historique + classement simple
    volume_moyen: float | None = None
    liquidite: str | None = None  # "haute" | "moyenne" | "faible"
    variation_30j: float | None = None
    regularite_dividende: str = "faible"
    annees_dividende_consecutives: int = 0


class StatutDonneesOut(BaseModel):
    derniere_seance: date | None = None
    recupere_le: datetime | None = None
    actions_couvertes: int = 0
    actions_total: int = 0
    age_jours: int | None = None
    statut: str = "indisponible"


class TopActionOut(BaseModel):
    """Une action classee par le score pedagogique du Top 10."""

    rang: int
    symbole: str
    nom: str
    pays: str | None
    secteur: str | None
    meilleur_du_secteur: bool = False
    cours_cloture: float | None
    rendement: float | None
    liquidite: str | None
    tendance_dividende: str | None
    score: float                 # sur 100
    raisons: list[str]           # explication du score, lisible


class AchatIn(BaseModel):
    """Achat fictif : le prix est celui du dernier cours connu."""

    symbole: str
    quantite: int
    frais_courtage_pct: float = 0
    portefeuille_id: int | None = None


class VenteIn(BaseModel):
    quantite: int
    frais_courtage_pct: float = 0
    fiscalite_pct: float = 0


class MouvementEspecesIn(BaseModel):
    type: str
    montant: float


class PositionOut(BaseModel):
    id: int
    symbole: str
    nom: str
    quantite: int
    prix_achat: float
    jour_achat: date
    cours_actuel: float | None
    investi: float                    # quantite x prix_achat
    valeur_actuelle: float | None     # quantite x cours actuel
    plus_value: float | None          # valeur - investi
    plus_value_pct: float | None
    dividende_annuel: float | None    # quantite x dernier dividende connu
    dividende_par_action: float | None = None
    annee_dividende: int | None = None
    rendement_dividende_pct: float | None = None
    date_detachement_annoncee: str | None = None
    dividende_donnee_ancienne: bool = False
    dividende_potentiellement_exceptionnel: bool = False
    secteur: str | None = None
    pays: str | None = None
    dividendes_recus: float = 0
    cout_base: float = 0


class TransactionOut(BaseModel):
    id: int
    symbole: str
    type: str
    quantite: int
    prix: float
    jour: date
    frais_courtage: float
    fiscalite: float
    montant_net: float
    gain_realise: float | None = None

    model_config = ConfigDict(from_attributes=True)


class MouvementEspecesOut(BaseModel):
    id: int
    type: str
    montant: float
    solde_apres: float | None = None
    cree_le: datetime

    model_config = ConfigDict(from_attributes=True)


class PointValeur(BaseModel):
    jour: date
    valeur: float


class RepartitionOut(BaseModel):
    libelle: str
    valeur: float
    pourcentage: float


class PointComparaisonPortefeuille(BaseModel):
    jour: date
    portefeuille: float | None = None
    indice: float | None = None


class PortefeuilleOut(BaseModel):
    positions: list[PositionOut]
    total_investi: float
    valeur_totale: float
    plus_value: float
    plus_value_pct: float | None
    dividendes_annuels: float
    historique: list[PointValeur]     # valeur totale jour par jour
    repartition_secteurs: list[RepartitionOut] = Field(default_factory=list)
    repartition_pays: list[RepartitionOut] = Field(default_factory=list)
    concentration_max_pct: float | None = None
    indice_concentration: float | None = None
    dividendes_recus: float = 0
    performance_totale: float = 0
    performance_totale_pct: float | None = None
    rendement_annualise: float | None = None
    volatilite_annualisee: float | None = None
    comparaison_indice: list[PointComparaisonPortefeuille] = Field(default_factory=list)
    indice_reference: str = "BRVM Composite"
    transactions: list[TransactionOut] = Field(default_factory=list)
    frais_totaux: float = 0
    fiscalite_totale: float = 0
    plus_value_realisee: float = 0
    plus_value_latente: float = 0
    solde_especes: float = 0
    valeur_globale: float = 0
    mouvements_especes: list[MouvementEspecesOut] = Field(default_factory=list)


class PerformanceOut(BaseModel):
    variation_7j: float | None = None
    variation_30j: float | None = None
    variation_6m: float | None = None
    variation_1a: float | None = None
    plus_haut_52s: float | None = None
    plus_bas_52s: float | None = None
    debut_52s: date | None = None
    fin_52s: date | None = None


class ComparaisonPointOut(BaseModel):
    jour: date
    action: float | None = None
    brvm_composite: float | None = None
    brvm_30: float | None = None


class PointTechniqueOut(BaseModel):
    jour: date
    cours: float
    moyenne_mobile_20: float | None = None
    moyenne_mobile_50: float | None = None


class IndicateursTechniquesOut(BaseModel):
    moyenne_mobile_20: float | None = None
    moyenne_mobile_50: float | None = None
    rsi_14: float | None = None
    volatilite_20: float | None = None
    volume_moyen_20: float | None = None
    points: list[PointTechniqueOut] = Field(default_factory=list)
    explications: list[str] = Field(default_factory=list)


class ActionDetailOut(BaseModel):
    """Une action avec tout son historique (vue detail + graphique)."""

    symbole: str
    nom: str
    historique: list[CotationOut]
    dividendes: list[DividendeOut] = Field(default_factory=list)
    prochain_detachement: DetachementOut | None = None
    performances: PerformanceOut
    comparaison_indices: list[ComparaisonPointOut] = Field(default_factory=list)
    indicateurs_techniques: IndicateursTechniquesOut


class AlerteIn(BaseModel):
    symbole: str
    type: str
    seuil: float | None = None
    email: str | None = None


class AlerteOut(AlerteIn):
    id: int
    active: bool
    creee_le: datetime

    model_config = ConfigDict(from_attributes=True)


class EvenementAlerteOut(BaseModel):
    id: int
    alerte_id: int
    titre: str
    message: str
    cree_le: datetime
    lue: bool

    model_config = ConfigDict(from_attributes=True)


class EvenementCalendrierOut(BaseModel):
    symbole: str
    nom: str
    date_detachement: date | None = None
    date_detachement_source: str
    date_paiement: date | None = None
    montant: float | None = None
    rendement: float | None = None
    quantite_portefeuille: int = 0
    revenu_estime: float = 0


class CalendrierDividendesOut(BaseModel):
    evenements: list[EvenementCalendrierOut]
    revenu_total_estime: float
    prochaine_date: date | None = None


class BacktestIn(BaseModel):
    date_depart: date
    capital: float = 1_000_000
    frais_pct: float = 1.0
    taille_panier: int = 5


class PointBacktestOut(BaseModel):
    jour: date
    valeur: float


class LigneBacktestOut(BaseModel):
    strategie: str
    description: str
    symboles: list[str]
    capital_initial: float
    montant_investi: float
    valeur_finale: float
    dividendes: float
    frais: float
    performance_pct: float
    points: list[PointBacktestOut]


class BacktestOut(BaseModel):
    date_depart_demandee: date
    date_depart_effective: date
    date_fin: date
    historique_disponible_depuis: date
    strategies: list[LigneBacktestOut]
    limites: list[str]


class CompteIn(BaseModel):
    email: str
    mot_de_passe: str
    nom: str = "Investisseur"


class ConnexionIn(BaseModel):
    email: str
    mot_de_passe: str


class UtilisateurOut(BaseModel):
    id: int
    email: str
    nom: str


class ProfilIn(BaseModel):
    nom: str


class ChangementMotDePasseIn(BaseModel):
    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str


class PortefeuilleUtilisateurIn(BaseModel):
    nom: str


class PortefeuilleUtilisateurOut(BaseModel):
    id: int
    nom: str
    cree_le: datetime

    model_config = ConfigDict(from_attributes=True)
