"""
JWT Manager - Handles JWT token operations for the client app.

This module provides utilities for:
- Creating and verifying JWT tokens locally (for session management)
- Extracting user information from tokens
- Token expiration checking
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os

# Configuration - In production, use environment variables
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "client-app-secret-key-for-local-session")
ALGORITHM = "HS256"
LOCAL_TOKEN_EXPIRE_MINUTES = 60


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification.
    Used to extract payload from tokens received from the remote server.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        # Decode without verification (server already verified)
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except jwt.InvalidTokenError:
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if a JWT token is expired.
    
    Args:
        token: JWT token string
        
    Returns:
        True if expired, False otherwise
    """
    payload = decode_token(token)
    if not payload:
        return True
    
    exp = payload.get("exp")
    if not exp:
        return True
    
    return datetime.utcnow().timestamp() > exp


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Extract user information from a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        User info dict with id, email, name or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name", "User")
    }


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get the expiration datetime of a token.
    
    Args:
        token: JWT token string
        
    Returns:
        Expiration datetime or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    
    exp = payload.get("exp")
    if not exp:
        return None
    
    return datetime.fromtimestamp(exp)


def create_local_session_token(user_data: Dict[str, Any]) -> str:
    """
    Create a local session token for the client app.
    This is separate from the server token and used for local session management.
    
    Args:
        user_data: User information to encode
        
    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(minutes=LOCAL_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(user_data.get("id", "")),
        "email": user_data.get("email", ""),
        "name": user_data.get("name", "User"),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_local_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a local session token.
    
    Args:
        token: Local session JWT token
        
    Returns:
        User info dict or None if invalid/expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "name": payload.get("name")
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None








