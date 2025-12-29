"""
Configuration de la base de données avec support PostgreSQL (production) et SQLite (local)
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Utilise DATABASE_URL en production (Railway), sinon SQLite en local
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./monlivredecuisine.db")

# Railway utilise "postgres://" mais SQLAlchemy a besoin de "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configuration du moteur selon le type de DB
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dépendance FastAPI pour obtenir une session DB"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

