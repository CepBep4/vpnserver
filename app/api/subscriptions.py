from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.subscription import Subscription
from app.services.vless import disable_vless_profile, create_vless_profile, extract_uuid_from_link, generate_vless_link_only
from app.services.xray_manager import is_user_in_xray, add_user_to_xray

router = APIRouter(
    tags=["subscriptions"]
)


class SubscriptionCreate(BaseModel):
    username: str
    password: str
    active: bool = True


class SubscriptionUpdate(BaseModel):
    active: bool


class SubscriptionResponse(BaseModel):
    id: int
    username: str
    password: str
    active: bool
    link: str | None

    class Config:
        from_attributes = True


@router.post(
    "/add",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить пользователя",
    description="Добавление нового пользователя (подписки) в систему"
)
async def add_subscription(
    subscription_data: SubscriptionCreate,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Добавляет нового пользователя в систему.
    
    Требует валидный JWT токен в заголовке Authorization.
    
    - **username**: уникальное имя пользователя (может быть числом)
    - **password**: пароль пользователя
    - **active**: активна ли подписка (по умолчанию True)
    
    Поле `link` не указывается при создании, оно будет сгенерировано автоматически Celery для активных подписок.
    """
    # Проверяем, существует ли пользователь с таким username
    existing_subscription = db.query(Subscription).filter(
        Subscription.username == subscription_data.username
    ).first()
    
    if existing_subscription:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Пользователь с username '{subscription_data.username}' уже существует"
        )
    
    # Создаем новую подписку
    # link всегда None при создании, будет сгенерирован автоматически Celery
    new_subscription = Subscription(
        username=subscription_data.username,
        password=subscription_data.password,
        active=subscription_data.active,
        link=None
    )
    
    try:
        db.add(new_subscription)
        db.commit()
        db.refresh(new_subscription)
        
        return SubscriptionResponse(
            id=new_subscription.id,
            username=new_subscription.username,
            password=new_subscription.password,
            active=new_subscription.active,
            link=new_subscription.link
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при добавлении пользователя: {str(e)}"
        )


@router.get(
    "/users",
    response_model=List[SubscriptionResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить всех пользователей",
    description="Возвращает список всех пользователей (подписок) в системе"
)
async def get_all_users(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает список всех пользователей в системе.
    
    Требует валидный JWT токен в заголовке Authorization.
    
    Возвращает список всех подписок с их данными:
    - id, username, password, active, link
    """
    subscriptions = db.query(Subscription).all()
    
    return [
        SubscriptionResponse(
            id=sub.id,
            username=sub.username,
            password=sub.password,
            active=sub.active,
            link=sub.link
        )
        for sub in subscriptions
    ]


@router.patch(
    "/patch/{username}",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Изменить состояние пользователя",
    description="Изменяет поле active для пользователя с указанным username"
)
async def patch_user(
    username: str,
    update_data: SubscriptionUpdate,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Изменяет состояние пользователя (поле active).
    
    Требует валидный JWT токен в заголовке Authorization.
    
    - **username**: имя пользователя для поиска
    - **active**: новое значение состояния (True/False)
    
    Можно изменять только поле active.
    """
    # Находим пользователя по username
    subscription = db.query(Subscription).filter(
        Subscription.username == username
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Пользователь с username '{username}' не найден"
        )
    
    # Сохраняем старое значение active для проверки изменений
    old_active = subscription.active
    new_active = update_data.active
    
    # Обновляем только поле active
    subscription.active = new_active
    
    try:
        db.commit()
        db.refresh(subscription)
        
        # Если статус изменился и есть ссылка, немедленно применяем изменения в Xray
        if old_active != new_active and subscription.link:
            if new_active:
                # Активируем пользователя в Xray
                # Всегда добавляем/обновляем пользователя с правильным UUID из ссылки
                uuid_from_link = extract_uuid_from_link(subscription.link)
                if uuid_from_link:
                    email = f"{subscription.username}@sunstrikevpn.local"
                    # add_user_to_xray обрабатывает дубликаты и гарантирует правильный UUID
                    add_user_to_xray(uuid_from_link, email)
                else:
                    print(f"⚠ Предупреждение: не удалось извлечь UUID из ссылки для пользователя {subscription.username}")
            else:
                # Отключаем пользователя из Xray немедленно
                disable_vless_profile(subscription)
        
        return SubscriptionResponse(
            id=subscription.id,
            username=subscription.username,
            password=subscription.password,
            active=subscription.active,
            link=subscription.link
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении пользователя: {str(e)}"
        )


class LinkRequest(BaseModel):
    username: str
    password: str


class LinkResponse(BaseModel):
    link: str


@router.post(
    "/link",
    response_model=LinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить ссылку VPN",
    description="Возвращает VLESS ссылку для пользователя по username и password. Создает пользователя если его нет."
)
async def get_link(
    link_data: LinkRequest,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Возвращает VLESS ссылку для пользователя.
    
    Требует валидный JWT токен в заголовке Authorization.
    
    Если пользователя нет в базе - создает его с active=False.
    Если пользователь существует - использует его данные.
    Ссылка всегда генерируется сразу и является действительной.
    
    - **username**: имя пользователя
    - **password**: пароль пользователя
    
    Возвращает корректную VLESS ссылку с именем из конфига (VPN_NAME).
    """
    from app.services.vless import generate_uuid_from_credentials, generate_vless_link_only, extract_uuid_from_link
    from app.services.xray_manager import is_user_in_xray, add_user_to_xray
    
    # Ищем пользователя в базе данных
    subscription = db.query(Subscription).filter(
        Subscription.username == link_data.username
    ).first()
    
    user_created = False
    
    if not subscription:
        # Пользователя нет - создаем его с active=False
        user_uuid = generate_uuid_from_credentials(link_data.username, link_data.password)
        link = generate_vless_link_only(user_uuid)
        
        subscription = Subscription(
            username=link_data.username,
            password=link_data.password,
            active=False,  # Пользователи созданные через /link неактивны по умолчанию
            link=link
        )
        
        try:
            db.add(subscription)
            db.commit()
            db.refresh(subscription)
            user_created = True
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при создании пользователя: {str(e)}"
            )
    else:
        # Пользователь существует - проверяем пароль
        if subscription.password != link_data.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный пароль"
            )
        
        # Если у пользователя нет ссылки - генерируем её
        if not subscription.link:
            user_uuid = generate_uuid_from_credentials(link_data.username, link_data.password)
            link = generate_vless_link_only(user_uuid)
            subscription.link = link
            try:
                db.commit()
                db.refresh(subscription)
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Ошибка при сохранении ссылки: {str(e)}"
                )
        else:
            # Используем существующую ссылку или генерируем новую с правильным именем
            user_uuid = extract_uuid_from_link(subscription.link)
            if not user_uuid:
                # Если не удалось извлечь UUID, генерируем детерминированно
                user_uuid = generate_uuid_from_credentials(link_data.username, link_data.password)
                link = generate_vless_link_only(user_uuid)
                subscription.link = link
                db.commit()
            else:
                # Генерируем ссылку с правильным именем из конфига
                link = generate_vless_link_only(user_uuid)
                # Обновляем ссылку если имя изменилось
                if subscription.link != link:
                    subscription.link = link
                    db.commit()
    
    # Если пользователь активен и его нет в Xray - добавляем
    if subscription.active:
        user_uuid = extract_uuid_from_link(subscription.link)
        if user_uuid and not is_user_in_xray(user_uuid):
            email = f"{subscription.username}@sunstrikevpn.local"
            add_user_to_xray(user_uuid, email)
    
    return LinkResponse(link=link)

