"""API FastAPI du BRVM Explorer.

Routes :
  GET /              -> petit message de sante
  POST /refresh      -> scrape la BRVM et enregistre les cotations du jour
  GET /actions       -> liste des actions avec leur dernier cours
  GET /actions/{sym} -> detail d'une action + historique (pour le graphique)
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import time
from contextlib import asynccontextmanager
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import stdev

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import SessionLocal, get_db
from .ingest import (creer_tables, enregistrer_cotations, enregistrer_dividendes,
                     enregistrer_indices)
from .alertes import TYPES, TYPES_SEUIL, evaluer_alertes, initialiser_alerte
from .auth import COOKIE, creer_session, hacher_mot_de_passe, supprimer_session, utilisateur_courant, verifier_mot_de_passe
from .models import (Alerte, Cotation, Detachement, Dividende, EvenementAlerte,
                     FavoriUtilisateur, IndiceCotation, PortefeuilleUtilisateur,
                     MouvementEspeces, SessionUtilisateur, Societe, Transaction, Utilisateur)
from .schemas import (
    AchatIn,
    AlerteIn,
    AlerteOut,
    ActionDetailOut,
    ActionOut,
    CotationOut,
    DetachementOut,
    DividendeOut,
    EvenementAlerteOut,
    EvenementCalendrierOut,
    CalendrierDividendesOut,
    BacktestIn,
    BacktestOut,
    LigneBacktestOut,
    PointBacktestOut,
    CompteIn,
    ConnexionIn,
    UtilisateurOut,
    PortefeuilleUtilisateurIn,
    PortefeuilleUtilisateurOut,
    ComparaisonPointOut,
    PerformanceOut,
    PointTechniqueOut,
    IndicateursTechniquesOut,
    PointValeur,
    PointComparaisonPortefeuille,
    RepartitionOut,
    PortefeuilleOut,
    PositionOut,
    TopActionOut,
    TransactionOut,
    VenteIn,
    MouvementEspecesIn,
    MouvementEspecesOut,
    StatutDonneesOut,
    ProfilIn,
    ChangementMotDePasseIn,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    creer_tables()
    yield


app = FastAPI(title="BRVM Explorer", version="0.2.0", lifespan=lifespan)


@app.get("/donnees/statut", response_model=StatutDonneesOut)
def statut_donnees(db: Session = Depends(get_db)):
    """Fraîcheur et couverture du dernier jeu de cotations enregistré."""
    derniere_seance = db.query(func.max(Cotation.jour)).scalar()
    total = db.query(func.count(Societe.symbole)).scalar() or 0
    if derniere_seance is None:
        return StatutDonneesOut(actions_total=total)
    couvertes = db.query(func.count(func.distinct(Cotation.symbole))).filter(
        Cotation.jour == derniere_seance
    ).scalar() or 0
    recupere_le = db.query(func.max(Cotation.recupere_le)).filter(
        Cotation.jour == derniere_seance
    ).scalar()
    age = max((date.today() - derniere_seance).days, 0)
    couverture_complete = total == 0 or couvertes / total >= 0.9
    statut = "a_jour" if age <= 3 and couverture_complete else "a_verifier" if age <= 7 else "ancien"
    return StatutDonneesOut(
        derniere_seance=derniere_seance, recupere_le=recupere_le,
        actions_couvertes=couvertes, actions_total=total,
        age_jours=age, statut=statut,
    )

# Le suffixe du symbole BRVM indique le pays d'origine de la societe :
# BOAC = BOA Cote d'Ivoire, BOAS = BOA Senegal, ONTBF = Onatel Burkina...
_PAYS_SUFFIXE = {
    "BF": "Burkina Faso",
    "C": "Côte d'Ivoire",
    "B": "Bénin",
    "S": "Sénégal",
    "M": "Mali",
    "N": "Niger",
    "T": "Togo",
}
_ECHECS_CONNEXION: dict[str, list[float]] = {}


def pays_depuis_symbole(symbole: str) -> str:
    if symbole.endswith("BF"):  # suffixe 2 lettres, a tester en premier
        return _PAYS_SUFFIXE["BF"]
    return _PAYS_SUFFIXE.get(symbole[-1], "Autre")


def classer_liquidite(volume_moyen: float | None) -> str | None:
    """Classement simple base sur le volume moyen quotidien echange."""
    if volume_moyen is None:
        return None
    if volume_moyen >= 1000:
        return "haute"
    if volume_moyen >= 100:
        return "moyenne"
    return "faible"


def _annees_consecutives(annees: list[int]) -> int:
    if not annees:
        return 0
    uniques = sorted(set(annees), reverse=True)
    total = 1
    for recente, ancienne in zip(uniques, uniques[1:]):
        if recente - ancienne != 1:
            break
        total += 1
    return total

# Autorise le front React a appeler l'API. Vite prend 5173 par defaut mais
# bascule sur 5174/5175... si le port est occupe : on tolere tous les ports
# de localhost (app locale uniquement, aucun risque).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origine.strip() for origine in os.getenv(
        "BRVM_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origine.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.get("/")
def racine():
    return {"message": "BRVM Explorer API. Voir /docs pour la documentation."}


@app.post("/auth/inscription", response_model=UtilisateurOut)
def inscription(entree: CompteIn, response: Response, db: Session = Depends(get_db)):
    email = entree.email.strip().lower()
    if "@" not in email or not 10 <= len(entree.mot_de_passe) <= 128:
        raise HTTPException(status_code=400, detail="E-mail invalide ou mot de passe inférieur à 10 caractères")
    if db.query(Utilisateur).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Ce compte existe déjà")
    import secrets
    sel = secrets.token_hex(16)
    utilisateur = Utilisateur(email=email, nom=entree.nom.strip() or "Investisseur",
                              sel=sel, mot_de_passe_hash=hacher_mot_de_passe(entree.mot_de_passe, sel))
    db.add(utilisateur); db.flush()
    portefeuille = PortefeuilleUtilisateur(utilisateur_id=utilisateur.id, nom="Mon portefeuille")
    db.add(portefeuille); db.flush()
    # Le premier compte local recupere les transactions historiques non attribuees.
    if os.getenv("BRVM_CLAIM_LEGACY_DATA", "0") == "1" and db.query(Utilisateur).count() == 1:
        db.query(Transaction).filter(Transaction.portefeuille_id.is_(None)).update({"portefeuille_id": portefeuille.id})
        db.query(Alerte).filter(Alerte.utilisateur_id.is_(None)).update({"utilisateur_id": utilisateur.id})
    db.commit(); creer_session(db, utilisateur, response)
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@app.post("/auth/connexion", response_model=UtilisateurOut)
def connexion(entree: ConnexionIn, response: Response, db: Session = Depends(get_db)):
    if not 1 <= len(entree.mot_de_passe) <= 128:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    email = entree.email.strip().lower()
    maintenant = time.monotonic()
    echecs = [instant for instant in _ECHECS_CONNEXION.get(email, []) if maintenant - instant < 900]
    _ECHECS_CONNEXION[email] = echecs
    if len(echecs) >= 5:
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessaie dans 15 minutes.")
    utilisateur = db.query(Utilisateur).filter_by(email=email).first()
    if utilisateur is None:
        hacher_mot_de_passe(entree.mot_de_passe, "00" * 16)
        echecs.append(maintenant)
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    if not verifier_mot_de_passe(entree.mot_de_passe, utilisateur):
        echecs.append(maintenant)
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    _ECHECS_CONNEXION.pop(email, None)
    creer_session(db, utilisateur, response)
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@app.post("/auth/deconnexion")
def deconnexion(response: Response, utilisateur: Utilisateur = Depends(utilisateur_courant),
                brvm_session: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    supprimer_session(db, brvm_session, response)
    return {"deconnecte": True}


@app.get("/auth/moi", response_model=UtilisateurOut)
def moi(utilisateur: Utilisateur = Depends(utilisateur_courant)):
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@app.put("/auth/profil", response_model=UtilisateurOut)
def modifier_profil(entree: ProfilIn,
                    utilisateur: Utilisateur = Depends(utilisateur_courant),
                    db: Session = Depends(get_db)):
    nom = entree.nom.strip()
    if not nom or len(nom) > 100:
        raise HTTPException(status_code=400, detail="Nom invalide")
    utilisateur.nom = nom
    db.commit(); db.refresh(utilisateur)
    return UtilisateurOut(id=utilisateur.id, email=utilisateur.email, nom=utilisateur.nom)


@app.post("/auth/mot-de-passe")
def changer_mot_de_passe(entree: ChangementMotDePasseIn,
                         utilisateur: Utilisateur = Depends(utilisateur_courant),
                         brvm_session: str | None = Cookie(default=None),
                         db: Session = Depends(get_db)):
    if not verifier_mot_de_passe(entree.mot_de_passe_actuel, utilisateur):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if not 10 <= len(entree.nouveau_mot_de_passe) <= 128:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit contenir au moins 10 caractères")
    import secrets
    utilisateur.sel = secrets.token_hex(16)
    utilisateur.mot_de_passe_hash = hacher_mot_de_passe(entree.nouveau_mot_de_passe, utilisateur.sel)
    jeton_courant = hashlib.sha256(brvm_session.encode()).hexdigest() if brvm_session else None
    requete = db.query(SessionUtilisateur).filter_by(utilisateur_id=utilisateur.id)
    if jeton_courant:
        requete = requete.filter(SessionUtilisateur.jeton_hash != jeton_courant)
    requete.delete(synchronize_session=False)
    db.commit()
    return {"modifie": True, "autres_sessions_revoquees": True}


@app.get("/mes-portefeuilles", response_model=list[PortefeuilleUtilisateurOut])
def mes_portefeuilles(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    return db.query(PortefeuilleUtilisateur).filter_by(utilisateur_id=utilisateur.id).order_by(PortefeuilleUtilisateur.cree_le).all()


@app.post("/mes-portefeuilles", response_model=PortefeuilleUtilisateurOut)
def creer_portefeuille(entree: PortefeuilleUtilisateurIn, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    if not entree.nom.strip(): raise HTTPException(status_code=400, detail="Nom requis")
    p = PortefeuilleUtilisateur(utilisateur_id=utilisateur.id, nom=entree.nom.strip())
    db.add(p); db.commit(); db.refresh(p); return p


@app.put("/mes-portefeuilles/{portefeuille_id}", response_model=PortefeuilleUtilisateurOut)
def renommer_portefeuille(portefeuille_id: int, entree: PortefeuilleUtilisateurIn,
                          utilisateur: Utilisateur = Depends(utilisateur_courant),
                          db: Session = Depends(get_db)):
    portefeuille = _selection_portefeuille(db, utilisateur, portefeuille_id)
    nom = entree.nom.strip()
    if not nom:
        raise HTTPException(status_code=400, detail="Nom requis")
    portefeuille.nom = nom
    db.commit(); db.refresh(portefeuille)
    return portefeuille


@app.delete("/mes-portefeuilles/{portefeuille_id}")
def supprimer_portefeuille(portefeuille_id: int,
                           utilisateur: Utilisateur = Depends(utilisateur_courant),
                           db: Session = Depends(get_db)):
    portefeuille = _selection_portefeuille(db, utilisateur, portefeuille_id)
    nombre = db.query(PortefeuilleUtilisateur).filter_by(utilisateur_id=utilisateur.id).count()
    if nombre <= 1:
        raise HTTPException(status_code=400, detail="Le dernier portefeuille ne peut pas être supprimé")
    db.query(Transaction).filter_by(portefeuille_id=portefeuille.id).delete()
    db.query(MouvementEspeces).filter_by(portefeuille_id=portefeuille.id).delete()
    db.delete(portefeuille)
    db.commit()
    return {"supprime": portefeuille_id}


@app.get("/watchlist", response_model=list[str])
def watchlist(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    return [f.symbole for f in db.query(FavoriUtilisateur).filter_by(utilisateur_id=utilisateur.id).all()]


@app.put("/watchlist/{symbole}")
def ajouter_favori(symbole: str, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    symbole = symbole.upper()
    if not db.get(Societe, symbole): raise HTTPException(status_code=404, detail="Action introuvable")
    if not db.query(FavoriUtilisateur).filter_by(utilisateur_id=utilisateur.id, symbole=symbole).first():
        db.add(FavoriUtilisateur(utilisateur_id=utilisateur.id, symbole=symbole)); db.commit()
    return {"ajoute": symbole}


@app.delete("/watchlist/{symbole}")
def retirer_favori(symbole: str, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    db.query(FavoriUtilisateur).filter_by(utilisateur_id=utilisateur.id, symbole=symbole.upper()).delete(); db.commit()
    return {"retire": symbole.upper()}


@app.post("/refresh")
def refresh(utilisateur: Utilisateur = Depends(utilisateur_courant)):
    """Declenche un scraping : cotations du jour + dividendes."""
    administrateurs = {e.strip().lower() for e in os.getenv("BRVM_ADMIN_EMAILS", "").split(",") if e.strip()}
    if os.getenv("BRVM_ALLOW_USER_REFRESH", "0") != "1" and utilisateur.email not in administrateurs:
        raise HTTPException(status_code=403, detail="Rafraîchissement réservé à l'administrateur")
    n = enregistrer_cotations()
    nb_indices = enregistrer_indices()
    nb_hist, nb_proch = enregistrer_dividendes()
    db = SessionLocal()
    try:
        nb_alertes = len(evaluer_alertes(db))
    finally:
        db.close()
    return {
        "actions_enregistrees": n,
        "indices_enregistres": nb_indices,
        "dividendes_historique": nb_hist,
        "detachements_a_venir": nb_proch,
        "alertes_declenchees": nb_alertes,
    }


@app.get("/alertes", response_model=list[AlerteOut])
def liste_alertes(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    return db.query(Alerte).filter_by(utilisateur_id=utilisateur.id).order_by(Alerte.creee_le.desc()).all()


@app.post("/alertes", response_model=AlerteOut)
def creer_alerte(entree: AlerteIn, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    symbole = entree.symbole.upper()
    if db.get(Societe, symbole) is None:
        raise HTTPException(status_code=404, detail="Action introuvable")
    if entree.type not in TYPES:
        raise HTTPException(status_code=400, detail="Type d'alerte invalide")
    if entree.type in TYPES_SEUIL and (entree.seuil is None or entree.seuil <= 0):
        raise HTTPException(status_code=400, detail="Seuil positif requis")
    if entree.email and ("@" not in entree.email or len(entree.email) > 254):
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide")
    alerte = Alerte(symbole=symbole, type=entree.type, seuil=entree.seuil,
                    email=entree.email.strip() if entree.email else None, active=True,
                    utilisateur_id=utilisateur.id)
    db.add(alerte)
    db.flush()
    initialiser_alerte(db, alerte)
    db.commit()
    db.refresh(alerte)
    return alerte


@app.delete("/alertes/{alerte_id}")
def supprimer_alerte(alerte_id: int, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    alerte = db.query(Alerte).filter_by(id=alerte_id, utilisateur_id=utilisateur.id).first()
    if alerte is None:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    db.query(EvenementAlerte).filter_by(alerte_id=alerte_id).delete()
    db.delete(alerte)
    db.commit()
    return {"supprimee": alerte_id}


@app.post("/alertes/evaluer", response_model=list[EvenementAlerteOut])
def verifier_alertes(utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    evaluer_alertes(db, utilisateur.id)
    return (db.query(EvenementAlerte).join(Alerte, Alerte.id == EvenementAlerte.alerte_id)
            .filter(Alerte.utilisateur_id == utilisateur.id, EvenementAlerte.lue.is_(False))
            .order_by(EvenementAlerte.cree_le).all())


@app.post("/alertes/evenements/{evenement_id}/lire")
def marquer_evenement_lu(evenement_id: int, utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    evenement = (db.query(EvenementAlerte).join(Alerte, Alerte.id == EvenementAlerte.alerte_id)
                 .filter(EvenementAlerte.id == evenement_id, Alerte.utilisateur_id == utilisateur.id).first())
    if evenement is None:
        raise HTTPException(status_code=404, detail="Notification introuvable")
    evenement.lue = True
    db.commit()
    return {"lue": evenement_id}


@app.get("/dividendes/calendrier", response_model=CalendrierDividendesOut)
def calendrier_dividendes(portefeuille_id: int | None = None,
                          utilisateur: Utilisateur = Depends(utilisateur_courant),
                          db: Session = Depends(get_db)):
    portefeuille_actif = _selection_portefeuille(db, utilisateur, portefeuille_id)
    quantites = {p.symbole: p.quantite for p in _positions_out(db, portefeuille_actif.id)}
    evenements = []
    for d in db.query(Detachement).all():
        societe = db.get(Societe, d.symbole)
        try:
            jour = datetime.strptime(d.date_detachement, "%d/%m/%Y").date()
        except (ValueError, TypeError):
            jour = None
        quantite = quantites.get(d.symbole, 0)
        evenements.append(EvenementCalendrierOut(
            symbole=d.symbole, nom=societe.nom if societe else d.symbole,
            date_detachement=jour, date_detachement_source=d.date_detachement,
            date_paiement=None, montant=d.montant, rendement=d.rendement,
            quantite_portefeuille=quantite,
            revenu_estime=quantite * (d.montant or 0),
        ))
    evenements.sort(key=lambda e: (e.date_detachement is None, e.date_detachement or date.max))
    dates_futures = [e.date_detachement for e in evenements if e.date_detachement and e.date_detachement >= date.today()]
    return CalendrierDividendesOut(
        evenements=evenements,
        revenu_total_estime=sum(e.revenu_estime for e in evenements),
        prochaine_date=min(dates_futures) if dates_futures else None,
    )


@app.post("/backtest", response_model=BacktestOut)
def backtester(entree: BacktestIn, db: Session = Depends(get_db)):
    if entree.capital <= 0 or not 0 <= entree.frais_pct <= 100:
        raise HTTPException(status_code=400, detail="Capital ou frais invalides")
    taille = max(2, min(entree.taille_panier, 10))
    premiere = db.query(func.min(Cotation.jour)).scalar()
    derniere = db.query(func.max(Cotation.jour)).scalar()
    if not premiere or not derniere:
        raise HTTPException(status_code=400, detail="Aucun historique disponible")
    depart = db.query(func.min(Cotation.jour)).filter(Cotation.jour >= entree.date_depart).scalar()
    if depart is None or depart >= derniere:
        raise HTTPException(status_code=400, detail="La date doit précéder la dernière séance disponible")

    candidats = _candidats_backtest(db, depart)
    if len(candidats) < 2:
        raise HTTPException(status_code=400, detail="Pas assez d'actions cotées à cette date")
    rendement = sorted(candidats, key=lambda c: -c["rendement"])[:taille]
    score = sorted(candidats, key=lambda c: -c["score"])[:taille]
    diversification = []
    secteurs = set()
    for c in sorted(candidats, key=lambda c: -c["score"]):
        secteur = c["secteur"] or "Non classé"
        if secteur not in secteurs:
            diversification.append(c); secteurs.add(secteur)
        if len(diversification) >= taille:
            break
    for c in sorted(candidats, key=lambda c: -c["score"]):
        if len(diversification) >= taille: break
        if c not in diversification: diversification.append(c)

    definitions = [
        ("Rendement", "Meilleurs rendements estimés à la date de départ", rendement),
        ("Score", "Rendement, liquidité et historique du dividende", score),
        ("Diversification", "Meilleur score de chaque secteur avant complément", diversification),
    ]
    lignes = [_simuler_backtest(db, nom, description, panier, depart, derniere,
                                entree.capital, entree.frais_pct)
              for nom, description, panier in definitions]
    return BacktestOut(
        date_depart_demandee=entree.date_depart, date_depart_effective=depart,
        date_fin=derniere, historique_disponible_depuis=premiere, strategies=lignes,
        limites=[
            "L'historique commence seulement à la première date collectée par l'application.",
            "Les dividendes sont rattachés à leur exercice, faute de date historique exacte de paiement.",
            "Les achats et la vente finale utilisent les cours de clôture, sans carnet d'ordres ni glissement.",
            "Les stratégies n'utilisent que les dividendes antérieurs au départ, mais les résultats passés ne prédisent pas les résultats futurs.",
        ],
    )


def _candidats_backtest(db: Session, depart: date) -> list[dict]:
    resultat = []
    societes = db.query(Societe).all()
    for s in societes:
        cours = db.query(Cotation).filter(Cotation.symbole == s.symbole, Cotation.jour == depart,
                                          Cotation.cours_cloture.isnot(None)).first()
        if not cours or not cours.cours_cloture:
            continue
        divs = db.query(Dividende).filter(Dividende.symbole == s.symbole,
            Dividende.annee < depart.year, Dividende.montant.isnot(None)).order_by(Dividende.annee).all()
        dernier_div = divs[-1].montant if divs else 0
        rendement = dernier_div / cours.cours_cloture * 100
        volume = db.query(func.avg(Cotation.volume)).filter(
            Cotation.symbole == s.symbole, Cotation.jour <= depart).scalar() or 0
        liquidite = 30 if volume >= 1000 else 15 if volume >= 100 else 0
        consecutives = _annees_consecutives([d.annee for d in divs])
        regularite = min(consecutives, 4) / 4 * 30
        rendement_pts = min(rendement, 8) / 8 * 40 if rendement <= 15 else 10
        resultat.append({"symbole": s.symbole, "secteur": s.secteur,
                         "cours": cours.cours_cloture, "rendement": rendement,
                         "score": rendement_pts + liquidite + regularite})
    return resultat


def _simuler_backtest(db: Session, nom: str, description: str, panier: list[dict],
                      depart: date, fin: date, capital: float, frais_pct: float) -> LigneBacktestOut:
    allocation = capital / len(panier)
    positions, cash, frais_achat = {}, capital, 0.0
    for c in panier:
        cout_unitaire = c["cours"] * (1 + frais_pct / 100)
        quantite = int(allocation // cout_unitaire)
        brut, frais = quantite * c["cours"], quantite * c["cours"] * frais_pct / 100
        positions[c["symbole"]] = quantite
        cash -= brut + frais
        frais_achat += frais
    cotations = db.query(Cotation).filter(Cotation.symbole.in_(positions),
        Cotation.jour >= depart, Cotation.jour <= fin).order_by(Cotation.jour).all()
    jours = sorted({c.jour for c in cotations})
    cours_jour = {(c.symbole, c.jour): c.cours_cloture for c in cotations if c.cours_cloture}
    derniers = {}
    dividendes_par_annee = {}
    for d in db.query(Dividende).filter(Dividende.symbole.in_(positions),
            Dividende.annee >= depart.year, Dividende.annee <= fin.year,
            Dividende.montant.isnot(None)).all():
        dividendes_par_annee.setdefault(d.annee, 0)
        dividendes_par_annee[d.annee] += positions[d.symbole] * d.montant
    points, dividendes_cumules, annee_precedente = [], 0.0, depart.year
    for jour in jours:
        for symbole in positions:
            if (symbole, jour) in cours_jour: derniers[symbole] = cours_jour[(symbole, jour)]
        if jour.year > annee_precedente:
            dividendes_cumules += dividendes_par_annee.get(annee_precedente, 0)
            annee_precedente = jour.year
        valeur = cash + dividendes_cumules + sum(q * derniers.get(s, next(c["cours"] for c in panier if c["symbole"] == s)) for s, q in positions.items())
        points.append(PointBacktestOut(jour=jour, valeur=round(valeur, 2)))
    dividendes_cumules += dividendes_par_annee.get(fin.year, 0)
    valeur_titres = sum(q * derniers.get(s, 0) for s, q in positions.items())
    frais_vente = valeur_titres * frais_pct / 100
    final = cash + dividendes_cumules + valeur_titres - frais_vente
    return LigneBacktestOut(
        strategie=nom, description=description, symboles=list(positions),
        capital_initial=capital, montant_investi=capital - cash,
        valeur_finale=round(final, 2), dividendes=round(dividendes_cumules, 2),
        frais=round(frais_achat + frais_vente, 2),
        performance_pct=round((final / capital - 1) * 100, 2), points=points,
    )


@app.get("/actions", response_model=list[ActionOut])
def liste_actions(db: Session = Depends(get_db)):
    """Toutes les actions avec leur cotation la plus recente."""
    # Pour chaque symbole, on cherche le jour le plus recent.
    dernier_jour = (
        db.query(Cotation.symbole, func.max(Cotation.jour).label("jour"))
        .group_by(Cotation.symbole)
        .subquery()
    )
    lignes = (
        db.query(Societe, Cotation)
        .join(Cotation, Cotation.symbole == Societe.symbole)
        .join(
            dernier_jour,
            (Cotation.symbole == dernier_jour.c.symbole)
            & (Cotation.jour == dernier_jour.c.jour),
        )
        .order_by(Societe.symbole)
        .all()
    )

    # Dernier dividende connu par societe (annee la plus recente avec montant)
    derniers_dividendes: dict[str, Dividende] = {}
    for d in db.query(Dividende).order_by(Dividende.annee).all():
        if d.montant is not None:
            derniers_dividendes[d.symbole] = d  # ecrase -> garde la + recente

    # Volume moyen par societe sur tout l'historique : plus l'historique
    # grandit, plus la mesure de liquidite devient fiable.
    volumes_moyens: dict[str, float] = {
        symbole: moyenne
        for symbole, moyenne in db.query(
            Cotation.symbole, func.avg(Cotation.volume)
        )
        .group_by(Cotation.symbole)
        .all()
        if moyenne is not None
    }
    divs_par_symbole: dict[str, list[int]] = {}
    for d in db.query(Dividende).filter(Dividende.montant.isnot(None)).all():
        divs_par_symbole.setdefault(d.symbole, []).append(d.annee)

    historiques_cours: dict[str, list[Cotation]] = {}
    for cotation in db.query(Cotation).filter(Cotation.cours_cloture.isnot(None)).order_by(Cotation.jour).all():
        historiques_cours.setdefault(cotation.symbole, []).append(cotation)
    variations_30j: dict[str, float | None] = {}
    for s, c in lignes:
        cible = c.jour - timedelta(days=30)
        ancien = next((x for x in reversed(historiques_cours.get(s.symbole, []))
                       if x.jour <= cible), None)
        variations_30j[s.symbole] = (
            round((c.cours_cloture / ancien.cours_cloture - 1) * 100, 2)
            if ancien and ancien.cours_cloture and c.cours_cloture else None
        )

    resultat = []
    for s, c in lignes:
        div = derniers_dividendes.get(s.symbole)
        rendement = None
        if div is not None and c.cours_cloture:
            # Rendement recalcule sur le cours d'aujourd'hui, pas celui
            # de l'epoque du versement : c'est ce que TOI tu toucherais.
            rendement = round(div.montant / c.cours_cloture * 100, 2)
        consecutives = _annees_consecutives(divs_par_symbole.get(s.symbole, []))
        regularite = "forte" if consecutives >= 4 else "moyenne" if consecutives >= 2 else "faible"
        resultat.append(
            ActionOut(
                symbole=s.symbole,
                nom=s.nom,
                cours_cloture=c.cours_cloture,
                variation=c.variation,
                volume=c.volume,
                dernier_jour=c.jour,
                dividende=div.montant if div else None,
                annee_dividende=div.annee if div else None,
                rendement=rendement,
                pays=pays_depuis_symbole(s.symbole),
                secteur=s.secteur,
                volume_moyen=volumes_moyens.get(s.symbole),
                liquidite=classer_liquidite(volumes_moyens.get(s.symbole)),
                variation_30j=variations_30j[s.symbole],
                regularite_dividende=regularite,
                annees_dividende_consecutives=consecutives,
            )
        )
    return resultat


@app.get("/actions/{symbole}", response_model=ActionDetailOut)
def detail_action(symbole: str, db: Session = Depends(get_db)):
    """Detail d'une action + tout son historique de cours."""
    societe = db.get(Societe, symbole.upper())
    if societe is None:
        raise HTTPException(status_code=404, detail="Action introuvable")

    historique = (
        db.query(Cotation)
        .filter_by(symbole=societe.symbole)
        .order_by(Cotation.jour)
        .all()
    )
    dividendes = (
        db.query(Dividende)
        .filter_by(symbole=societe.symbole)
        .order_by(Dividende.annee.desc())
        .all()
    )
    detachement = db.get(Detachement, societe.symbole)

    cours_valides = [c for c in historique if c.cours_cloture is not None]
    performances = _calculer_performances(cours_valides)
    comparaison = _comparaison_indices(db, cours_valides)
    indicateurs = _indicateurs_techniques(cours_valides)

    return ActionDetailOut(
        symbole=societe.symbole,
        nom=societe.nom,
        historique=[CotationOut.model_validate(c) for c in historique],
        dividendes=[DividendeOut.model_validate(d) for d in dividendes],
        prochain_detachement=(
            DetachementOut.model_validate(detachement) if detachement else None
        ),
        performances=performances,
        comparaison_indices=comparaison,
        indicateurs_techniques=indicateurs,
    )


