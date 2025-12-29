"""
Schémas Pydantic pour validation des données API
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum


class CategorieRecette(str, Enum):
    """Catégories de recettes"""
    ENTREE = "Entrée"
    PLAT = "Plat"
    DESSERT = "Dessert"
    GOURMANDISES = "Gourmandises"


# ============== USER SCHEMAS ==============

class UserBase(BaseModel):
    nom: str = Field(..., min_length=2, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    is_admin: bool = False

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ============== INGREDIENT SCHEMAS ==============

class IngredientBase(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100)
    quantite: Optional[float] = None
    unite: Optional[str] = Field(None, max_length=50)


class IngredientCreate(IngredientBase):
    pass


class IngredientResponse(IngredientBase):
    id: int

    class Config:
        from_attributes = True


# ============== STEP SCHEMAS ==============

class StepBase(BaseModel):
    description: str = Field(..., min_length=1, max_length=1000)
    ordre: int = Field(..., ge=1)


class StepCreate(StepBase):
    pass


class StepResponse(StepBase):
    id: int

    class Config:
        from_attributes = True


# ============== RECIPE SCHEMAS ==============

class RecipeBase(BaseModel):
    titre: str = Field(..., min_length=2, max_length=200)
    categorie: CategorieRecette
    temps_prep: Optional[int] = Field(None, ge=0)
    temps_cuisson: Optional[int] = Field(None, ge=0)
    temperature: Optional[int] = Field(None, ge=0)


class RecipeCreate(RecipeBase):
    ingredients: List[IngredientCreate] = []
    steps: List[StepCreate] = []


class RecipeUpdate(BaseModel):
    titre: Optional[str] = Field(None, min_length=2, max_length=200)
    categorie: Optional[CategorieRecette] = None
    temps_prep: Optional[int] = Field(None, ge=0)
    temps_cuisson: Optional[int] = Field(None, ge=0)
    temperature: Optional[int] = Field(None, ge=0)
    ingredients: Optional[List[IngredientCreate]] = None
    steps: Optional[List[StepCreate]] = None


class RecipeResponse(RecipeBase):
    id: int
    auteur_id: int
    auteur: UserResponse
    ingredients: List[IngredientResponse] = []
    steps: List[StepResponse] = []

    class Config:
        from_attributes = True


class RecipeListResponse(RecipeBase):
    """Version allégée pour les listes"""
    id: int
    auteur_id: int
    auteur: UserResponse

    class Config:
        from_attributes = True


# ============== FRIGO SEARCH SCHEMAS ==============

class FrigoSearchRequest(BaseModel):
    ingredients: List[str] = Field(..., min_items=1)


class FrigoSearchResult(BaseModel):
    recipe: RecipeListResponse
    match_count: int
    matched_ingredients: List[str]
