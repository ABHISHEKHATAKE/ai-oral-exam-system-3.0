from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta

from app.models.schemas import Token, SignUp
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.core.config import get_settings
from app.services.mongo_service import mongo_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()

# In-memory user database (replace with real database)
users_db = {
    "instructor@university.edu": {
        "username": "instructor@university.edu",
        "hashed_password": "$2b$12$example_bcrypt_hash",
        "role": "instructor"
    }
}

@router.post("/signup")
def signup(request: SignUp):
    """Register a new user"""
    # Check in MongoDB first
    existing = mongo_service.get_user_by_username(request.username) if mongo_service.is_connected() else None
    if existing or request.username in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    
    if request.role not in ["instructor", "student"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'instructor' or 'student'"
        )
    
    hashed_password = get_password_hash(request.password)
    user_record = {
        "username": request.username,
        "hashed_password": hashed_password,
        "role": request.role
    }
    users_db[request.username] = user_record
    # Persist to MongoDB
    try:
        mongo_service.create_user(user_record)
    except Exception:
        pass
    
    return {"message": "User created successfully", "username": request.username}

@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login and get access token"""
    # Try MongoDB first
    user = None
    try:
        if mongo_service.is_connected():
            user = mongo_service.get_user_by_username(form_data.username)
    except Exception:
        user = None

    if not user:
        user = users_db.get(form_data.username)

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}