def _calculer_performances(cours: list[Cotation]) -> PerformanceOut:
    if not cours:
        return PerformanceOut()
    dernier = cours[-1]

    def variation(delta: timedelta) -> float | None:
        cible = dernier.jour - delta
        anciens = [c for c in cours if c.jour <= cible]
        if not anciens or not anciens[-1].cours_cloture:
            return None
        return round((dernier.cours_cloture / anciens[-1].cours_cloture - 1) * 100, 2)

    debut = dernier.jour - timedelta(days=364)
    fenetre = [c for c in cours if c.jour >= debut]
    valeurs = [c.cours_cloture for c in fenetre if c.cours_cloture is not None]
    return PerformanceOut(
        variation_7j=variation(timedelta(days=7)),
        variation_30j=variation(timedelta(days=30)),
        variation_6m=variation(timedelta(days=182)),
        variation_1a=variation(timedelta(days=365)),
        plus_haut_52s=max(valeurs) if valeurs else None,
        plus_bas_52s=min(valeurs) if valeurs else None,
        debut_52s=fenetre[0].jour if fenetre else None,
        fin_52s=dernier.jour,
    )


def _comparaison_indices(db: Session, cours: list[Cotation]) -> list[ComparaisonPointOut]:
    if not cours:
        return []
    debut = cours[-1].jour - timedelta(days=365)
    actions = [c for c in cours if c.jour >= debut]
    indices = db.query(IndiceCotation).filter(
        IndiceCotation.jour >= debut,
        IndiceCotation.jour <= cours[-1].jour,
    ).order_by(IndiceCotation.jour).all()
    par_code = {}
    for i in indices:
        par_code.setdefault(i.code, {})[i.jour] = i.cloture
    if not indices:
        return []

    jours = sorted({c.jour for c in actions} | {i.jour for i in indices})
    action_jour = {c.jour: c.cours_cloture for c in actions}
    derniers = {"action": None, "BRVM-COMPOSITE": None, "BRVM-30": None}
    bases = {}
    resultat = []
    for jour in jours:
        if jour in action_jour:
            derniers["action"] = action_jour[jour]
        for code in ("BRVM-COMPOSITE", "BRVM-30"):
            if jour in par_code.get(code, {}):
                derniers[code] = par_code[code][jour]
        if any(v is None for v in derniers.values()):
            continue
        for cle, valeur in derniers.items():
            bases.setdefault(cle, valeur)
        resultat.append(ComparaisonPointOut(
            jour=jour,
            action=round(derniers["action"] / bases["action"] * 100, 2),
            brvm_composite=round(derniers["BRVM-COMPOSITE"] / bases["BRVM-COMPOSITE"] * 100, 2),
            brvm_30=round(derniers["BRVM-30"] / bases["BRVM-30"] * 100, 2),
        ))
    return resultat


