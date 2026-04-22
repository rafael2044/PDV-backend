from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models, auth
from app.dependencies import allow_admin_only
from pydantic import BaseModel

router = APIRouter(tags=["Auth"])

# Schema simples só para criar usuário
class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: models.UserRole = models.UserRole.SELLER # Padrão é vendedor

@router.post("/register", dependencies=[Depends(allow_admin_only)])
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # Verifica user existente
    result = await db.execute(select(models.User).where(models.User.username == user.username))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username já existe")
    
    hashed_pw = auth.get_password_hash(user.password)
    
    new_user = models.User(
        username=user.username,
        name=user.name,
        hashed_password=hashed_pw,
        role=user.role # Salva o cargo escolhido
    )
    db.add(new_user)
    await db.commit()
    return {"message": "Usuário criado com sucesso"}

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    # Busca user
    result = await db.execute(select(models.User).where(models.User.username == form_data.username))
    user = result.scalars().first()
    
    # VERIFICAÇÃO DE STATUS
    if user and not user.is_active:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário inativo. Contate o administrador."
        )

    # Verificação de Senha
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "name": user.name
    }