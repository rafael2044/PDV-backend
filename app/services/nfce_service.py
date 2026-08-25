import logging
import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app import models
from app.routers.settings import get_nfce_habilitado

logger = logging.getLogger(__name__)

# Mapeamento de métodos de pagamento para códigos SEFAZ
PAYMENT_METHOD_MAP = {
    "dinheiro": "01",    # Dinheiro
    "credito": "03",     # Cartão de Crédito
    "debito": "04",      # Cartão de Débito
    "pix": "17",         # Pagamento Instantâneo (PIX)
}


def _validar_codigo_ibge(codigo: str) -> str:
    """Valida e formata o código IBGE do município."""
    # Remove caracteres não numéricos
    codigo_limpo = ''.join(filter(str.isdigit, codigo))
    
    # Verifica se tem 7 dígitos
    if len(codigo_limpo) != 7:
        raise ValueError(f"Código IBGE inválido: {codigo}. Deve ter exatamente 7 dígitos.")
    
    return codigo_limpo


def _criar_emitente():
    """Cria o objeto Emitente com os dados do .env."""
    from pynfe.entidades.emitente import Emitente
    
    cnpj_limpo = settings.CNPJ.replace(".", "").replace("/", "").replace("-", "")
    
    # Validar código IBGE do município
    municipio_ibge = _validar_codigo_ibge(settings.NFCE_MUNICIPIO_IBGE)
    
    emitente = Emitente(
        razao_social=settings.NOME_FANTASIA,
        nome_fantasia=settings.NOME_FANTASIA,
        cnpj=cnpj_limpo,
        codigo_de_regime_tributario='1',  # Simples Nacional
        inscricao_estadual='',  # Preencher se necessário
        inscricao_municipal='',
        cnae_fiscal='',
        endereco_logradouro='',
        endereco_numero='',
        endereco_bairro='',
        endereco_municipio=municipio_ibge,
        endereco_uf=settings.NFCE_UF,
        endereco_cep='',
        endereco_pais='1058'  # Brasil
    )
    
    return emitente


def _criar_cliente():
    """Cria o objeto Cliente (consumidor final sem identificação)."""
    from pynfe.entidades.cliente import Cliente
    
    cliente = Cliente(
        razao_social='CONSUMIDOR FINAL',
        tipo_documento='CPF',
        email='',
        numero_documento='',
        indicador_ie=9,  # Não contribuinte
        endereco_logradouro='',
        endereco_numero='',
        endereco_complemento='',
        endereco_bairro='',
        endereco_municipio='',
        endereco_uf=settings.NFCE_UF,
        endereco_cep='',
        endereco_pais='1058',  # Brasil
        endereco_telefone=''
    )
    
    return cliente


def _montar_nota_fiscal(sale: models.Sale, emitente, cliente):
    """Monta o objeto NotaFiscal com os dados da venda."""
    from pynfe.entidades.notafiscal import NotaFiscal
    
    # Determinar forma de pagamento
    forma_pagamento = 0  # À vista
    if sale.payment_method in ['credito']:
        forma_pagamento = 1  # A prazo
    
    # Validar código IBGE do município
    municipio_ibge = _validar_codigo_ibge(settings.NFCE_MUNICIPIO_IBGE)
    
    nota_fiscal = NotaFiscal(
        emitente=emitente,
        cliente=cliente,
        uf=settings.NFCE_UF.upper(),
        natureza_operacao='VENDA',
        forma_pagamento=forma_pagamento,
        tipo_pagamento=PAYMENT_METHOD_MAP.get(sale.payment_method, '01'),
        modelo=65,  # NFC-e
        serie=settings.NFCE_SERIE,
        numero_nf=str(sale.id),
        data_emissao=datetime.datetime.now(),
        data_saida_entrada=datetime.datetime.now(),
        tipo_documento=1,  # Saída
        municipio=municipio_ibge,
        tipo_impressao_danfe=4,  # DANFE NFC-e
        forma_emissao='1',  # Normal
        cliente_final=1,  # Consumidor final
        indicador_destino=1,
        indicador_presencial=1,  # Presencial
        finalidade_emissao='1',  # Normal
        processo_emissao='0',  # Aplicativo do contribuinte
        transporte_modalidade_frete=9,  # Sem transporte
        informacoes_adicionais_interesse_fisco='',
        totais_tributos_aproximado=Decimal('0.00')
    )
    
    return nota_fiscal


