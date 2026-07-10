"""API FastAPI du BRVM Explorer.

Ce fichier assemble l'application : cycle de vie, CORS et montage des routers.
La logique vit dans app/routers/ (routes par domaine) et app/services/
(analyse, portefeuille, backtest). Voir /docs pour la documentation interactive.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .ingest import creer_tables
from .routers import (
    actions,
    alertes,
    auth,
    backtest,
    calendrier,
    portefeuilles,
    trading,
)

# Reexports pour compatibilite (tests, anciens imports depuis app.main).
from .services.analyse import (  # noqa: F401
    classer_liquidite,
    indicateurs_techniques as _indicateurs_techniques,
    pays_depuis_symbole,
    tendance_dividendes as _tendance_dividendes,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    creer_tables()
    yield


app = FastAPI(title="BRVM Explorer", version="0.2.0", lifespan=lifespan)

# Autorise le front React a appeler l'API. Origines configurables par
# BRVM_CORS_ORIGINS (liste separee par des virgules).
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


for module in (auth, portefeuilles, alertes, calendrier, backtest, actions, trading):
    app.include_router(module.router)
