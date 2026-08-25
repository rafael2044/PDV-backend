# Configuração do Sistema PDV com NFC-e

## Instalação das Dependências

### Backend (Python)

```bash
cd PDV-backend
pip install -r requirements.txt
```

### Frontend (Node.js)

```bash
cd PDV-frontend
npm install
```

## Configuração do Banco de Dados

Execute a migração para adicionar as novas colunas:

```bash
cd PDV-backend
alembic upgrade head
```

## Configuração do NFC-e

### 1. Certificado Digital

- Obtenha um certificado digital e-CNPJ (A1 ou A3) válido
- Converta para o formato `.pfx` ou `.p12` se necessário
- Coloque o arquivo em um diretório seguro no servidor

### 2. CSC (Código de Segurança do Contribuinte)

- Solicite o CSC junto à SEFAZ do seu estado
- Para homologação, use o CSC de homologação fornecido pela SEFAZ
- Para produção, use o CSC de produção

### 3. Configuração do .env

Copie o arquivo `.env.example` para `.env` e configure:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:

```env
# Dados da Empresa (obrigatório)
NOME_FANTASIA=Sua Empresa LTDA
CNPJ=00.000.000/0001-00

# Banco de Dados
DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/pdv_db

# NFC-e
NFCE_HABILITADO=true
NFCE_AMBIENTE=2  # 2=Homologação, 1=Produção
NFCE_UF=SP  # UF do emitente
NFCE_SERIE=1
NFCE_MUNICIPIO_IBGE=3550308  # Código IBGE do município (São Paulo)
NFCE_CERTIFICADO_CAMINHO=/caminho/para/certificado.pfx
NFCE_CERTIFICADO_SENHA=senha_do_certificado
NFCE_CSC=seu_csc_aqui
NFCE_ID_CSC=000001
```

### 4. Códigos IBGE dos Municípios

O código IBGE do município é **obrigatório** para emissão de NFC-e. 

**Como encontrar o código correto:**
1. Acesse: https://www.ibge.gov.br/explica/codigos-dos-municipios.php
2. Busque pelo nome do seu município
3. O código tem 7 dígitos (ex: 3550308 = São Paulo)

**Exemplos de códigos:**

| Município | Código IBGE |
|-----------|-------------|
| São Paulo | 3550308 |
| Rio de Janeiro | 3304557 |
| Belo Horizonte | 3106200 |
| Curitiba | 4106902 |
| Porto Alegre | 4314902 |
| Salvador | 2927408 |
| Brasília | 5300108 |
| Fortaleza | 2304400 |
| Recife | 2611606 |
| Manaus | 1302603 |
| São Luís | 2111300 |

**Importante:** 
- O código IBGE no `.env` deve ter exatamente 7 dígitos, sem pontos ou traços.
- As configurações de NFC-e (habilitado/desabilitado) são aplicadas **em tempo real**, sem necessidade de reiniciar o servidor.
- Outras configurações (certificado, CSC, UF) requerem reinicialização do servidor.

### 5. Interface de Configuração

Acesse as configurações do sistema de duas formas:

1. **No PDV**: Clique no botão "Configurações" (apenas para administradores)
2. **Direto**: Acesse `http://localhost:3000/settings`

Na página de configurações você pode:
- Ativar/desativar a emissão de NFC-e
- Configurar ambiente (homologação/produção)
- Configurar UF e município
- Configurar certificado digital
- Configurar CSC
- Testar a configuração
- Testar conexão com a SEFAZ

### 4. Testando em Homologação

1. Altere `NFCE_AMBIENTE=2` no `.env`
2. Use o CSC de homologação
3. Realize uma venda de teste
4. Verifique o status no relatório de vendas

### 5. Indo para Produção

1. Altere `NFCE_AMBIENTE=1` no `.env`
2. Use o CSC de produção
3. Reinicie o servidor backend

## Estrutura de Configuração por Estado

Cada estado brasileiro tem configurações específicas para NFC-e:

| UF | Código | Ambiente Homologação |
|----|--------|---------------------|
| SP | 35     | https://homologacao.nfce.fazenda.sp.gov.br |
| RJ | 33     | https://www.nfe.fazenda.rj.gov.br |
| MG | 31     | https://hnfe.fazenda.mg.gov.br |
| RS | 43     | https://nfce-homologacao.sefazrs.rs.gov.br |
| BA | 29     | https://hnfe.sefaz.ba.gov.br |
| PR | 41     | https://homologacao.nfce.sefa.pr.gov.br |
| SC | 42     | https://homologacao.nfce.sef.sc.gov.br |
| GO | 52     | https://homologacao.sefaz.go.gov.br |
| DF | 53     | https://dec.fazenda.df.gov.br |
| CE | 23     | https://nfceh.sefaz.ce.gov.br |

## Solução de Problemas

### Erro: "module 'pynfe' has no attribute 'nfce'"
- O PyNFe não possui módulo `nfce` diretamente
- A estrutura correta é:
  ```python
  from pynfe.processamento.comunicacao import ComunicacaoSefaz
  from pynfe.processamento.serializacao import Serializacao
  from pynfe.processamento.assinatura import Assinatura
  from pynfe.entidades import Nota, Emitente, Produto
  ```

### Erro: "Certificado digital não encontrado"
- Verifique se o caminho do certificado está correto no `.env`
- Verifique se o arquivo tem permissão de leitura
- O certificado deve ser um arquivo `.pfx` ou `.p12`

### Erro: "CSC inválido"
- Verifique se o CSC está correto para o ambiente (homologação/produção)
- Solicite um novo CSC na SEFAZ se necessário

