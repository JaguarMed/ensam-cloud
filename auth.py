"""
Authentication module for the Cloud Python Execution Platform.
Handles JWT token creation, verification, and user authentication.
"""

from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

# ============================================================================
# Configuration
# ============================================================================

SECRET_KEY = "your-super-secret-key-change-in-production-2025"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Hardcoded user for demo (in production, use a database)
DEMO_USERS = {
    "admin@cloud.com": {
        "id": 1,
        "email": "admin@cloud.com",
        "password": "admin123",  # In production, use hashed passwords!
        "name": "Admin User"
    },
    "demo@ensam.ma": {
        "id": 2,
        "email": "demo@ensam.ma",
        "password": "demo123",
        "name": "Demo Student"
    }
}


# ============================================================================
# JWT Token Functions
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data to encode (should include user info)
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Authenticate a user with email and password.
    
    Args:
        email: User's email address
        password: User's password
        
    Returns:
        User dict if authenticated, None otherwise
    """
    user = DEMO_USERS.get(email)
    if user and user["password"] == password:
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"]
        }
    return None


# ============================================================================
# FastAPI Dependencies
# ============================================================================

async def get_current_user(request: Request) -> Optional[dict]:
    """
    Extract and verify the current user from the request.
    Checks Authorization header for Bearer token.
    
    Returns:
        User dict if authenticated, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    
    if not payload:
        return None
    
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name", "User")
    }


async def require_auth(request: Request):
    """
    Dependency that requires authentication.
    Raises HTTPException if not authenticated.
    """
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


def check_auth_cookie(request: Request) -> Optional[dict]:
    """
    Check for JWT in cookie (alternative to header).
    Used for page rendering.
    """
    token = request.cookies.get("access_token")
    if token:
        return verify_token(token)
    return None








