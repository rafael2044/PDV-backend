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
from app.routers.settings import get_nfce_habilitado
from app.services.nfce_service import processar_nfce, reprocessar_nfce, verificar_status_nfce, gerar_danfe_nfce, verificar_status_servico

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
    x_terminal_id: str = Header(..., alias="x-terminal-id")

):
    # 1. Verificar se o usuário tem uma sessão de caixa ABERTA
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
        nfce_status="pendente" if get_nfce_habilitado() else "desabilitado",
        items=db_sale_items
    )

    db.add(new_sale)
    
    try:
        # 6. FLUSH para obter o ID da venda antes de enviar à SEFAZ
        await db.flush()
        
        nfce_result = None
        
        # 7. Processar NFC-e SE estiver habilitado
        if get_nfce_habilitado():
            nfce_result = await processar_nfce(new_sale.id, db)
            
            # REGRA CRÍTICA: Falha na NFC-e NÃO faz rollback da venda
            if not nfce_result["success"]:
                # Venda já foi salva com status rejeitada/pendente no serviço
                pass
        
        # 8. Commit final (venda + NFC-e)
        await db.commit()
        
        # 9. Recarregar venda com todos os dados
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
            "metodo_pagamento": final_sale.payment_method,
            "nfce_status": final_sale.nfce_status,
            "nfce_chave": final_sale.nfce_chave,
            "nfce_protocolo": final_sale.nfce_protocolo
        }
        
        # Adicionar resultado da NFC-e se foi processada
        if nfce_result:
            cupom_data["nfce_resultado"] = nfce_result
        
        return cupom_data

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sale_id}/nfce/status")
async def get_nfce_status(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Consulta o status da NFC-e de uma venda."""
    result = await verificar_status_nfce(sale_id, db)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result


@router.post("/{sale_id}/nfce/reprocessar")
async def reprocessar_nfce_endpoint(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Reprocessa uma NFC-e rejeitada ou pendente."""
    if not get_nfce_habilitado():
        raise HTTPException(
            status_code=400,
            detail="Emissão de NFC-e está desabilitada nas configurações."
        )
    
    result = await reprocessar_nfce(sale_id, db)
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
    
    return result


@router.get("/{sale_id}/nfce/danfe")
async def get_nfce_danfe(
    sale_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Gera o DANFE (cupom fiscal) de uma NFC-e autorizada."""
    query = select(models.Sale).where(models.Sale.id == sale_id)
    result = await db.execute(query)
    sale = result.scalars().first()
    
    if not sale:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
    
    if sale.nfce_status != "autorizada":
        raise HTTPException(
            status_code=400,
            detail=f"Venda não possui NFC-e autorizada. Status atual: {sale.nfce_status}"
        )
    
    if not sale.nfce_xml:
        raise HTTPException(
            status_code=400,
            detail="XML da NFC-e não encontrado para esta venda."
        )
    
    html_danfe = gerar_danfe_nfce(sale_id, sale.nfce_xml)
    
    if not html_danfe:
        raise HTTPException(
            status_code=500,
            detail="Erro ao gerar DANFE."
        )
    
    return {
        "success": True,
        "html": html_danfe,
        "sale_id": sale_id,
        "nfce_chave": sale.nfce_chave
    }


@router.get("/nfce/configuracao")
async def get_nfce_config(
    current_user: models.User = Depends(get_current_user)
):
    """Retorna a configuração atual do NFC-e."""
    return {
        "nfce_habilitado": get_nfce_habilitado(),
        "nfce_ambiente": settings.NFCE_AMBIENTE,
        "nfce_uf": settings.NFCE_UF,
        "nfce_serie": settings.NFCE_SERIE,
        "nfce_certificado_configurado": bool(settings.NFCE_CERTIFICADO_CAMINHO),
        "nfce_csc_configurado": bool(settings.NFCE_CSC)
    }


@router.get("/nfce/status-servico")
async def get_nfce_servico_status(
    current_user: models.User = Depends(get_current_user)
):
    """Verifica o status do serviço da SEFAZ."""
    if not get_nfce_habilitado():
        return {
            "success": False,
            "message": "NFC-e está desabilitado nas configurações."
        }
    
    result = await verificar_status_servico()
    return result


@router.get("/nfce/testar-configuracao")
async def testar_configuracao_nfce(
    current_user: models.User = Depends(get_current_user)
):
    """Testa a configuração atual do NFC-e sem enviar para SEFAZ."""
    from app.services.nfce_service import _validar_codigo_ibge
    
    erros = []
    
    # Testar código IBGE
    try:
        municipio_ibge = _validar_codigo_ibge(settings.NFCE_MUNICIPIO_IBGE)
    except ValueError as e:
        erros.append(f"Código IBGE: {str(e)}")
    
    # Testar certificado
    import os
    if not settings.NFCE_CERTIFICADO_CAMINHO:
        erros.append("Certificado digital não configurado")
    elif not os.path.exists(settings.NFCE_CERTIFICADO_CAMINHO):
        erros.append(f"Certificado digital não encontrado: {settings.NFCE_CERTIFICADO_CAMINHO}")
    
    # Testar CSC
    if not settings.NFCE_CSC:
        erros.append("CSC não configurado")
    
    if not settings.NFCE_ID_CSC:
        erros.append("ID CSC não configurado")
    
    return {
        "success": len(erros) == 0,
        "erros": erros,
        "configuracao": {
            "uf": settings.NFCE_UF,
            "municipio_ibge": settings.NFCE_MUNICIPIO_IBGE,
            "ambiente": "homologacao" if settings.NFCE_AMBIENTE == 2 else "producao",
            "serie": settings.NFCE_SERIE,
            "certificado_configurado": bool(settings.NFCE_CERTIFICADO_CAMINHO),
            "csc_configurado": bool(settings.NFCE_CSC)
        }
    }