def _adicionar_itens(nota_fiscal, sale: models.Sale):
    """Adiciona os itens da venda na nota fiscal."""
    for sale_item in sale.items:
        product = sale_item.product
        
        # Determinar quantidade (inteiro para unidades, decimal para peso)
        if product.is_weighted:
            quantidade = Decimal(str(sale_item.quantity))
        else:
            quantidade = Decimal(str(int(sale_item.quantity)))
        
        nota_fiscal.adicionar_produto_servico(
            codigo=str(product.id),
            descricao=product.name,
            ncm=product.ncm or '00000000',
            cfop=product.cfop or '5102',
            unidade_comercial=product.unidade_medida or 'UN',
            ean=product.barcode or 'SEM GTIN',
            ean_tributavel=product.barcode or 'SEM GTIN',
            quantidade_comercial=quantidade,
            valor_unitario_comercial=Decimal(str(sale_item.unit_price)),
            valor_total_bruto=Decimal(str(sale_item.subtotal)),
            unidade_tributavel=product.unidade_medida or 'UN',
            quantidade_tributavel=quantidade,
            valor_unitario_tributavel=Decimal(str(sale_item.unit_price)),
            ind_total=1,
            icms_modalidade='102',  # Simples Nacional - Tributada sem permissão de crédito
            icms_origem=int(product.origem or '0'),
            icms_csosn=product.csosn_icms or '102',
            pis_modalidade='07',  # Outras operações de saída
            cofins_modalidade='07',  # Outras operações de saída
            valor_tributos_aprox=Decimal('0.00')
        )


def _adicionar_responsavel_tecnico(nota_fiscal):
    """Adiciona o responsável técnico na nota fiscal."""
    cnpj_limpo = settings.CNPJ.replace(".", "").replace("/", "").replace("-", "")
    
    nota_fiscal.adicionar_responsavel_tecnico(
        cnpj=cnpj_limpo,
        contato='Suporte',
        email='',
        fone=''
    )


