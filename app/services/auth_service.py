from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from app.core.config import settings
from app.schemas.context import UserContext

# Estrae "Authorization: Bearer <token>"
security = HTTPBearer()  # puoi fare HTTPBearer(auto_error=True) per 403 su header mancante

class AuthService:
    # Valori presi da env/config
    JWT_ALGORITHM = settings.jwt_algorithm          # es: "RS256" o "HS256"
    PUBLIC_KEY = settings.jwt_public_key            # PEM per RS*, chiave segreta per HS*

    @staticmethod
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> UserContext:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token,
                AuthService.PUBLIC_KEY,
                algorithms=[AuthService.JWT_ALGORITHM],
                # facoltativi se li usi:
                # audience=settings.jwt_audience,
                # issuer=settings.jwt_issuer,
            )

            user_id = payload.get("sub")
            role = payload.get("role")  # può essere str o list[str] in base a come emetti il token

            if not user_id or role is None:
                raise HTTPException(status_code=401, detail="Invalid token payload")

            return UserContext(user_id=user_id, role=role)

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
