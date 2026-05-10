from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings

bearer = HTTPBearer(auto_error=False)

VALID_TOKEN = settings.secret_key


async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials or credentials.credentials != VALID_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def get_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    """Returns token or None — for optional auth."""
    if credentials:
        return credentials.credentials
    return None