def _indicateurs_techniques(cours: list[Cotation]) -> IndicateursTechniquesOut:
    """Indicateurs descriptifs, sans generation de signal d'investissement."""
    if not cours:
        return IndicateursTechniquesOut(explications=["Aucun cours disponible."])
    clotures = [c.cours_cloture for c in cours]
    points = []
    for i, c in enumerate(cours):
        mm20 = sum(clotures[i - 19:i + 1]) / 20 if i >= 19 else None
        mm50 = sum(clotures[i - 49:i + 1]) / 50 if i >= 49 else None
        points.append(PointTechniqueOut(
            jour=c.jour, cours=c.cours_cloture,
            moyenne_mobile_20=round(mm20, 2) if mm20 is not None else None,
            moyenne_mobile_50=round(mm50, 2) if mm50 is not None else None,
        ))
    variations = [(b / a - 1) for a, b in zip(clotures, clotures[1:]) if a]
    rsi = None
    if len(clotures) >= 15:
        changements = [b - a for a, b in zip(clotures[-15:-1], clotures[-14:])]
        gains = sum(max(v, 0) for v in changements) / 14
        pertes = sum(max(-v, 0) for v in changements) / 14
        rsi = 100.0 if pertes == 0 else 100 - 100 / (1 + gains / pertes)
    volatilite = stdev(variations[-20:]) * sqrt(252) * 100 if len(variations) >= 20 else None
    volumes = [c.volume for c in cours[-20:] if c.volume is not None]
    volume_moyen = sum(volumes) / len(volumes) if volumes else None
    mm20, mm50 = points[-1].moyenne_mobile_20, points[-1].moyenne_mobile_50
    dernier = clotures[-1]
    explications = []
    if mm20 is None:
        explications.append("La moyenne mobile 20 nécessite encore davantage de séances.")
    else:
        position = "au-dessus" if dernier > mm20 else "en dessous" if dernier < mm20 else "au niveau"
        explications.append(f"Le cours se situe {position} de sa moyenne des 20 dernières séances : cela décrit la tendance récente, sans prédire sa poursuite.")
    if mm50 is None:
        explications.append("La moyenne mobile 50 apparaîtra après 50 cours de clôture.")
    elif mm20 is not None:
        relation = "supérieure" if mm20 > mm50 else "inférieure" if mm20 < mm50 else "proche"
        explications.append(f"La moyenne 20 séances est {relation} à la moyenne 50 séances, ce qui situe le mouvement récent par rapport à la tendance plus longue.")
    if rsi is None:
        explications.append("Le RSI nécessite au moins 15 cours de clôture.")
    elif rsi >= 70:
        explications.append("Le RSI est élevé : les hausses récentes ont dominé, mais cela ne signifie pas automatiquement que le cours va baisser.")
    elif rsi <= 30:
        explications.append("Le RSI est faible : les baisses récentes ont dominé, sans garantir un rebond.")
    else:
        explications.append("Le RSI se situe dans une zone intermédiaire : hausses et baisses récentes sont relativement équilibrées.")
    if volatilite is not None:
        explications.append("La volatilité annualisée mesure l'amplitude des variations, pas leur direction : plus elle est élevée, plus le cours a été irrégulier.")
    return IndicateursTechniquesOut(
        moyenne_mobile_20=mm20, moyenne_mobile_50=mm50,
        rsi_14=round(rsi, 2) if rsi is not None else None,
        volatilite_20=round(volatilite, 2) if volatilite is not None else None,
        volume_moyen_20=round(volume_moyen, 2) if volume_moyen is not None else None,
        points=points, explications=explications,
    )


