import uuid
import bcrypt
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.models import User
from app.schemas.schemas import UserRegisterRequest, UserLoginRequest, UserResponse, AuthResponse


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verifies a plaintext password against the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def register_user(db: Session, data: UserRegisterRequest) -> AuthResponse:
    email = data.email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    # Check if user already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    hashed = hash_password(data.password)
    user = User(
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        country=data.country.strip() if data.country else "United States",
        email=email,
        hashed_password=hashed,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = f"agy_{uuid.uuid4().hex}"
    return AuthResponse(
        token=token,
        user=UserResponse.model_validate(user)
    )


def login_user(db: Session, data: UserLoginRequest) -> AuthResponse:
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = f"agy_{uuid.uuid4().hex}"
    return AuthResponse(
        token=token,
        user=UserResponse.model_validate(user)
    )


def get_user_by_id(db: Session, user_id: int) -> UserResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserResponse.model_validate(user)
