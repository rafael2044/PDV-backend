from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


from app.config import settings

# O driver deve ser postgresql+asyncpg://...
engine = create_async_engine(settings.DATABASE_URL, echo=False)

SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Dependência para injetar a sessão nas rotas
async def get_db():
    async with SessionLocal() as db:
        yield db