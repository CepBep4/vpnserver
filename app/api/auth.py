from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import timedelta
from app.core.config import settings
from app.core.security import create_access_token

router = APIRouter(
    tags=["authentication"]
)


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Авторизация",
    description="Получение JWT токена для доступа к API"
)
async def login(login_data: LoginRequest):
    """
    Эндпоинт для авторизации.
    
    Принимает логин и пароль в теле запроса (JSON).
    Возвращает JWT токен для дальнейшей работы с API.
    
    - **login**: логин администратора
    - **password**: пароль администратора
    """
    # Проверяем учетные данные из конфига
    if login_data.login != settings.ADMIN_USERNAME or login_data.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )
    
    # Создаем токен
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": login_data.login},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer"
    )
