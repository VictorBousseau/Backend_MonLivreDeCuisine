"""
Script de migration pour ajouter la colonne is_admin
Exécuter une seule fois sur Railway
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./monlivredecuisine.db")

# Railway utilise "postgres://" mais SQLAlchemy a besoin de "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        # Ajouter la colonne is_admin si elle n'existe pas
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("✅ Colonne is_admin ajoutée avec succès")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("ℹ️ La colonne is_admin existe déjà")
            else:
                print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    migrate()