async def processar_nfce(sale_id: int, session: AsyncSession) -> dict:
    """
    Processa a emissão de uma NFC-e para uma venda existente.
    
    Args:
        sale_id: ID da venda
        session: Sessão do banco de dados
        
    Returns:
        dict com status, mensagem e dados da NFC-e
    """
    if not get_nfce_habilitado():
        return {
            "success": False,
            "status": "desabilitado",
            "message": "Emissão de NFC-e está desabilitada nas configurações."
        }
    
    try:
        # Validar configurações antes de prosseguir
        logger.info(f"Iniciando processamento NFC-e para venda {sale_id}")
        logger.info(f"Configurações: UF={settings.NFCE_UF}, Município={settings.NFCE_MUNICIPIO_IBGE}, Ambiente={settings.NFCE_AMBIENTE}")
        
        # Validar código IBGE
        try:
            municipio_ibge = _validar_codigo_ibge(settings.NFCE_MUNICIPIO_IBGE)
            logger.info(f"Código IBGE validado: {municipio_ibge}")
        except ValueError as e:
            logger.error(f"Erro na validação do código IBGE: {e}")
            return {
                "success": False,
                "status": "erro",
                "message": f"Configuração inválida: {str(e)}"
            }
        
        # Carregar venda com itens e produtos
        query = select(models.Sale).where(models.Sale.id == sale_id).options(
            selectinload(models.Sale.items).selectinload(models.SaleItem.product)
        )
        result = await session.execute(query)
        sale = result.scalars().first()
        
        if not sale:
            return {
                "success": False,
                "status": "erro",
                "message": f"Venda ID {sale_id} não encontrada."
            }
        
        logger.info(f"Venda encontrada: {sale.id}, Total: {sale.total_amount}, Itens: {len(sale.items)}")
        
        # Importar PyNFe
        from pynfe.processamento.comunicacao import ComunicacaoSefaz
        from pynfe.processamento.serializacao import SerializacaoXML, SerializacaoQrcode
        from pynfe.processamento.assinatura import AssinaturaA1
        from pynfe.entidades.fonte_dados import _fonte_dados
        from lxml import etree
        
        # Criar emitente, cliente e nota fiscal
        logger.info("Criando emitente...")
        emitente = _criar_emitente()
        
        logger.info("Criando cliente...")
        cliente = _criar_cliente()
        
        logger.info("Montando nota fiscal...")
        nota_fiscal = _montar_nota_fiscal(sale, emitente, cliente)
        
        # Adicionar itens
        logger.info(f"Adicionando {len(sale.items)} itens...")
        _adicionar_itens(nota_fiscal, sale)
        
        # Adicionar responsável técnico
        logger.info("Adicionando responsável técnico...")
        _adicionar_responsavel_tecnico(nota_fiscal)
        
        # Serialização
        logger.info("Serializando XML...")
        homologacao = settings.NFCE_AMBIENTE == 2
        serializador = SerializacaoXML(_fonte_dados, homologacao=homologacao)
        nfce = serializador.exportar()
        
        # Assinatura
        logger.info("Assinando XML...")
        a1 = AssinaturaA1(
            settings.NFCE_CERTIFICADO_CAMINHO,
            settings.NFCE_CERTIFICADO_SENHA
        )
        xml = a1.assinar(nfce)
        
        # Gerar QRCode
        logger.info("Gerando QRCode...")
        token = settings.NFCE_ID_CSC
        csc = settings.NFCE_CSC
        xml_com_qrcode = SerializacaoQrcode().gerar_qrcode(token, csc, xml)
        
        # Envio para SEFAZ
        logger.info("Enviando para SEFAZ...")
        con = ComunicacaoSefaz(
            settings.NFCE_UF,
            settings.NFCE_CERTIFICADO_CAMINHO,
            settings.NFCE_CERTIFICADO_SENHA,
            homologacao
        )
        envio = con.autorizacao(modelo='nfce', nota_fiscal=xml_com_qrcode)
        
        # Processar resultado
        if envio[0] == 0:
            # Sucesso - XML autorizado
            xml_autorizado = etree.tostring(envio[1], encoding="unicode").replace('\n', '').replace('ns0:', '')
            
            # Extrair chave de acesso e protocolo do XML
            # TODO: Extrair valores reais do XML de retorno
            chave_acesso = ''
            protocolo = ''
            
            # Atualizar venda com dados da NFC-e autorizada
            sale.nfce_chave = chave_acesso
            sale.nfce_numero = sale.id
            sale.nfce_protocolo = protocolo
            sale.nfce_status = "autorizada"
            sale.nfce_xml = xml_autorizado
            
            await session.commit()
            
            return {
                "success": True,
                "status": "autorizada",
                "message": "NFC-e autorizada com sucesso!",
                "chave": chave_acesso,
                "protocolo": protocolo,
                "numero": sale.id
            }
        else:
            # Erro - Rejeição
            resposta_erro = envio[1].text if envio[1] is not None else "Erro desconhecido"
            
            # Tentar extrair código e motivo do erro
            codigo_erro = ""
            motivo_erro = resposta_erro
            
            try:
                if envio[1] is not None:
                    xml_erro = etree.tostring(envio[1], encoding="unicode")
                    # Parsear XML de erro para extrair informações
                    # TODO: Extrair cStat e xMotivo do XML de retorno
            except Exception:
                pass
            
            # Atualizar venda como rejeitada
            sale.nfce_status = "rejeitada"
            sale.nfce_protocolo = motivo_erro[:255] if motivo_erro else None
            
            await session.commit()
            
            return {
                "success": False,
                "status": "rejeitada",
                "message": f"NFC-e rejeitada: {motivo_erro}",
                "codigo_erro": codigo_erro
            }
    
    except FileNotFoundError as e:
        logger.error(f"Certificado digital não encontrado: {e}")
        return {
            "success": False,
            "status": "erro",
            "message": "Certificado digital não encontrado. Verifique o caminho configurado."
        }
    
    except Exception as e:
        logger.error(f"Erro ao processar NFC-e: {e}")
        return {
            "success": False,
            "status": "erro",
            "message": f"Erro ao processar NFC-e: {str(e)}"
        }