def _tendance_dividendes(serie: list[Dividende]) -> str | None:
    """Qualifie l'evolution du dividende sur les annees connues."""
    montants = [d.montant for d in sorted(serie, key=lambda d: d.annee)]
    if len(montants) < 2:
        return None
    evolution = (montants[-1] - montants[0]) / montants[0] * 100
    jamais_baisse = all(b >= a for a, b in zip(montants, montants[1:]))
    if jamais_baisse and evolution > 5:
        return "hausse"
    if abs(evolution) <= 5:
        return "stable"
    if evolution < 0:
        return "baisse"
    return "irregulier"


@app.get("/top-actions", response_model=list[TopActionOut])
def top_actions(limit: int = 10, db: Session = Depends(get_db)):
    """Top 10 pedagogique pour un debutant 'rendement long terme'.

    Score sur 100, volontairement simple et transparent :
      - 40 pts : rendement du dividende (plafonne a 8 % ; un rendement > 15 %
        est suspect = dividende exceptionnel, peu de points)
      - 30 pts : liquidite (peut-on recuperer son argent facilement ?)
      - 30 pts : historique du dividende (regularite + tendance)

    Le top est DIVERSIFIE : d'abord la meilleure action de chaque secteur
    officiel BRVM, puis les meilleurs scores restants pour completer a 10.
    Ce n'est PAS un conseil d'investissement : c'est un filtre d'apprentissage.
    """
    actions = liste_actions(db)

    # Historique des dividendes par societe (pour la tendance)
    divs_par_symbole: dict[str, list[Dividende]] = {}
    for d in db.query(Dividende).filter(Dividende.montant.isnot(None)).all():
        divs_par_symbole.setdefault(d.symbole, []).append(d)

    resultats = []
    for a in actions:
        raisons: list[str] = []

        # --- Rendement (40 pts) ---
        if a.rendement is None:
            pts_rendement = 0.0
            raisons.append("Pas de dividende connu (0/40)")
        elif a.rendement > 15:
            pts_rendement = 10.0
            raisons.append(
                f"⚠️ Rendement {a.rendement:.1f} % : dividende probablement exceptionnel (10/40)"
            )
        else:
            pts_rendement = min(a.rendement, 8.0) / 8.0 * 40.0
            raisons.append(f"Rendement {a.rendement:.2f} % ({pts_rendement:.0f}/40)")

        # --- Liquidite (30 pts) ---
        pts_liquidite = {"haute": 30.0, "moyenne": 15.0, "faible": 0.0}.get(
            a.liquidite or "", 0.0
        )
        emoji = {"haute": "🟢", "moyenne": "🟡", "faible": "🔴"}.get(a.liquidite or "", "")
        raisons.append(f"Liquidité {a.liquidite or 'inconnue'} {emoji} ({pts_liquidite:.0f}/30)")

        # --- Historique du dividende (30 pts) ---
        serie = divs_par_symbole.get(a.symbole, [])
        tendance = _tendance_dividendes(serie)
        pts_regularite = min(len(serie), 4) / 4.0 * 10.0
        pts_tendance = {"hausse": 20.0, "stable": 14.0, "irregulier": 7.0, "baisse": 0.0}.get(
            tendance or "", 0.0
        )
        libelle = {
            "hausse": "en hausse régulière 🌱",
            "stable": "stable ⚖️",
            "irregulier": "irrégulier 🎢",
            "baisse": "en baisse 📉",
        }.get(tendance or "", "historique trop court")
        raisons.append(
            f"Dividende {libelle}, versé {len(serie)} année(s) ({pts_tendance + pts_regularite:.0f}/30)"
        )

        resultats.append(
            TopActionOut(
                rang=0,
                symbole=a.symbole,
                nom=a.nom,
                pays=a.pays,
                secteur=a.secteur,
                cours_cloture=a.cours_cloture,
                rendement=a.rendement,
                liquidite=a.liquidite,
                tendance_dividende=tendance,
                score=round(pts_rendement + pts_liquidite + pts_tendance + pts_regularite, 1),
                raisons=raisons,
            )
        )

    resultats.sort(key=lambda r: -r.score)

    # Diversification : la meilleure action de chaque secteur d'abord...
    top: list[TopActionOut] = []
    secteurs_pris: set[str] = set()
    for r in resultats:
        if r.secteur and r.secteur not in secteurs_pris:
            r.meilleur_du_secteur = True
            secteurs_pris.add(r.secteur)
            top.append(r)
    # ... puis les meilleurs scores restants pour completer.
    limit = max(1, min(limit, len(resultats)))
    for r in resultats:
        if len(top) >= limit:
            break
        if r not in top:
            top.append(r)

    top.sort(key=lambda r: -r.score)
    for i, r in enumerate(top[:limit], start=1):
        r.rang = i
    return top[:limit]


