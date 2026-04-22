from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession


from app.database import get_db
from app.config import settings
from app.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Busca o usuário no banco
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    if user is None:
        raise credentials_exception
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Operação não permitida para seu nível de acesso."
            )
        return user

# Instâncias prontas para usar nas rotas
allow_admin_only = RoleChecker([UserRole.ADMIN])
allow_manager = RoleChecker([UserRole.ADMIN, UserRole.MANAGER]) # Admin também pode o que Gerente pode
allow_seller = RoleChecker([UserRole.ADMIN, UserRole.MANAGER, UserRole.SELLER])