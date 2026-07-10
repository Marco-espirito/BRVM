"""Connexion a la base SQLite et session SQLAlchemy."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# La base est un simple fichier a la racine du backend : brvm.db.
# BRVM_DB_PATH permet d'utiliser une autre base (tests, deploiement).
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("BRVM_DB_PATH", BASE_DIR / "brvm.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependance FastAPI : fournit une session et la ferme apres usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
