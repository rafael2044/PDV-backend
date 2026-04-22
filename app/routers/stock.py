from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.dependencies import allow_manager, get_current_user

router = APIRouter(prefix="/stock", tags=["Stock"])

# Schema de Resposta (inclui o nome do produto)
class StockMovementResponse(BaseModel):
    id: int
    product_name: str
    quantity_change: float
    movement_type: str
    description: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True

# Rota de Histórico
@router.get("/history", response_model=List[StockMovementResponse], dependencies=[Depends(allow_manager)])
async def get_stock_history(
    movement_type: Optional[str] = None, # entry, sale, loss
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Join para pegar o nome do produto
    query = select(models.StockMovement, models.Product.name).join(models.Product)

    # Filtros
    if movement_type:
        query = query.where(models.StockMovement.movement_type == movement_type)
    
    if start_date:
        query = query.where(models.StockMovement.timestamp >= start_date)
        
    if end_date:
        # Ajuste para pegar até o final do dia
        query = query.where(models.StockMovement.timestamp <= datetime.combine(end_date, datetime.max.time()))

    if product_id:
        query = query.where(models.StockMovement.product_id == product_id)

    # Ordenação: Mais recente primeiro
    query = query.order_by(models.StockMovement.timestamp.desc())

    result = await db.execute(query)
    
    # Montar resposta (Já que o join retorna uma tupla)
    history = []
    for movement, product_name in result:
        history.append({
            "id": movement.id,
            "product_name": product_name,
            "quantity_change": movement.quantity_change,
            "movement_type": movement.movement_type,
            "description": movement.description,
            "timestamp": movement.timestamp
        })
        
    return history