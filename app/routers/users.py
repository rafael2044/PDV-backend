# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app import models, auth
from app.dependencies import allow_manager, allow_admin_only, get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

# --- SCHEMAS ---
class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None # Opcional: permitir trocar senha

# --- ROTAS ---

# 1. Listar Usuários (Apenas Manager/Admin)
@router.get("/", response_model=List[UserResponse], dependencies=[Depends(allow_manager)])
async def read_users(active_only: bool = False, db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    query = select(models.User)
    if active_only:
        query = query.where(models.User.is_active == True)
    
    result = await db.execute(query)
    return result.scalars().all()

# 2. Obter um Usuário (Para edição)
@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(allow_manager)])
async def read_user(user_id: int, db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

# 3. Atualizar Usuário (Editar ou Inativar)
@router.put("/{user_id}", dependencies=[Depends(allow_admin_only)]) # Só Admin edita usuários
async def update_user(user_id: int, user_in: UserUpdate, db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
    # Atualiza campos se enviados
    if user_in.name: user.name = user_in.name
    if user_in.role: user.role = user_in.role
    if user_in.is_active is not None: user.is_active = user_in.is_active
    
    # Se enviou senha nova, faz o hash
    if user_in.password:
        user.hashed_password = auth.get_password_hash(user_in.password)

    await db.commit()
    return {"message": "Usuário atualizado com sucesso"}

# 4. Deletar Usuário (Físico - Só se não tiver histórico)
@router.delete("/{user_id}", dependencies=[Depends(allow_admin_only)])
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Verifica se tem vendas ou sessões de caixa
    # (Poderíamos checar tabela por tabela, mas o IntegrityError do banco já faz isso)
    try:
        await db.delete(user)
        await db.commit()
        return {"message": "Usuário excluído permanentemente"}
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400, 
            detail="Não é possível excluir: Este usuário possui histórico de vendas ou caixas."
        )