async def reprocessar_nfce(sale_id: int, session: AsyncSession) -> dict:
    """
    Reprocessa uma NFC-e que foi rejeitada ou está pendente.
    
    Args:
        sale_id: ID da venda
        session: Sessão do banco de dados
        
    Returns:
        dict com status e mensagem
    """
    query = select(models.Sale).where(models.Sale.id == sale_id)
    result = await session.execute(query)
    sale = result.scalars().first()
    
    if not sale:
        return {
            "success": False,
            "status": "erro",
            "message": f"Venda ID {sale_id} não encontrada."
        }
    
    if sale.nfce_status == "autorizada":
        return {
            "success": False,
            "status": "ja_autorizada",
            "message": "Esta venda já possui uma NFC-e autorizada."
        }
    
    # Limpar dados anteriores para reprocessamento
    sale.nfce_chave = None
    sale.nfce_numero = None
    sale.nfce_protocolo = None
    sale.nfce_status = "pendente"
    sale.nfce_xml = None
    
    await session.commit()
    
    # Processar novamente
    return await processar_nfce(sale_id, session)


async def verificar_status_nfce(sale_id: int, session: AsyncSession) -> dict:
    """
    Consulta o status da NFC-e de uma venda.
    
    Args:
        sale_id: ID da venda
        session: Sessão do banco de dados
        
    Returns:
        dict com dados da NFC-e
    """
    query = select(models.Sale).where(models.Sale.id == sale_id)
    result = await session.execute(query)
    sale = result.scalars().first()
    
    if not sale:
        return {
            "success": False,
            "message": f"Venda ID {sale_id} não encontrada."
        }
    
    return {
        "success": True,
        "nfce_status": sale.nfce_status,
        "nfce_chave": sale.nfce_chave,
        "nfce_numero": sale.nfce_numero,
        "nfce_protocolo": sale.nfce_protocolo,
        "nfce_xml": sale.nfce_xml
    }


async def verificar_status_servico() -> dict:
    """
    Verifica o status do serviço da SEFAZ.
    
    Returns:
        dict com status do serviço
    """
    try:
        from pynfe.processamento.comunicacao import ComunicacaoSefaz
        
        logger.info(f"Verificando status do serviço SEFAZ para UF={settings.NFCE_UF}")
        
        # Validar código IBGE antes de prosseguir
        try:
            municipio_ibge = _validar_codigo_ibge(settings.NFCE_MUNICIPIO_IBGE)
            logger.info(f"Código IBGE validado: {municipio_ibge}")
        except ValueError as e:
            logger.error(f"Erro na validação do código IBGE: {e}")
            return {
                "success": False,
                "message": f"Configuração inválida: {str(e)}"
            }
        
        homologacao = settings.NFCE_AMBIENTE == 2
        
        con = ComunicacaoSefaz(
            settings.NFCE_UF,
            settings.NFCE_CERTIFICADO_CAMINHO,
            settings.NFCE_CERTIFICADO_SENHA,
            homologacao
        )
        
        resultado = con.status_servico('nfe')
        
        logger.info(f"Resultado status serviço: {resultado.text}")
        
        return {
            "success": True,
            "status": resultado.text,
            "ambiente": "homologacao" if homologacao else "producao"
        }
    except Exception as e:
        logger.error(f"Erro ao verificar status do serviço: {e}")
        return {
            "success": False,
            "message": f"Erro ao verificar status do serviço: {str(e)}"
        }


def gerar_danfe_nfce(sale_id: int, xml_content: str) -> Optional[str]:
    """
    Gera o DANFE (Documento Auxiliar da NFC-e) em formato HTML.
    
    Args:
        sale_id: ID da venda
        xml_content: XML da NFC-e autorizada
        
    Returns:
        String com o conteúdo HTML do DANFE ou None em caso de erro
    """
    try:
        # TODO: Implementar geração de DANFE NFC-e
        # O PyNFe pode não ter geração de DANFE nativa
        # Pode ser necessário usar uma biblioteca adicional como danfe ou nfelib
        
        html_content = f"""
        <html>
        <head>
            <title>DANFE NFC-e - Venda #{sale_id}</title>
            <style>
                body {{ font-family: monospace; font-size: 12px; width: 80mm; margin: 0 auto; }}
                .center {{ text-align: center; }}
                .bold {{ font-weight: bold; }}
                .separator {{ border-top: 1px dashed #000; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="center bold">
                <h2>CUPOM FISCAL ELETRÔNICO - NFC-e</h2>
                <p>Venda #{sale_id}</p>
            </div>
            <div class="separator"></div>
            <p>XML Autorizado disponível para impressão.</p>
            <p>Consulte o documento completo no portal da SEFAZ.</p>
        </body>
        </html>
        """
        
        return html_content
    
    except Exception as e:
        logger.error(f"Erro ao gerar DANFE: {e}")
        return None
