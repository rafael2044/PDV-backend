from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user
from app.dependencies import allow_manager, allow_admin_only
from typing import List
from app.config import settings

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.get("/", response_model=List[schemas.SaleResponse], dependencies=[Depends(allow_manager), Depends(allow_admin_only)])
async def read_sales(
    session_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)   
):
    # Busca vendas daquela sessão carregando os itens e os produtos dos itens
    query = select(models.Sale)\
        .where(models.Sale.session_id == session_id)\
        .options(
            selectinload(models.Sale.items).selectinload(models.SaleItem.product)
        )\
        .options(
            selectinload(models.Sale.seller)
        )\
        .order_by(models.Sale.timestamp.desc())

    result = await db.execute(query)
    return result.scalars().all()

@router.post("/")
async def create_sale(
    sale_in: schemas.SaleCreate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_terminal_id: str = Header(..., alias="x-terminal-id") # Lê o Header obrigatório

):
    # 1. Verificar se o usuário tem uma sessão de caixa ABERTA
    # Buscamos a última sessão do usuário que ainda não tem 'end_time'
    query_session = select(models.CashierSession).where(
        models.CashierSession.terminal_id == x_terminal_id,
        models.CashierSession.status == "open"
    )
    result_session = await db.execute(query_session)
    cashier_session = result_session.scalars().first()

    if not cashier_session:
        raise HTTPException(
            status_code=400, 
            detail="Você precisa abrir o caixa antes de realizar vendas."
        )

    # Inicia variáveis da venda
    total_amount = 0.0
    db_sale_items = []
    
    # 2. Processar cada item da venda
    for item in sale_in.items:
        # Busca o produto
        result_prod = await db.execute(select(models.Product).where(models.Product.id == item.product_id))
        product = result_prod.scalars().first()

        if not product:
            raise HTTPException(status_code=404, detail=f"Produto ID {item.product_id} não encontrado")

        # Verifica estoque
        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Estoque insuficiente para '{product.name}'. Disponível: {product.stock_quantity}"
            )

        # 3. Baixa de Estoque
        product.stock_quantity -= item.quantity
        
        # 4. Registrar Movimentação de Estoque (Auditoria)
        stock_move = models.StockMovement(
            product_id=product.id,
            quantity_change=-item.quantity, # Negativo pois é saída
            movement_type=models.StockMovementType.SALE,
            description=f"Venda PDV"
        )
        db.add(stock_move)

        # Prepara o Item da Venda
        # Importante: Pegamos o preço ATUAL do produto para salvar no histórico da venda
        subtotal = product.price * item.quantity
        total_amount += subtotal

        sale_item = models.SaleItem(
            product_id=product.id,
            quantity=item.quantity,
            unit_price=product.price,
            subtotal=subtotal
        )
        db_sale_items.append(sale_item)

    # 5. Criar a Venda
    new_sale = models.Sale(
        user_id=current_user.id,
        session_id=cashier_session.id,
        total_amount=total_amount,
        payment_method=sale_in.payment_method,
        status=models.SaleStatus.COMPLETED,
        items=db_sale_items # O SQLAlchemy resolve as FKs aqui
    )

    db.add(new_sale)
    
    try:
        await db.commit()
        query = select(models.Sale).where(models.Sale.id == new_sale.id).options(
            selectinload(models.Sale.items).selectinload(models.SaleItem.product)
        )
        result = await db.execute(query)
        final_sale = result.scalars().first()
        
        cupom_data = {
            "id_venda": final_sale.id,
            "data_hora": final_sale.timestamp.strftime("%d/%m/%Y %H:%M"),
            "nome_fantasia": settings.NOME_FANTASIA,
            "cnpj": settings.CNPJ,
            "itens": [
                {
                    "descricao": item.product.name,
                    "quantidade": item.quantity,
                    "valor_unitario": float(item.unit_price),
                    "valor_total": float(item.subtotal)
                }
                for item in final_sale.items
            ],
            "total_venda": float(final_sale.total_amount),
            "metodo_pagamento": final_sale.payment_method
        }
        
        return cupom_data

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))