# --------------------------------------------------------------------------
# Portefeuille virtuel (paper trading) : achats FICTIFS au dernier cours
# connu, pour apprendre a suivre un portefeuille. Aucun ordre reel.
# --------------------------------------------------------------------------

def _selection_portefeuille(db: Session, utilisateur: Utilisateur,
                            portefeuille_id: int | None) -> PortefeuilleUtilisateur:
    requete = db.query(PortefeuilleUtilisateur).filter_by(utilisateur_id=utilisateur.id)
    portefeuille_actif = requete.filter_by(id=portefeuille_id).first() if portefeuille_id else requete.order_by(PortefeuilleUtilisateur.cree_le).first()
    if portefeuille_actif is None:
        raise HTTPException(status_code=404, detail="Portefeuille introuvable")
    return portefeuille_actif


def _dernier_cours(db: Session, symbole: str) -> Cotation | None:
    return (
        db.query(Cotation)
        .filter_by(symbole=symbole)
        .order_by(Cotation.jour.desc())
        .first()
    )


@app.post("/portefeuille/especes")
def mouvement_especes(entree: MouvementEspecesIn,
                      portefeuille_id: int | None = None,
                      utilisateur: Utilisateur = Depends(utilisateur_courant),
                      db: Session = Depends(get_db)):
    portefeuille_actif = _selection_portefeuille(db, utilisateur, portefeuille_id)
    type_mouvement = entree.type.strip().upper()
    if type_mouvement not in {"DEPOT", "RETRAIT"} or entree.montant <= 0:
        raise HTTPException(status_code=400, detail="Mouvement de trésorerie invalide")
    if type_mouvement == "RETRAIT" and entree.montant > portefeuille_actif.solde_especes:
        raise HTTPException(status_code=400, detail="Liquidités insuffisantes")
    portefeuille_actif.solde_especes += entree.montant if type_mouvement == "DEPOT" else -entree.montant
    db.add(MouvementEspeces(portefeuille_id=portefeuille_actif.id,
                            type=type_mouvement, montant=entree.montant,
                            solde_apres=portefeuille_actif.solde_especes))
    db.commit()
    return {"solde_especes": portefeuille_actif.solde_especes}


