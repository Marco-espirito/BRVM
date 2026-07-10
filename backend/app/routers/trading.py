"""Routes du portefeuille virtuel : mouvements d'especes, achats/ventes fictifs,
valorisation complete (jour par jour, performance, repartition) et export CSV."""
from __future__ import annotations

import csv
import io
from math import sqrt
from statistics import stdev

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth import utilisateur_courant
from ..db import get_db
from ..models import (
    Cotation,
    MouvementEspeces,
    PortefeuilleUtilisateur,
    Societe,
    Transaction,
    Utilisateur,
)
from ..schemas import (
    AchatIn,
    MouvementEspecesIn,
    MouvementEspecesOut,
    PointValeur,
    PortefeuilleOut,
    PositionOut,
    TransactionOut,
    VenteIn,
)
from ..services.portefeuille import (
    comparaison_portefeuille,
    dernier_cours,
    dividendes_recus_position,
    enregistrer_vente,
    performance_temporelle,
    positions_out,
    repartition,
    selection_portefeuille,
)

router = APIRouter(tags=["trading"])


@router.post("/portefeuille/especes")
def mouvement_especes(entree: MouvementEspecesIn,
                      portefeuille_id: int | None = None,
                      utilisateur: Utilisateur = Depends(utilisateur_courant),
                      db: Session = Depends(get_db)):
    portefeuille_actif = selection_portefeuille(db, utilisateur, portefeuille_id)
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


@router.post("/portefeuille/positions", response_model=PositionOut)
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
    cotation = dernier_cours(db, societe.symbole)
    if cotation is None or cotation.cours_cloture is None:
        raise HTTPException(status_code=400, detail="Pas de cours disponible")

    portefeuille_actif = selection_portefeuille(db, utilisateur, achat.portefeuille_id)
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
    return next(p for p in positions_out(db, portefeuille_actif.id) if p.symbole == societe.symbole)


@router.delete("/portefeuille/positions/{position_id}")
def vendre(position_id: int, portefeuille_id: int | None = None,
           utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    """Compatibilite : vend la totalite d'une position sans frais."""
    portefeuille_actif = selection_portefeuille(db, utilisateur, portefeuille_id)
    position = next((p for p in positions_out(db, portefeuille_actif.id) if p.id == position_id), None)
    if position is None:
        raise HTTPException(status_code=404, detail="Position introuvable")
    transaction = enregistrer_vente(db, position, VenteIn(quantite=position.quantite), portefeuille_actif.id)
    return {"vendu": transaction.id}


@router.post("/portefeuille/positions/{position_id}/vendre", response_model=TransactionOut)
def vendre_partiellement(position_id: int, vente: VenteIn, portefeuille_id: int | None = None,
                         utilisateur: Utilisateur = Depends(utilisateur_courant), db: Session = Depends(get_db)):
    portefeuille_actif = selection_portefeuille(db, utilisateur, portefeuille_id)
    position = next((p for p in positions_out(db, portefeuille_actif.id) if p.id == position_id), None)
    if position is None:
        raise HTTPException(status_code=404, detail="Position introuvable")
    return enregistrer_vente(db, position, vente, portefeuille_actif.id)


@router.get("/portefeuille", response_model=PortefeuilleOut)
def portefeuille(portefeuille_id: int | None = None,
                 utilisateur: Utilisateur = Depends(utilisateur_courant),
                 db: Session = Depends(get_db)):
    """Le portefeuille complet + sa valeur totale jour par jour."""
    portefeuille_actif = selection_portefeuille(db, utilisateur, portefeuille_id)
    transactions = db.query(Transaction).filter_by(portefeuille_id=portefeuille_actif.id).order_by(Transaction.jour, Transaction.id).all()
    mouvements_especes = db.query(MouvementEspeces).filter_by(
        portefeuille_id=portefeuille_actif.id
    ).order_by(MouvementEspeces.cree_le.desc(), MouvementEspeces.id.desc()).all()
    sorties = positions_out(db, portefeuille_actif.id)

    total_investi = sum(s.investi for s in sorties)
    valeur_totale = sum(s.valeur_actuelle or s.investi for s in sorties)
    plus_value = valeur_totale - total_investi
    plus_value_realisee = sum(t.gain_realise or 0 for t in transactions if t.type == "VENTE")
    frais_totaux = sum(t.frais_courtage for t in transactions)
    fiscalite_totale = sum(t.fiscalite for t in transactions)
    dividendes_annuels = sum(s.dividende_annuel or 0 for s in sorties)
    dividendes_recus = sum(dividendes_recus_position(db, portefeuille_actif.id, symbole)
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

    rendements, courbe = performance_temporelle(historique, transactions)
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
        repartition_secteurs=repartition(sorties, "secteur", valeur_totale),
        repartition_pays=repartition(sorties, "pays", valeur_totale),
        concentration_max_pct=round(max(poids) * 100, 2) if poids else None,
        indice_concentration=round(sum(p * p for p in poids) * 10000, 0) if poids else None,
        dividendes_recus=dividendes_recus,
        performance_totale=performance_totale,
        performance_totale_pct=performance_totale_pct,
        rendement_annualise=round(rendement_annualise, 2) if rendement_annualise is not None else None,
        volatilite_annualisee=round(volatilite, 2) if volatilite is not None else None,
        comparaison_indice=comparaison_portefeuille(db, courbe),
        transactions=[TransactionOut.model_validate(t) for t in reversed(transactions)],
        frais_totaux=frais_totaux,
        fiscalite_totale=fiscalite_totale,
        plus_value_realisee=plus_value_realisee,
        plus_value_latente=plus_value,
        solde_especes=portefeuille_actif.solde_especes,
        valeur_globale=valeur_totale + portefeuille_actif.solde_especes,
        mouvements_especes=[MouvementEspecesOut.model_validate(m) for m in mouvements_especes],
    )


@router.get("/portefeuille/export.csv")
def exporter_transactions_csv(portefeuille_id: int | None = None,
                              utilisateur: Utilisateur = Depends(utilisateur_courant),
                              db: Session = Depends(get_db)):
    """Registre complet UTF-8, séparateur ';', ouvrable dans Excel."""
    portefeuille_actif = selection_portefeuille(db, utilisateur, portefeuille_id)
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
    contenu = ("﻿" + sortie.getvalue()).encode("utf-8")
    return StreamingResponse(io.BytesIO(contenu), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=journal-complet-brvm.csv"})
