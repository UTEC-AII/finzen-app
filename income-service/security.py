# Verificación de tokens JWT compartidos entre microservicios.
# Todos los servicios usan el mismo SECRET_KEY para validar el token emitido por user-service.
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.getenv("SECRET_KEY", "finzen-dev-secret-change-me")
ALGORITHM = "HS256"

# Esquema de seguridad que lee el encabezado "Authorization: Bearer <token>".
security_scheme = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> str:
    # Dependencia reutilizable: valida el token y devuelve el id del usuario autenticado.
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no contiene un usuario válido",
        )
    return user_id
