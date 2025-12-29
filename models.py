"""
Modèles SQLAlchemy pour MonLivreDeCuisine
Relations: User -> Recipes -> Ingredients/Steps
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
import enum

from database import Base


class CategorieRecette(str, enum.Enum):
    """Catégories de recettes disponibles"""
    ENTREE = "Entrée"
    PLAT = "Plat"
    DESSERT = "Dessert"
    GOURMANDISES = "Gourmandises"


class User(Base):
    """Modèle utilisateur"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)

    # Relation: un utilisateur peut avoir plusieurs recettes
    recipes = relationship("Recipe", back_populates="auteur", cascade="all, delete-orphan")


class Recipe(Base):
    """Modèle recette"""
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    titre = Column(String(200), nullable=False, index=True)
    categorie = Column(SQLEnum(CategorieRecette), nullable=False)
    temps_prep = Column(Integer, nullable=True)  # en minutes
    temps_cuisson = Column(Integer, nullable=True)  # en minutes
    temperature = Column(Integer, nullable=True)  # en °C
    
    # Clé étrangère vers User
    auteur_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relations
    auteur = relationship("User", back_populates="recipes")
    ingredients = relationship("Ingredient", back_populates="recipe", cascade="all, delete-orphan")
    steps = relationship("Step", back_populates="recipe", cascade="all, delete-orphan", order_by="Step.ordre")


class Ingredient(Base):
    """Modèle ingrédient"""
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False, index=True)
    quantite = Column(Float, nullable=True)
    unite = Column(String(50), nullable=True)  # ex: "g", "ml", "pièce"
    
    # Clé étrangère vers Recipe
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)

    # Relation
    recipe = relationship("Recipe", back_populates="ingredients")


class Step(Base):
    """Modèle étape de préparation"""
    __tablename__ = "steps"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String(1000), nullable=False)
    ordre = Column(Integer, nullable=False)  # 1, 2, 3...
    
    # Clé étrangère vers Recipe
    recipe_id = Column(Integer, ForeignKey("recipes.id"), nullable=False)

    # Relation
    recipe = relationship("Recipe", back_populates="steps")
