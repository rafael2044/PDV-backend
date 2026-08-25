from fastapi import FastAPI
from sqlalchemy import select
from fastapi.middleware.cors import CORSMiddleware


from app.routers import sales, products, cashier, auth, users, stock, reports, backup, settings as settings_router
from app.database import engine, Base, SessionLocal
from app.models import User
from app.auth import get_password_hash
from app.models import UserRole
from app.config import settings

app = FastAPI(title="PDV System API")

# Configuração de CORS (Essencial para o Next.js conversar com FastAPI)
origins = [settings.URL_FRONTEND]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Criar tabelas ao iniciar (apenas para dev/teste rápido)
# Em produção, use Alembic para migrações
@app.on_event("startup")
async def startup():
    # 1. Cria as tabelas no banco se não existirem (sempre roda para garantir)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Verifica se precisa criar o Admin Padrão
    async with SessionLocal() as db:
        # Busca se existe QUALQUER usuário no banco
        result = await db.execute(select(User))
        user = result.scalars().first()
        
        # Se não existir NENHUM usuário, cria o admin automaticamente
        if not user:
            print("\n--- Inicialização: Banco de usuários vazio ---")
            print("Criando usuário 'admin' padrão...")
            
            admin_user = User(
                name="Administrador do Sistema",
                username="admin",
                hashed_password=get_password_hash("admin123"), # Senha padrão: admin
                role=UserRole.ADMIN,
                is_active=True
            )
            
            db.add(admin_user)
            await db.commit()
            print("✅ Usuário criado com sucesso!")
            print("👉 Login: admin")
            print("👉 Senha: admin123\n")
        else:
            print("\n--- Inicialização: O sistema já possui usuários cadastrados. ---\n")

# Registrar Rotas
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cashier.router)
app.include_router(sales.router)
app.include_router(users.router)
app.include_router(stock.router)
app.include_router(reports.router)
app.include_router(backup.router)
app.include_router(settings_router.router)

@app.get("/")
async def root():
    return {"status": "PDV API Online"}
