from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, time
from app.database import get_db
from app import models
from app.dependencies import allow_manager, get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/dashboard", dependencies=[Depends(allow_manager)])
async def get_dashboard_data(db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    today = datetime.now().date()
    start_of_day = datetime.combine(today, time.min)
    end_of_day = datetime.combine(today, time.max)

    # 1. Total Vendido Hoje (Soma das vendas concluídas)
    sales_query = select(func.sum(models.Sale.total_amount)).where(
        models.Sale.timestamp >= start_of_day,
        models.Sale.timestamp <= end_of_day,
        models.Sale.status == models.SaleStatus.COMPLETED
    )
    sales_result = await db.execute(sales_query)
    total_sales_today = sales_result.scalar() or 0.0

    # 2. Produtos Mais Vendidos (Top 10 Geral)
    # Agrupa itens vendidos, soma quantidades e ordena
    best_seller_query = select(
        models.Product.name,
        func.sum(models.SaleItem.quantity).label("total_qty")
    ).join(models.SaleItem.product).join(models.SaleItem.sale).where(
        models.Sale.status == models.SaleStatus.COMPLETED
    ).group_by(models.Product.id, models.Product.name).order_by(desc("total_qty")).limit(10)
    
    bs_result = await db.execute(best_seller_query)
    top_products = [{"name": row.name, "quantity": row.total_qty} for row in bs_result]

    # O "Best Seller" é o primeiro da lista
    best_seller = top_products[0] if top_products else None

    # 3. Estoque Baixo (Abaixo do Mínimo e Ativos)
    low_stock_query = select(models.Product).where(
        models.Product.stock_quantity < models.Product.min_stock,
        models.Product.is_active == True
    )
    ls_result = await db.execute(low_stock_query)
    low_stock_items = ls_result.scalars().all()

    return {
        "sales_today": total_sales_today,
        "best_seller": best_seller,
        "top_products": top_products, # Para o modal de detalhes
        "low_stock_count": len(low_stock_items),
        "low_stock_items": low_stock_items # Para o modal de detalhes
    }