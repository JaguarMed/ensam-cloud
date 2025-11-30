"""
Authentication module for the Client App.

Handles:
- JWT token validation from remote server
- Local session management
- Authentication middleware/dependencies
"""

from fastapi import Request, HTTPException, status
from typing import Optional, Dict, Any
from .utils.jwt_manager import (
    decode_token,
    is_token_expired,
    get_user_from_token
)


async def get_token_from_request(request: Request) -> Optional[str]:
    """
    Extract JWT token from request.
    Checks Authorization header first, then cookies.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Token string or None
    """
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]
    
    # Check cookie
    token = request.cookies.get("access_token")
    if token:
        return token
    
    return None


async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User info dict or None if not authenticated
    """
    token = await get_token_from_request(request)
    
    if not token:
        return None
    
    if is_token_expired(token):
        return None
    
    return get_user_from_token(token)


async def require_auth(request: Request) -> Dict[str, Any]:
    """
    Dependency that requires authentication.
    Raises HTTPException if not authenticated.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User info dict
        
    Raises:
        HTTPException: If not authenticated
    """
    user = await get_current_user(request)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user


def validate_server_token(token: str) -> bool:
    """
    Validate a token received from the remote server.
    
    Args:
        token: JWT token from server
        
    Returns:
        True if valid, False otherwise
    """
    if not token:
        return False
    
    if is_token_expired(token):
        return False
    
    payload = decode_token(token)
    return payload is not None