@app.post("/portefeuille/positions", response_model=PositionOut)
def acheter(achat: AchatIn, utilisateur: Utilisateur = Depends(utilisateur_courant),
            db: Session = Depends(get_db)):
    """Achat fictif conserve dans le journal des transactions."""
    societe = db.get(Societe, achat.symbole.upper())
    if societe is None:
        raise HTTPException(status_code=404, detail="Action introuvable")
    if achat.quantite <= 0:
        raise HTTPException(status_code=400, detail="Quantité invalide")
    if not 0 <= achat.frais_courtage_pct <= 100:
        raise HTTPException(status_code=400, detail="Frais invalides")
    cotation = _dernier_cours(db, societe.symbole)
    if cotation is None or cotation.cours_cloture is None:
        raise HTTPException(status_code=400, detail="Pas de cours disponible")

    portefeuille_actif = _selection_portefeuille(db, utilisateur, achat.portefeuille_id)
    brut = achat.quantite * cotation.cours_cloture
    frais = brut * achat.frais_courtage_pct / 100
    montant_total = brut + frais
    if montant_total > portefeuille_actif.solde_especes:
        raise HTTPException(status_code=400, detail=f"Liquidités insuffisantes : {portefeuille_actif.solde_especes:.0f} FCFA disponibles")
    portefeuille_actif.solde_especes -= montant_total
    db.add(Transaction(symbole=societe.symbole, type="ACHAT",
                       quantite=achat.quantite, prix=cotation.cours_cloture,
                       jour=cotation.jour, frais_courtage=frais,
                       fiscalite=0, montant_net=montant_total,
                       portefeuille_id=portefeuille_actif.id))
    db.commit()
    return next(p for p in _positions_out(db, portefeuille_actif.id) if p.symbole == societe.symbole)


