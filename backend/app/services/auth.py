import uuid
import bcrypt
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.models import User
from app.schemas.schemas import UserRegisterRequest, UserLoginRequest, UserResponse, AuthResponse
from app.services.time_utils import get_ist_now


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


def register_user(db: Session, data: UserRegisterRequest, ip: str = None, user_agent: str = None) -> AuthResponse:
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
    now = get_ist_now()
    user = User(
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        country=data.country.strip() if data.country else "United States",
        email=email,
        hashed_password=hashed,
        login_count=1,
        visit_count=1,
        last_login_at=now,
        last_visit_at=now,
        last_ip=ip,
        last_user_agent=user_agent[:512] if user_agent else None,
        created_at=now,
    )
    db.add(user)
    db.flush()

    # Log registration + first login activity
    from app.models.models import UserActivity
    act = UserActivity(
        user_id=user.id,
        email=user.email,
        user_name=f"{user.first_name} {user.last_name}",
        activity_type="REGISTER_AND_LOGIN",
        ip_address=ip,
        user_agent=user_agent[:512] if user_agent else None,
        page_url="/auth/register",
        details_json='{"status": "Account registered and logged in successfully"}',
        timestamp=now
    )
    db.add(act)
    db.commit()
    db.refresh(user)

    token = f"agy_{uuid.uuid4().hex}"
    return AuthResponse(
        token=token,
        user=UserResponse.model_validate(user),
        expires_in_minutes=30
    )


def login_user(db: Session, data: UserLoginRequest, ip: str = None, user_agent: str = None) -> AuthResponse:
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    now = get_ist_now()
    user.login_count = (user.login_count or 0) + 1
    user.visit_count = (user.visit_count or 0) + 1
    user.last_login_at = now
    user.last_visit_at = now
    if ip:
        user.last_ip = ip
    if user_agent:
        user.last_user_agent = user_agent[:512]

    from app.models.models import UserActivity
    act = UserActivity(
        user_id=user.id,
        email=user.email,
        user_name=f"{user.first_name} {user.last_name}",
        activity_type="LOGIN",
        ip_address=ip,
        user_agent=user_agent[:512] if user_agent else None,
        page_url="/auth/login",
        details_json=f'{{"login_number": {user.login_count}, "status": "SUCCESS"}}',
        timestamp=now
    )
    db.add(act)
    db.commit()
    db.refresh(user)

    token = f"agy_{uuid.uuid4().hex}"
    return AuthResponse(
        token=token,
        user=UserResponse.model_validate(user),
        expires_in_minutes=30
    )


def record_user_activity(
    db: Session,
    activity_type: str,
    user_id: int = None,
    email: str = None,
    ip: str = None,
    user_agent: str = None,
    page_url: str = None,
    details_json: str = None
):
    """Persists a real user audit trail entry into user_activities in PostgreSQL/Neon."""
    from app.models.models import UserActivity
    now = get_ist_now()
    user = None
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    elif email:
        user = db.query(User).filter(User.email == email.strip().lower()).first()

    if user:
        user_name = f"{user.first_name} {user.last_name}"
        email = user.email
        user_id = user.id
        if activity_type == "VISIT":
            user.visit_count = (user.visit_count or 0) + 1
            user.last_visit_at = now
            if ip:
                user.last_ip = ip
            if user_agent:
                user.last_user_agent = user_agent[:512]
    else:
        user_name = "Anonymous Visitor"

    act = UserActivity(
        user_id=user_id,
        email=email,
        user_name=user_name,
        activity_type=activity_type,
        ip_address=ip,
        user_agent=user_agent[:512] if user_agent else None,
        page_url=page_url or "/",
        details_json=details_json,
        timestamp=now
    )
    db.add(act)
    db.commit()
    return act


def get_user_activity_stats(db: Session, limit: int = 100):
    """Retrieves aggregated user activity stats and recent logs from Neon/PostgreSQL."""
    from app.models.models import UserActivity
    from app.schemas.schemas import UserActivityStatsResponse, UserActivityItem, UserResponse

    total_users = db.query(User).count()
    users = db.query(User).order_by(User.last_visit_at.desc().nulls_last()).all()
    total_logins = sum((u.login_count or 0) for u in users)
    total_visits = sum((u.visit_count or 0) for u in users)

    recent_acts = (
        db.query(UserActivity)
        .order_by(UserActivity.timestamp.desc())
        .limit(limit)
        .all()
    )

    return UserActivityStatsResponse(
        total_users=total_users,
        total_logins=total_logins,
        total_visits=total_visits,
        users=[UserResponse.model_validate(u) for u in users],
        recent_activities=[UserActivityItem.model_validate(a) for a in recent_acts]
    )


def get_user_by_id(db: Session, user_id: int) -> UserResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return UserResponse.model_validate(user)
