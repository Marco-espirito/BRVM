"""Logique du portefeuille : selection, positions agregees (PRMP), ventes,
dividendes recus, repartition et performance temporelle. Aucune route ici."""
from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    Cotation,
    Detachement,
    Dividende,
    IndiceCotation,
    MouvementEspeces,
    PortefeuilleUtilisateur,
    Societe,
    Transaction,
    Utilisateur,
)
from ..schemas import (
    PointComparaisonPortefeuille,
    PointValeur,
    PositionOut,
    RepartitionOut,
    VenteIn,
)
from .analyse import pays_depuis_symbole


def selection_portefeuille(db: Session, utilisateur: Utilisateur,
                           portefeuille_id: int | None) -> PortefeuilleUtilisateur:
    requete = db.query(PortefeuilleUtilisateur).filter_by(utilisateur_id=utilisateur.id)
    portefeuille_actif = requete.filter_by(id=portefeuille_id).first() if portefeuille_id else requete.order_by(PortefeuilleUtilisateur.cree_le).first()
    if portefeuille_actif is None:
        raise HTTPException(status_code=404, detail="Portefeuille introuvable")
    return portefeuille_actif


def dernier_cours(db: Session, symbole: str) -> Cotation | None:
    return (
        db.query(Cotation)
        .filter_by(symbole=symbole)
        .order_by(Cotation.jour.desc())
        .first()
    )


def enregistrer_vente(db: Session, position: PositionOut, vente: VenteIn, portefeuille_id: int) -> Transaction:
    if vente.quantite <= 0 or vente.quantite > position.quantite:
        raise HTTPException(status_code=400, detail="Quantité de vente invalide")
    if not 0 <= vente.frais_courtage_pct <= 100 or not 0 <= vente.fiscalite_pct <= 100:
        raise HTTPException(status_code=400, detail="Taux invalide")
    cotation = dernier_cours(db, position.symbole)
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


def etats_positions(db: Session, portefeuille_id: int) -> dict[str, dict]:
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


def positions_out(db: Session, portefeuille_id: int) -> list[PositionOut]:
    return [transaction_position_out(db, symbole, etat, portefeuille_id)
            for symbole, etat in etats_positions(db, portefeuille_id).items() if etat["quantite"] > 0]


def dividendes_recus_position(db: Session, portefeuille_id: int, symbole: str) -> float:
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


def transaction_position_out(db: Session, symbole: str, etat: dict, portefeuille_id: int) -> PositionOut:
    societe = db.get(Societe, symbole)
    cotation = dernier_cours(db, symbole)
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
    dividendes_recus = dividendes_recus_position(db, portefeuille_id, symbole)
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


def repartition(sorties: list[PositionOut], champ: str, valeur_totale: float) -> list[RepartitionOut]:
    groupes: dict[str, float] = {}
    for position in sorties:
        libelle = getattr(position, champ) or "Non classé"
        groupes[libelle] = groupes.get(libelle, 0) + (position.valeur_actuelle or position.investi)
    return [RepartitionOut(libelle=k, valeur=v, pourcentage=round(v / valeur_totale * 100, 2))
            for k, v in sorted(groupes.items(), key=lambda item: -item[1])] if valeur_totale else []


def performance_temporelle(historique: list[PointValeur], transactions: list[Transaction]):
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


def comparaison_portefeuille(db: Session, courbe: list[tuple]) -> list[PointComparaisonPortefeuille]:
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
