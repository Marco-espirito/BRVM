"""Route du calendrier des dividendes : prochains detachements croises avec
les quantites detenues dans le portefeuille actif."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import utilisateur_courant
from ..db import get_db
from ..models import Detachement, Societe, Utilisateur
from ..schemas import CalendrierDividendesOut, EvenementCalendrierOut
from ..services.portefeuille import positions_out, selection_portefeuille

router = APIRouter(tags=["calendrier"])


@router.get("/dividendes/calendrier", response_model=CalendrierDividendesOut)
def calendrier_dividendes(portefeuille_id: int | None = None,
                          utilisateur: Utilisateur = Depends(utilisateur_courant),
                          db: Session = Depends(get_db)):
    portefeuille_actif = selection_portefeuille(db, utilisateur, portefeuille_id)
    quantites = {p.symbole: p.quantite for p in positions_out(db, portefeuille_actif.id)}
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
