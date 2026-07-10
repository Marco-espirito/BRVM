"""Connexion a la base SQLite et session SQLAlchemy."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# La base est un simple fichier a la racine du backend : brvm.db.
# BRVM_DB_PATH permet d'utiliser une autre base (tests, deploiement).
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("BRVM_DB_PATH", BASE_DIR / "brvm.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _configurer_sqlite(dbapi_connection, _connection_record):
    curseur = dbapi_connection.cursor()
    curseur.execute("PRAGMA foreign_keys=ON")
    curseur.execute("PRAGMA journal_mode=WAL")
    curseur.execute("PRAGMA busy_timeout=5000")
    curseur.close()
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