@app.delete("/portefeuille/positions/{position_id}")
def vendre(position_id: int, portefeuille_id: int | None = None,
           utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    """Compatibilite : vend la totalite d'une position sans frais."""
    portefeuille_actif = _selection_portefeuille(db, utilisateur, portefeuille_id)
    position = next((p for p in _positions_out(db, portefeuille_actif.id) if p.id == position_id), None)
    if position is None:
        raise HTTPException(status_code=404, detail="Position introuvable")
    transaction = _enregistrer_vente(db, position, VenteIn(quantite=position.quantite), portefeuille_actif.id)
    return {"vendu": transaction.id}


@app.post("/portefeuille/positions/{position_id}/vendre", response_model=TransactionOut)
def vendre_partiellement(position_id: int, vente: VenteIn, portefeuille_id: int | None = None,
                         utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    portefeuille_actif = _selection_portefeuille(db, utilisateur, portefeuille_id)
    position = next((p for p in _positions_out(db, portefeuille_actif.id) if p.id == position_id), None)
    if position is None:
        raise HTTPException(status_code=404, detail="Position introuvable")
    return _enregistrer_vente(db, position, vente, portefeuille_actif.id)


def _enregistrer_vente(db: Session, position: PositionOut, vente: VenteIn, portefeuille_id: int) -> Transaction:
    if vente.quantite <= 0 or vente.quantite > position.quantite:
        raise HTTPException(status_code=400, detail="Quantité de vente invalide")
    if not 0 <= vente.frais_courtage_pct <= 100 or not 0 <= vente.fiscalite_pct <= 100:
        raise HTTPException(status_code=400, detail="Taux invalide")
    cotation = _dernier_cours(db, position.symbole)
    if cotation is None or cotation.cours_cloture is None:
        raise HTTPException(status_code=400, detail="Pas de cours disponible")
    brut = vente.quantite * cotation.cours_cloture
    frais = brut * vente.frais_courtage_pct / 100
    gain_avant_impot = brut - frais - vente.quantite * position.prix_achat
    fiscalite = max(gain_avant_impot, 0) * vente.fiscalite_pct / 100
    transaction = Transaction(
        symbole=position.symbole, type="VENTE", quantite=vente.quantite,
        prix=cotation.cours_cloture, jour=cotation.jour,
        frais_courtage=frais, fiscalite=fiscalite,
        montant_net=brut - frais - fiscalite,
        gain_realise=brut - frais - fiscalite - vente.quantite * position.prix_achat,
        portefeuille_id=portefeuille_id,
    )
    db.add(transaction)
    portefeuille = db.get(PortefeuilleUtilisateur, portefeuille_id)
    portefeuille.solde_especes += transaction.montant_net
    db.commit()
    db.refresh(transaction)
    return transaction


def _etats_positions(db: Session, portefeuille_id: int) -> dict[str, dict]:
    etats: dict[str, dict] = {}
    for t in db.query(Transaction).filter_by(portefeuille_id=portefeuille_id).order_by(Transaction.jour, Transaction.id).all():
        etat = etats.setdefault(t.symbole, {"quantite": 0, "cout": 0.0, "jour": t.jour, "id": t.id})
        if t.type == "ACHAT":
            if etat["quantite"] == 0:
                etat["jour"], etat["id"] = t.jour, t.id
            etat["cout"] += t.montant_net
            etat["quantite"] += t.quantite
        elif etat["quantite"] > 0:
            prmp = etat["cout"] / etat["quantite"]
            etat["cout"] -= prmp * t.quantite
            etat["quantite"] -= t.quantite
            if etat["quantite"] == 0:
                etat["cout"] = 0.0
    return etats


def _positions_out(db: Session, portefeuille_id: int) -> list[PositionOut]:
    return [_transaction_position_out(db, symbole, etat, portefeuille_id)
            for symbole, etat in _etats_positions(db, portefeuille_id).items() if etat["quantite"] > 0]


def _dividendes_recus_position(db: Session, portefeuille_id: int, symbole: str) -> float:
    transactions = db.query(Transaction).filter_by(
        portefeuille_id=portefeuille_id, symbole=symbole
    ).order_by(Transaction.jour, Transaction.id).all()
    total = 0.0
    for dividende in db.query(Dividende).filter(
        Dividende.symbole == symbole, Dividende.montant.isnot(None)
    ).all():
        fin_exercice = date(dividende.annee, 12, 31)
        quantite = sum((t.quantite if t.type == "ACHAT" else -t.quantite)
                       for t in transactions if t.jour <= fin_exercice)
        total += max(quantite, 0) * dividende.montant
    return total


def _transaction_position_out(db: Session, symbole: str, etat: dict, portefeuille_id: int) -> PositionOut:
    societe = db.get(Societe, symbole)
    cotation = _dernier_cours(db, symbole)
    cours = cotation.cours_cloture if cotation else None
    quantite, investi = etat["quantite"], etat["cout"]
    prmp = investi / quantite
    valeur = quantite * cours if cours is not None else None
    dernier_div = db.query(Dividende).filter(
        Dividende.symbole == symbole, Dividende.montant.isnot(None)
    ).order_by(Dividende.annee.desc()).first()
    detachement = db.get(Detachement, symbole)
    rendement_dividende = (
        dernier_div.montant / cours * 100
        if dernier_div and cours and cours > 0 else None
    )
    dividendes_recus = _dividendes_recus_position(db, portefeuille_id, symbole)
    return PositionOut(
        id=etat["id"], symbole=symbole, nom=societe.nom if societe else symbole,
        quantite=quantite, prix_achat=prmp, jour_achat=etat["jour"],
        cours_actuel=cours, investi=investi, valeur_actuelle=valeur,
        plus_value=valeur - investi if valeur is not None else None,
        plus_value_pct=(valeur - investi) / investi * 100 if valeur is not None and investi else None,
        dividende_annuel=quantite * dernier_div.montant if dernier_div else None,
        dividende_par_action=dernier_div.montant if dernier_div else None,
        annee_dividende=dernier_div.annee if dernier_div else None,
        rendement_dividende_pct=round(rendement_dividende, 2) if rendement_dividende is not None else None,
        date_detachement_annoncee=detachement.date_detachement if detachement else None,
        dividende_donnee_ancienne=bool(dernier_div and dernier_div.annee < date.today().year - 1),
        dividende_potentiellement_exceptionnel=bool(rendement_dividende and rendement_dividende > 15),
        secteur=societe.secteur if societe else None, pays=pays_depuis_symbole(symbole),
        dividendes_recus=dividendes_recus, cout_base=investi,
    )


def _repartition(sorties: list[PositionOut], champ: str, valeur_totale: float) -> list[RepartitionOut]:
    groupes: dict[str, float] = {}
    for position in sorties:
        libelle = getattr(position, champ) or "Non classé"
        groupes[libelle] = groupes.get(libelle, 0) + (position.valeur_actuelle or position.investi)
    return [RepartitionOut(libelle=k, valeur=v, pourcentage=round(v / valeur_totale * 100, 2))
            for k, v in sorted(groupes.items(), key=lambda item: -item[1])] if valeur_totale else []


def _performance_temporelle(historique: list[PointValeur], transactions: list[Transaction]):
    """Rendements quotidiens neutralisant les nouveaux apports."""
    apports: dict = {}
    for t in transactions:
        flux = t.montant_net if t.type == "ACHAT" else -t.montant_net
        apports[t.jour] = apports.get(t.jour, 0) + flux
    rendements = []
    courbe = []
    indice = 100.0
    precedent = None
    for point in historique:
        if precedent and precedent > 0:
            rendement = (point.valeur - apports.get(point.jour, 0)) / precedent - 1
            rendements.append(rendement)
            indice *= 1 + rendement
        courbe.append((point.jour, round(indice, 2)))
        precedent = point.valeur
    return rendements, courbe


def _comparaison_portefeuille(db: Session, courbe: list[tuple]) -> list[PointComparaisonPortefeuille]:
    if not courbe:
        return []
    niveaux = db.query(IndiceCotation).filter(
        IndiceCotation.code == "BRVM-COMPOSITE",
        IndiceCotation.jour >= courbe[0][0],
        IndiceCotation.jour <= courbe[-1][0],
    ).order_by(IndiceCotation.jour).all()
    if not niveaux:
        return []
    par_jour = {i.jour: i.cloture for i in niveaux}
    base = niveaux[0].cloture
    dernier = None
    resultat = []
    for jour, valeur in courbe:
        dernier = par_jour.get(jour, dernier)
        if dernier is not None:
            resultat.append(PointComparaisonPortefeuille(
                jour=jour, portefeuille=valeur,
                indice=round(dernier / base * 100, 2),
            ))
    return resultat


@app.get("/portefeuille", response_model=PortefeuilleOut)
def portefeuille(portefeuille_id: int | None = None,
                 utilisateur: Utilisateur = Depends(utilisateur_courant),
                 db: Session = Depends(get_db)):
    """Le portefeuille complet + sa valeur totale jour par jour."""
    portefeuille_actif = _selection_portefeuille(db, utilisateur, portefeuille_id)
    transactions = db.query(Transaction).filter_by(portefeuille_id=portefeuille_actif.id).order_by(Transaction.jour, Transaction.id).all()
    mouvements_especes = db.query(MouvementEspeces).filter_by(
        portefeuille_id=portefeuille_actif.id
    ).order_by(MouvementEspeces.cree_le.desc(), MouvementEspeces.id.desc()).all()
    sorties = _positions_out(db, portefeuille_actif.id)

    total_investi = sum(s.investi for s in sorties)
    valeur_totale = sum(s.valeur_actuelle or s.investi for s in sorties)
    plus_value = valeur_totale - total_investi
    plus_value_realisee = sum(t.gain_realise or 0 for t in transactions if t.type == "VENTE")
    frais_totaux = sum(t.frais_courtage for t in transactions)
    fiscalite_totale = sum(t.fiscalite for t in transactions)
    dividendes_annuels = sum(s.dividende_annuel or 0 for s in sorties)
    dividendes_recus = sum(_dividendes_recus_position(db, portefeuille_actif.id, symbole)
                           for symbole in {t.symbole for t in transactions})

    # Valeur du portefeuille jour par jour : pour chaque jour de cotation
    # depuis le premier achat, somme (quantite x dernier cours connu) des
    # positions deja achetees ce jour-la.
    historique: list[PointValeur] = []
    if transactions:
        symboles = {t.symbole for t in transactions}
        cotations = (
            db.query(Cotation)
            .filter(Cotation.symbole.in_(symboles))
            .order_by(Cotation.jour)
            .all()
        )
        jours = sorted({c.jour for c in cotations})
        cours_du_jour: dict[tuple, float] = {
            (c.symbole, c.jour): c.cours_cloture
            for c in cotations
            if c.cours_cloture is not None
        }
        derniers: dict[str, float] = {}
        premier_achat = min(t.jour for t in transactions)
        quantites = {s: 0 for s in symboles}
        transactions_par_jour: dict = {}
        for t in transactions:
            transactions_par_jour.setdefault(t.jour, []).append(t)
        for jour in jours:
            for s in symboles:
                if (s, jour) in cours_du_jour:
                    derniers[s] = cours_du_jour[(s, jour)]
            if jour < premier_achat:
                continue
            for t in transactions_par_jour.get(jour, []):
                quantites[t.symbole] += t.quantite if t.type == "ACHAT" else -t.quantite
            valeur_jour = sum(
                quantites[s] * derniers.get(s, 0)
                for s in symboles
            )
            historique.append(PointValeur(jour=jour, valeur=valeur_jour))

    rendements, courbe = _performance_temporelle(historique, transactions)
    performance_totale = plus_value + plus_value_realisee + dividendes_recus
    achats_totaux = sum(t.montant_net for t in transactions if t.type == "ACHAT")
    performance_totale_pct = performance_totale / achats_totaux * 100 if achats_totaux else None
    jours_detention = (historique[-1].jour - min(t.jour for t in transactions)).days if historique and transactions else 0
    rendement_annualise = None
    if achats_totaux and jours_detention >= 30 and 1 + performance_totale / achats_totaux > 0:
        rendement_annualise = ((1 + performance_totale / achats_totaux) ** (365 / jours_detention) - 1) * 100
    volatilite = stdev(rendements) * sqrt(252) * 100 if len(rendements) >= 20 else None
    poids = [(s.valeur_actuelle or s.investi) / valeur_totale for s in sorties] if valeur_totale else []

    return PortefeuilleOut(
        positions=sorties,
        total_investi=total_investi,
        valeur_totale=valeur_totale,
        plus_value=plus_value,
        plus_value_pct=(plus_value / total_investi * 100) if total_investi else None,
        dividendes_annuels=dividendes_annuels,
        historique=historique,
        repartition_secteurs=_repartition(sorties, "secteur", valeur_totale),
        repartition_pays=_repartition(sorties, "pays", valeur_totale),
        concentration_max_pct=round(max(poids) * 100, 2) if poids else None,
        indice_concentration=round(sum(p * p for p in poids) * 10000, 0) if poids else None,
        dividendes_recus=dividendes_recus,
        performance_totale=performance_totale,
        performance_totale_pct=performance_totale_pct,
        rendement_annualise=round(rendement_annualise, 2) if rendement_annualise is not None else None,
        volatilite_annualisee=round(volatilite, 2) if volatilite is not None else None,
        comparaison_indice=_comparaison_portefeuille(db, courbe),
        transactions=[TransactionOut.model_validate(t) for t in reversed(transactions)],
        frais_totaux=frais_totaux,
        fiscalite_totale=fiscalite_totale,
        plus_value_realisee=plus_value_realisee,
        plus_value_latente=plus_value,
        solde_especes=portefeuille_actif.solde_especes,
        valeur_globale=valeur_totale + portefeuille_actif.solde_especes,
        mouvements_especes=[MouvementEspecesOut.model_validate(m) for m in mouvements_especes],
    )


@app.get("/portefeuille/export.csv")
def exporter_transactions_csv(portefeuille_id: int | None = None,
                              utilisateur: Utilisateur = Depends(utilisateur_courant),
                              db: Session = Depends(get_db)):
    """Registre complet UTF-8, séparateur ';', ouvrable dans Excel."""
    portefeuille_actif = _selection_portefeuille(db, utilisateur, portefeuille_id)
    transactions = db.query(Transaction).filter_by(portefeuille_id=portefeuille_actif.id).all()
    mouvements = db.query(MouvementEspeces).filter_by(portefeuille_id=portefeuille_actif.id).all()
    sortie = io.StringIO(newline="")
    writer = csv.writer(sortie, delimiter=";")
    writer.writerow(["Date et heure", "Catégorie", "Type", "Symbole", "Quantité", "Prix unitaire FCFA",
                     "Frais de courtage FCFA", "Fiscalité FCFA", "Montant net FCFA",
                     "Plus-value réalisée FCFA", "Flux de trésorerie FCFA", "Solde après mouvement FCFA"])
    nombre = lambda valeur: "" if valeur is None else f"{valeur:.2f}".replace(".", ",")
    lignes = []
    for t in transactions:
        flux = -t.montant_net if t.type == "ACHAT" else t.montant_net
        lignes.append((t.creee_le, [t.creee_le.isoformat(sep=" ", timespec="seconds"), "Titres",
                       t.type, t.symbole, t.quantite, nombre(t.prix), nombre(t.frais_courtage),
                       nombre(t.fiscalite), nombre(t.montant_net), nombre(t.gain_realise),
                       nombre(flux), ""]))
    for m in mouvements:
        flux = m.montant if m.type == "DEPOT" else -m.montant
        lignes.append((m.cree_le, [m.cree_le.isoformat(sep=" ", timespec="seconds"), "Trésorerie",
                       m.type, "", "", "", "", "", nombre(m.montant), "",
                       nombre(flux), nombre(m.solde_apres)]))
    for _, ligne in sorted(lignes, key=lambda element: element[0]):
        writer.writerow(ligne)
    contenu = ("\ufeff" + sortie.getvalue()).encode("utf-8")
    return StreamingResponse(io.BytesIO(contenu), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=journal-complet-brvm.csv"})
