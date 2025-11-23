import os
import bcrypt
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.orm import Session
from models import User
from typing import Optional


# Secret key for session signing
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-random-secret-key-in-production")
serializer = URLSafeTimedSerializer(SECRET_KEY)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def create_session_token(user_id: int) -> str:
    """Create a signed session token for a user."""
    return serializer.dumps({"user_id": user_id})


def verify_session_token(token: str, max_age: int = 86400 * 30) -> Optional[dict]:
    """Verify and decode a session token. Returns None if invalid."""
    try:
        data = serializer.loads(token, max_age=max_age)
        return data
    except Exception:
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user by email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_default_admin_user(db: Session):
    """Create the default admin user if it doesn't exist."""
    existing_user = db.query(User).filter(User.email == "admin@example.com").first()
    if not existing_user:
        admin_user = User(
            email="admin@example.com",
            password_hash=hash_password("admin123")
        )
        db.add(admin_user)
        db.commit()
        print("Default admin user created: admin@example.com / admin123")
