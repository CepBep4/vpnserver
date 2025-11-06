from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# Схема безопасности для извлечения токена из заголовка
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создает JWT токен доступа.
    
    Args:
        data: Данные для включения в токен
        expires_delta: Время жизни токена
    
    Returns:
        Закодированный JWT токен
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Проверяет JWT токен и возвращает данные из токена.
    
    Args:
        credentials: Учетные данные из заголовка Authorization
    
    Returns:
        Декодированные данные токена
    
    Raises:
        HTTPException: Если токен невалиден или отсутствует
    """
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный токен",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(payload: dict = Depends(verify_token)) -> str:
    """
    Извлекает текущего пользователя из токена.
    
    Args:
        payload: Декодированные данные токена
    
    Returns:
        Имя пользователя
    """
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username

