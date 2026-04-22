import os
import json
import shutil
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, delete
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.dependencies import allow_admin_only, get_current_user

router = APIRouter(prefix="/backup", tags=["Backup"])

BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

# --- Schemas ---
class BackupStats(BaseModel):
    products: int
    users: int
    sales: int
    stock_movements: int
    last_backup: str | None

class BackupFile(BaseModel):
    filename: str
    size_kb: float
    created_at: str

# --- Rotas ---

@router.get("/stats", dependencies=[Depends(allow_admin_only)])
async def get_stats(db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    """Retorna contagem de registros para o dashboard"""
    products = await db.scalar(select(func.count(models.Product.id)))
    users = await db.scalar(select(func.count(models.User.id)))
    sales = await db.scalar(select(func.count(models.Sale.id)))
    movements = await db.scalar(select(func.count(models.StockMovement.id)))

    # Busca o arquivo mais recente
    files = sorted(os.listdir(BACKUP_DIR), reverse=True)
    last_backup = None
    if files:
        # Tenta formatar a data do nome do arquivo backup_YYYYMMDD_HHMMSS.json
        try:
            ts = files[0].replace("backup_", "").replace(".json", "")
            dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
            last_backup = dt.strftime("%d/%m/%Y às %H:%M")
        except:
            last_backup = files[0]

    return {
        "products": products,
        "users": users,
        "sales": sales,
        "stock_movements": movements,
        "last_backup": last_backup
    }

@router.post("/create", dependencies=[Depends(allow_admin_only)])
async def create_backup(db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    """Gera um arquivo JSON com todos os dados do banco"""
    
    # 1. Extrair dados
    # Usamos scalars().all() para pegar os objetos
    users = (await db.execute(select(models.User))).scalars().all()
    products = (await db.execute(select(models.Product))).scalars().all()
    sessions = (await db.execute(select(models.CashierSession))).scalars().all()
    sales = (await db.execute(select(models.Sale))).scalars().all()
    sale_items = (await db.execute(select(models.SaleItem))).scalars().all()
    movements = (await db.execute(select(models.StockMovement))).scalars().all()

    # 2. Serializar para Dicionário
    # Função auxiliar para converter objeto SQLAlchemy em dict
    def to_dict(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    # Precisamos serializar datas para string (JSON não suporta datetime nativo)
    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    data = {
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "users": [to_dict(u) for u in users],
        "products": [to_dict(p) for p in products],
        "sessions": [to_dict(s) for s in sessions],
        "sales": [to_dict(s) for s in sales],
        "sale_items": [to_dict(si) for si in sale_items],
        "stock_movements": [to_dict(m) for m in movements]
    }

    # 3. Salvar Arquivo
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    with open(filepath, "w", encoding='utf-8') as f:
        json.dump(data, f, default=json_serial, indent=2)

    return {"message": "Backup criado com sucesso", "filename": filename}

@router.get("/list", response_model=List[BackupFile], dependencies=[Depends(allow_admin_only)])
async def list_backups(
    current_user: models.User = Depends(get_current_user)
):
    """Lista arquivos na pasta backups"""
    files = []
    if not os.path.exists(BACKUP_DIR):
        return []

    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".json"):
            path = os.path.join(BACKUP_DIR, f)
            stat = os.stat(path)
            dt = datetime.fromtimestamp(stat.st_mtime)
            files.append({
                "filename": f,
                "size_kb": round(stat.st_size / 1024, 2),
                "created_at": dt.strftime("%d/%m/%Y %H:%M:%S")
            })
    
    # Ordenar por mais recente
    return sorted(files, key=lambda x: x['filename'], reverse=True)

@router.get("/download/{filename}", dependencies=[Depends(allow_admin_only)])
async def download_backup(filename: str,
    current_user: models.User = Depends(get_current_user)):
    path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(path, filename=filename, media_type='application/json')

@router.post("/restore", dependencies=[Depends(allow_admin_only)])
async def restore_backup(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    """Restaura um backup (PERIGO: Apaga dados atuais)"""
    
    try:
        content = await file.read()
        data = json.loads(content)
    except:
        raise HTTPException(400, "Arquivo de backup inválido ou corrompido")

    # Ordem de Limpeza (Filhos -> Pais para evitar erro de FK)
    await db.execute(delete(models.StockMovement))
    await db.execute(delete(models.SaleItem))
    await db.execute(delete(models.Sale))
    await db.execute(delete(models.CashierSession))
    await db.execute(delete(models.Product))
    await db.execute(delete(models.User))
    
    # Ordem de Inserção (Pais -> Filhos)
    
    # 1. Users
    for item in data.get("users", []):
        db.add(models.User(**item))
    
    # 2. Products
    for item in data.get("products", []):
        db.add(models.Product(**item))
        
    # Flush para garantir que IDs existam antes de inserir filhos
    await db.flush() 

    # 3. Sessions (Depende de User)
    # Precisamos converter strings de data de volta para datetime
    for item in data.get("sessions", []):
        if item.get('start_time'): item['start_time'] = datetime.fromisoformat(item['start_time'])
        if item.get('end_time'): item['end_time'] = datetime.fromisoformat(item['end_time'])
        db.add(models.CashierSession(**item))
    
    await db.flush()

    # 4. Sales (Depende de User e Session)
    for item in data.get("sales", []):
        if item.get('timestamp'): item['timestamp'] = datetime.fromisoformat(item['timestamp'])
        # Enum conversion handling if needed, but SQLAlchemy usually handles str to Enum if exact match
        db.add(models.Sale(**item))
        
    await db.flush()

    # 5. Sale Items (Depende de Sale e Product)
    for item in data.get("sale_items", []):
        db.add(models.SaleItem(**item))
        
    # 6. Stock Movements (Depende de Product)
    for item in data.get("stock_movements", []):
        if item.get('timestamp'): item['timestamp'] = datetime.fromisoformat(item['timestamp'])
        db.add(models.StockMovement(**item))

    await db.commit()

    # 3. CORREÇÃO DE SEQUÊNCIAS (RESET ID) - FIX PARA POSTGRESQL
    # Ajustamos o contador de cada tabela para MAX(id) + 1
    tables = [
        "users", 
        "products", 
        "cashier_sessions", 
        "sales", 
        "sale_items", 
        "stock_movements"
    ]

    for table in tables:
        try:
            # Comando SQL para Postgres resetar a sequence
            # setval define o valor atual. nextval será valor + 1
            # COALESCE garante que se a tabela estiver vazia, define como 1
            seq_name = f"{table}_id_seq"
            sql = text(f"SELECT setval('{seq_name}', (SELECT COALESCE(MAX(id), 0) FROM {table}), true);")
            await db.execute(sql)
        except Exception as e:
            print(f"Erro ao resetar sequence da tabela {table}: {e}")
            # Em alguns ambientes o nome da sequence pode ser diferente, mas não abortamos o processo
            continue
            
    await db.commit()
    
    return {"message": "Restauração concluída com sucesso! Faça login novamente."}

@router.delete("/{filename}", dependencies=[Depends(allow_admin_only)])
async def delete_backup_file(filename: str,
    current_user: models.User = Depends(get_current_user)):
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return {"message": "Arquivo excluído"}
    raise HTTPException(404, "Arquivo não encontrado")