### Erro: "Rejeição: Duplicidade de NFC-e"
- O número da venda já foi usado em outra NFC-e
- Verifique se não há vendas duplicadas

### NFC-e fica com status "pendente"
- Verifique a conexão com a internet
- Verifique se a SEFAZ do seu estado está disponível
- Use o botão "Reenviar NFC-e" para tentar novamente

### Erro: "Falha na comunicação com a SEFAZ"
- Verifique se a URL da SEFAZ está acessível
- Verifique se o certificado digital não está expirado
- Teste o status do serviço: `GET /sales/nfce/status-servico`

## Comandos Úteis

```bash
# Verificar status do servidor
curl http://localhost:8000/health

# Verificar configuração do NFC-e
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/settings/

# Testar configuração do NFC-e (sem enviar para SEFAZ)
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/sales/nfce/testar-configuracao

# Verificar status do serviço da SEFAZ
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/sales/nfce/status-servico

# Alternar NFC-e
curl -X POST -H "Authorization: Bearer TOKEN" http://localhost:8000/settings/nfce/toggle

# Verificar NFC-e de uma venda específica
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/sales/123/nfce/status

# Reprocessar NFC-e
curl -X POST -H "Authorization: Bearer TOKEN" http://localhost:8000/sales/123/nfce/reprocessar
```

## Exemplo de Uso do PyNFe

```python
from pynfe.processamento.comunicacao import ComunicacaoSefaz
from pynfe.processamento.serializacao import SerializacaoXML, SerializacaoQrcode
from pynfe.processamento.assinatura import AssinaturaA1
from pynfe.entidades.emitente import Emitente
from pynfe.entidades.cliente import Cliente
from pynfe.entidades.notafiscal import NotaFiscal
from pynfe.entidades.fonte_dados import _fonte_dados
from pynfe.utils.flags import CODIGO_BRASIL
from decimal import Decimal
import datetime

# Configurações
certificado = "/caminho/para/certificado.pfx"
senha = "senha_do_certificado"
uf = "SP"
homologacao = True

# Emitente
emitente = Emitente(
    razao_social='NOME DA EMPRESA',
    nome_fantasia='FANTASIA',
    cnpj='99999999000199',
    codigo_de_regime_tributario='1',  # Simples Nacional
    inscricao_estadual='9999999999',
    inscricao_municipal='',
    cnae_fiscal='9999999',
    endereco_logradouro='Rua Exemplo',
    endereco_numero='123',
    endereco_bairro='Centro',
    endereco_municipio='São Paulo',
    endereco_uf='SP',
    endereco_cep='01001000',
    endereco_pais=CODIGO_BRASIL
)

# Cliente (Consumidor Final)
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
    endereco_uf='SP',
    endereco_cep='',
    endereco_pais=CODIGO_BRASIL,
    endereco_telefone=''
)

# Nota Fiscal
nota_fiscal = NotaFiscal(
    emitente=emitente,
    cliente=cliente,
    uf='SP',
    natureza_operacao='VENDA',
    forma_pagamento=0,  # À vista
    tipo_pagamento='01',  # Dinheiro
    modelo=65,  # NFC-e
    serie='1',
    numero_nf='123',
    data_emissao=datetime.datetime.now(),
    data_saida_entrada=datetime.datetime.now(),
    tipo_documento=1,  # Saída
    municipio='3550308',  # São Paulo
    tipo_impressao_danfe=4,  # DANFE NFC-e
    forma_emissao='1',
    cliente_final=1,
    indicador_destino=1,
    indicador_presencial=1,
    finalidade_emissao='1',
    processo_emissao='0',
    transporte_modalidade_frete=9,
    informacoes_adicionais_interesse_fisco='',
    totais_tributos_aproximado=Decimal('0.00')
)

# Adicionar Produto
nota_fiscal.adicionar_produto_servico(
    codigo='001',
    descricao='PRODUTO TESTE',
    ncm='99999999',
    cfop='5102',
    unidade_comercial='UN',
    ean='SEM GTIN',
    ean_tributavel='SEM GTIN',
    quantidade_comercial=Decimal('1'),
    valor_unitario_comercial=Decimal('10.00'),
    valor_total_bruto=Decimal('10.00'),
    unidade_tributavel='UN',
    quantidade_tributavel=Decimal('1'),
    valor_unitario_tributavel=Decimal('10.00'),
    ind_total=1,
    icms_modalidade='102',
    icms_origem=0,
    icms_csosn='102',
    pis_modalidade='07',
    cofins_modalidade='07',
    valor_tributos_aprox=Decimal('0.00')
)

# Responsável Técnico
nota_fiscal.adicionar_responsavel_tecnico(
    cnpj='99999999000199',
    contato='Suporte',
    email='suporte@empresa.com',
    fone='11999999999'
)

# Serialização
serializador = SerializacaoXML(_fonte_dados, homologacao=homologacao)
nfce = serializador.exportar()

# Assinatura
a1 = AssinaturaA1(certificado, senha)
xml = a1.assinar(nfce)

# QRCode
token = '000001'
csc = 'N4EOUTEDXCOVCGNTWLFD4OJLHBWCWJHCXC0C'
xml_com_qrcode = SerializacaoQrcode().gerar_qrcode(token, csc, xml)

# Envio
con = ComunicacaoSefaz(uf, certificado, senha, homologacao)
envio = con.autorizacao(modelo='nfce', nota_fiscal=xml_com_qrcode)

# Resultado
from lxml import etree
if envio[0] == 0:
    print('Sucesso!')
    print(etree.tostring(envio[1], encoding="unicode"))
else:
    print('Erro:')
    print(envio[1].text)
```
