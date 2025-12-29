"""
MonLivreDeCuisine - API FastAPI
Endpoints: Auth, CRUD Recettes, Recherche Frigo
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text, or_
from typing import List
from datetime import timedelta

from database import engine, get_db, Base
from models import User, Recipe, Ingredient, Step, CategorieRecette
from schemas import (
    UserCreate, UserResponse, UserLogin, Token,
    RecipeCreate, RecipeUpdate, RecipeResponse, RecipeListResponse,
    FrigoSearchRequest, FrigoSearchResult
)
from auth import (
    get_password_hash, authenticate_user, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, get_user_by_email
)
# from sqlalchemy import text  <-- Removed redundant import


# Création des tables
Base.metadata.create_all(bind=engine)

# Migration: ajouter is_admin si la colonne n'existe pas
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
        conn.commit()
        print("✅ Migration: colonne is_admin ajoutée")
except Exception as e:
    pass

# Migration: corriger les utilisateurs avec is_admin NULL
try:
    with engine.connect() as conn:
        conn.execute(text("UPDATE users SET is_admin = FALSE WHERE is_admin IS NULL"))
        conn.commit()
        print("✅ Migration: is_admin NULL -> FALSE")
except Exception as e:
    pass

# Migration: ajouter tags si la colonne n'existe pas
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE recipes ADD COLUMN tags TEXT"))
        conn.commit()
        print("✅ Migration: colonne tags ajoutée")
except Exception as e:
    pass

# Migration: Convertir categorie en VARCHAR pour éviter les problèmes d'Enum et supporter Gourmandises
try:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        print("🔍 Migration: Conversion colonne categorie en VARCHAR...")
        if engine.dialect.name == 'postgresql':
            # Convertir l'enum en text/varchar
            conn.execute(text("ALTER TABLE recipes ALTER COLUMN categorie TYPE VARCHAR(50) USING categorie::text"))
            print("✅ Migration: Colonne categorie convertie en VARCHAR (PostgreSQL)")
        else:
            # SQLite (déjà flexible)
            print("ℹ️ Migration ignorée (SQLite)")

except Exception as e:
    print(f"Migration note (Varchar): {e}")
    pass

# Application FastAPI
app = FastAPI(
    title="MonLivreDeCuisine API",
    description="API de gestion de recettes de cuisine familiale",
    version="1.0.0"
)

# Configuration CORS pour React
# En production, utilise FRONTEND_URL, sinon autorise localhost
import os
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [
    frontend_url,
    "http://localhost:5173",
    "http://localhost:3000",
    "https://frontend-mon-livre-de-cuisibe.vercel.app",
    "https://*.vercel.app",
]

# Autoriser toutes les origines si en mode debug
allow_all = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== AUTH ENDPOINTS ==============

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Inscription d'un nouvel utilisateur"""
    # Vérifier si l'email existe déjà
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé"
        )
    
    # Créer l'utilisateur
    db_user = User(
        nom=user.nom,
        email=user.email,
        hashed_password=get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user


@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Connexion utilisateur - retourne un token JWT"""
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Récupère les infos de l'utilisateur connecté"""
    return current_user


# ============== RECIPES ENDPOINTS ==============

@app.get("/recipes", response_model=List[RecipeListResponse])
def get_recipes(
    categorie: CategorieRecette = None,
    search: str = None,
    auteur_id: int = None,
    tag: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Liste toutes les recettes avec filtres optionnels"""
    query = db.query(Recipe)
    
    # Filtre par catégorie
    if categorie:
        query = query.filter(Recipe.categorie == categorie)
    
    # Recherche par titre
    if search:
        query = query.filter(Recipe.titre.ilike(f"%{search}%"))
    
    # Filtre par auteur
    if auteur_id:
        query = query.filter(Recipe.auteur_id == auteur_id)
    
    # Filtre par tag (les tags sont stockés en JSON: ["tag1", "tag2"])
    if tag:
        # Recherche le tag dans le JSON string (avec ou sans guillemets)
        query = query.filter(
            Recipe.tags.ilike(f'%"{tag}"%') | Recipe.tags.ilike(f"%{tag}%")
        )
    
    recipes = query.order_by(Recipe.categorie, Recipe.titre).offset(skip).limit(limit).all()
    return recipes


@app.get("/recipes/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    """Récupère une recette par son ID avec tous les détails"""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recette non trouvée"
        )
    
    return recipe


@app.post("/recipes", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_recipe(
    recipe: RecipeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crée une nouvelle recette (authentification requise)"""
    import json
    
    # Créer la recette
    db_recipe = Recipe(
        titre=recipe.titre,
        categorie=recipe.categorie,
        temps_prep=recipe.temps_prep,
        temps_cuisson=recipe.temps_cuisson,
        temperature=recipe.temperature,
        tags=json.dumps(recipe.tags, ensure_ascii=False) if recipe.tags else None,
        auteur_id=current_user.id
    )
    db.add(db_recipe)
    db.flush()  # Pour obtenir l'ID
    
    # Ajouter les ingrédients
    for ingredient in recipe.ingredients:
        db_ingredient = Ingredient(
            nom=ingredient.nom,
            quantite=ingredient.quantite,
            unite=ingredient.unite,
            recipe_id=db_recipe.id
        )
        db.add(db_ingredient)
    
    # Ajouter les étapes
    for step in recipe.steps:
        db_step = Step(
            description=step.description,
            ordre=step.ordre,
            recipe_id=db_recipe.id
        )
        db.add(db_step)
    
    db.commit()
    db.refresh(db_recipe)
    
    return db_recipe


@app.put("/recipes/{recipe_id}", response_model=RecipeResponse)
def update_recipe(
    recipe_id: int,
    recipe_update: RecipeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Met à jour une recette (seul l'auteur peut modifier)"""
    db_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    
    if not db_recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recette non trouvée"
        )
    
    if db_recipe.auteur_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à modifier cette recette"
        )
    
    import json
    
    # Mettre à jour les champs de base
    update_data = recipe_update.model_dump(exclude_unset=True)
    
    for field in ["titre", "categorie", "temps_prep", "temps_cuisson", "temperature"]:
        if field in update_data and update_data[field] is not None:
            setattr(db_recipe, field, update_data[field])
    
    # Mettre à jour les tags
    if "tags" in update_data:
        db_recipe.tags = json.dumps(update_data["tags"], ensure_ascii=False) if update_data["tags"] else None
    
    # Mettre à jour les ingrédients si fournis
    if recipe_update.ingredients is not None:
        # Supprimer les anciens ingrédients
        db.query(Ingredient).filter(Ingredient.recipe_id == recipe_id).delete()
        # Ajouter les nouveaux
        for ingredient in recipe_update.ingredients:
            db_ingredient = Ingredient(
                nom=ingredient.nom,
                quantite=ingredient.quantite,
                unite=ingredient.unite,
                recipe_id=recipe_id
            )
            db.add(db_ingredient)
    
    # Mettre à jour les étapes si fournies
    if recipe_update.steps is not None:
        # Supprimer les anciennes étapes
        db.query(Step).filter(Step.recipe_id == recipe_id).delete()
        # Ajouter les nouvelles
        for step in recipe_update.steps:
            db_step = Step(
                description=step.description,
                ordre=step.ordre,
                recipe_id=recipe_id
            )
            db.add(db_step)
    
    db.commit()
    db.refresh(db_recipe)
    
    return db_recipe


@app.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprime une recette (seul l'auteur peut supprimer)"""
    db_recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    
    if not db_recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recette non trouvée"
        )
    
    if db_recipe.auteur_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à supprimer cette recette"
        )
    
    db.delete(db_recipe)
    db.commit()
    
    return None


# ============== FRIGO SEARCH ENDPOINT ==============

@app.post("/search/frigo", response_model=List[FrigoSearchResult])
def search_frigo(search: FrigoSearchRequest, db: Session = Depends(get_db)):
    """
    Recherche "Frigo" - Trouve les recettes par ingrédients disponibles
    
    Algorithme V2:
    1. Recherche partielle (ILIKE) des ingrédients
    2. Compte les matchs
    3. Mode Strict: ne garde que les recettes où tous les ingrédients sont trouvés
    """
    # Nettoyer les entrées
    search_ingredients = [ing.strip() for ing in search.ingredients if ing.strip()]
    
    if not search_ingredients:
        return []
    
    # Construire la condition OR ILIKE pour chaque ingrédient cherché
    # Ex: nom ILIKE %tomate% OR nom ILIKE %oeuf%
    filters = [Ingredient.nom.ilike(f"%{ing}%") for ing in search_ingredients]
    
    # Requête: trouver les recettes avec ingrédients correspondants
    matching_recipes = (
        db.query(
            Recipe.id,
            func.count(Ingredient.id).label('match_count'),
            func.group_concat(Ingredient.nom).label('matched_names')
        )
        .join(Ingredient)
        .filter(or_(*filters)) # Utilisation de OR avec ILIKE
        .group_by(Recipe.id)
        .order_by(desc('match_count'))
        .all()
    )
    
    # Construire les résultats
    results = []
    for recipe_id, match_count, matched_names in matching_recipes:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        
        # Filtre Mode Strict
        if search.strict_mode:
            # On vérifie si on a trouvé tous les ingrédients nécessaires
            # Note: len(recipe.ingredients) charge les ingrédients si pas déjà chargés
            total_ingredients = len(recipe.ingredients)
            if match_count < total_ingredients:
                continue

        # Parser les noms matchés
        matched_list = matched_names.split(',') if matched_names else []
        
        results.append(FrigoSearchResult(
            recipe=RecipeListResponse.model_validate(recipe),
            match_count=match_count,
            matched_ingredients=matched_list
        ))
    
    return results


# ============== ADMIN ENDPOINTS ==============

def require_admin(current_user: User = Depends(get_current_user)):
    """Vérifie que l'utilisateur est admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    return current_user


@app.get("/admin/users", response_model=List[UserResponse])
def get_all_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Liste tous les utilisateurs (admin only)"""
    return db.query(User).all()


@app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Supprime un utilisateur (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")
    db.delete(user)
    db.commit()
    return None


@app.delete("/admin/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_recipe(
    recipe_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Supprime n'importe quelle recette (admin only)"""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recette non trouvée")
    db.delete(recipe)
    db.commit()
    return None


@app.put("/admin/users/{user_id}/toggle-admin", response_model=UserResponse)
def toggle_admin(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Promouvoir/rétrograder un utilisateur admin (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Impossible de modifier votre propre statut")
    user.is_admin = not user.is_admin
    db.commit()
    db.refresh(user)
    return user


@app.put("/admin/make-first-admin", response_model=UserResponse)
def make_first_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Promouvoir le premier admin - fonctionne UNIQUEMENT s'il n'y a aucun admin.
    L'utilisateur connecté devient admin.
    """
    # Vérifier s'il y a déjà un admin
    existing_admin = db.query(User).filter(User.is_admin == True).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Un administrateur existe déjà. Utilisez l'endpoint toggle-admin."
        )
    
    # Promouvoir l'utilisateur actuel
    current_user.is_admin = True
    db.commit()
    db.refresh(current_user)
    return current_user


# ============== ROOT ENDPOINT ==============

@app.get("/")
def root():
    """Endpoint racine - info API"""
    return {
        "message": "Bienvenue sur MonLivreDeCuisine API",
        "docs": "/docs",
        "version": "2.0.0"
    }


@app.get("/debug/error")
def debug_error(db: Session = Depends(get_db)):
    try:
        results = db.query(Recipe).all()
        # Convertir en dict pour éviter problème de sérialisation si Enum
        sample = []
        for r in results[:10]:
            sample.append({
                "id": r.id,
                "titre": r.titre,
                "categorie": str(r.categorie), # Force string
                "tags": r.tags
            })
        return {"status": "ok", "count": len(results), "sample": sample}
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

