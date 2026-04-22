from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.database import get_db
from app import models, schemas
from app.dependencies import get_current_user, allow_admin_only, allow_manager

router = APIRouter(prefix="/products", tags=["Products"])

# Listar Produtos (Para o Frontend carregar a lista de seleção)
@router.get("/", response_model=List[schemas.ProductResponse])
async def read_products(
    skip: int = 0, 
    limit: int = 100, 
    active_only: bool = False, # <--- Novo Parâmetro
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = select(models.Product)
    
    # Se o front pedir active_only=true, filtramos
    if active_only:
        query = query.where(models.Product.is_active == True)
        
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{product_id}", response_model=schemas.ProductResponse)
async def read_product(product_id: int, db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product

# Criar Produto
@router.post("/", response_model=schemas.ProductResponse,
    dependencies=[Depends(allow_admin_only)])
async def create_product(
    product: schemas.ProductCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Verifica duplicidade de código de barras
    if product.barcode:
        existing = await db.execute(select(models.Product).where(models.Product.barcode == product.barcode))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Código de barras já cadastrado")

    new_product = models.Product(**product.model_dump())
    db.add(new_product)
    
    # Se já nasceu com estoque, cria o log de entrada inicial
    if product.stock_quantity > 0:
        # Nota: O produto precisa ser commitado primeiro para ter ID, ou adicionamos junto na sessão
        # Faremos o commit final no bloco try/except global se fosse complexo, aqui simplificado:
        pass 
        # (Para simplificar, assumimos que o estoque inicial não gera log de 'compra', 
        # ou faríamos um StockMovement aqui também. Vamos focar na rota de Adicionar Estoque abaixo)

    await db.commit()
    await db.refresh(new_product)
    
    # Se houve estoque inicial, registramos a auditoria agora que temos o ID
    if product.stock_quantity > 0:
        movement = models.StockMovement(
            product_id=new_product.id,
            quantity_change=product.stock_quantity,
            movement_type=models.StockMovementType.ENTRY,
            description="Estoque Inicial"
        )
        db.add(movement)
        await db.commit()

    return new_product

# Adicionar Estoque (Reposição)
@router.post("/{product_id}/stock", status_code=200)
async def add_stock(
    product_id: int, 
    quantity: float, 
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantidade deve ser positiva")

    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # 1. Atualiza quantidade atual
    product.stock_quantity += quantity
    
    # 2. Registra auditoria
    movement = models.StockMovement(
        product_id=product.id,
        quantity_change=quantity,
        movement_type=models.StockMovementType.ENTRY,
        description="Reposição de Estoque"
    )
    db.add(movement)
    
    await db.commit()
    return {"message": "Estoque atualizado", "new_quantity": product.stock_quantity}

@router.put("/{product_id}", response_model=schemas.ProductResponse,
    dependencies=[Depends(allow_manager), Depends(allow_admin_only)])
async def update_product(
    product_id: int,
    product_update: schemas.ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Busca o produto
    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Verifica duplicidade de código de barras (se foi alterado)
    if product_update.barcode and product_update.barcode != db_product.barcode:
        existing = await db.execute(select(models.Product).where(models.Product.barcode == product_update.barcode))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Novo código de barras já está em uso por outro produto")

    # Atualiza os campos
    db_product.name = product_update.name
    db_product.price = product_update.price
    db_product.cost_price = product_update.cost_price
    db_product.barcode = product_update.barcode
    db_product.category = product_update.category
    db_product.min_stock = product_update.min_stock

    if product_update.is_active is not None:
        db_product.is_active = product_update.is_active

    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.delete("/{product_id}", dependencies=[Depends(allow_manager)])
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)):
    # 1. Busca o produto
    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    product = result.scalars().first()

    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # 2. VERIFICAÇÃO DE SEGURANÇA: O produto já foi vendido?
    # Se tiver vendas, não podemos apagar, pois sumiria dos relatórios financeiros.
    # Solução ideal seria "Arquivar/Desativar", mas para exclusão física, bloqueamos.
    stmt_sales = select(models.SaleItem).where(models.SaleItem.product_id == product_id)
    result_sales = await db.execute(stmt_sales)
    
    if result_sales.scalars().first():
        raise HTTPException(
            status_code=400, 
            detail="Não é possível excluir: Este produto já possui vendas registradas."
        )

    try:
        # 3. LIMPEZA: Se não tem vendas, podemos apagar o histórico de estoque
        # Isso resolve o erro de Foreign Key do cadastro inicial
        await db.execute(delete(models.StockMovement).where(models.StockMovement.product_id == product_id))

        # 4. Agora sim, deleta o produto
        await db.delete(product)
        await db.commit()
        return {"message": "Produto excluído com sucesso"}
        
    except Exception as e:
        await db.rollback()
        # Logar o erro real no console para debug
        print(f"Erro ao deletar: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao excluir produto.")