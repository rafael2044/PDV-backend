# ﻿🛒 Sistema PDV - Backend API

API robusta e assíncrona para sistema de Ponto de Venda, desenvolvida com Python, FastAPI, SQLAlchemy (Async) e PostgreSQL.

# 📋 Pré-requisitos

- **Python 3.10+** instalado.

- **PostgreSQL** instalado e rodando.

- Um banco de dados criado (ex: pdv_db).

# 🚀 Instalação e Configuração

#### 1. Preparar o Ambiente

Entre na pasta do backend e crie um ambiente virtual para isolar as dependências:

    cd backend

    # Criar ambiente virtual
    python -m venv venv

    # Ativar ambiente (Windows)
    venv\Scripts\activate

    # Ativar ambiente (Linux/Mac)
    source venv/bin/activate


#### 2. Instalar Dependências

Com o ambiente ativo, instale os pacotes necessários:

    pip install -r requirements.txt


#### 3. Configurar Variáveis de Ambiente

Crie uma cópia do arquivo de exemplo:

    cp .env.example .env
    # Windows: copy .env.example .env


Edite o arquivo `.env` e configure as variaveis de ambiente:

    # Formato: postgresql+asyncpg://usuario:senha@host:porta/nome_do_banco
    # Exemplo local:
    DATABASE_URL=postgresql+asyncpg://postgres:admin@localhost:5432/pdv_db
    
    # ------------------------------------------------------------------------
    # SEGURANÇA E AUTENTICAÇÃO
    # ------------------------------------------------------------------------
    # Chave secreta para assinar os tokens JWT.
    # Em produção, gere uma chave forte (ex: 'openssl rand -hex 32')
    SECRET_KEY=uma_chave_secreta_super_segura_e_aleatoria_aqui
    
    # Algoritmo de criptografia do token (Padrão: HS256)
    ALGORITHM=HS256
    
    # Tempo de vida do token de acesso em minutos (Ex: 720 = 12 horas / turno de trabalho)
    ACCESS_TOKEN_EXPIRE_MINUTES=720

    # URL do frontend
    URL_FRONTEND=http://localhost:3000


# 💾 Banco de Dados

- Inicialização Automática

- Na primeira vez que você rodar o sistema, ele irá:

- Criar todas as tabelas automaticamente.

- Criar um usuário Admin padrão se o banco estiver vazio.

# ⚡ Executando o Servidor

#### Modo de Desenvolvimento

Para iniciar a API com hot-reload (recarrega ao salvar arquivos):

    uvicorn app.main:app --reload


#### Modo de Produção

Para rodar em um servidor real, acessível na rede:

    uvicorn app.main:app --host 0.0.0.0 --port 8000


A API estará rodando em: `http://localhost:8000` (ou no IP do servidor).

# 📚 Documentação da API (Swagger UI)

O FastAPI gera documentação interativa automaticamente. Com o servidor rodando, acesse:

👉 http://localhost:8000/docs

Lá você pode testar todas as rotas, autenticar (botão "Authorize") e ver os esquemas de dados.

# 🔐 Credenciais Padrão

Se o sistema criou o usuário automaticamente na inicialização:

**Usuário:** `admin`

**Senha**: `admin123`

# 🛠️ Estrutura do Projeto

`app/main.py`: Ponto de entrada da aplicação.

`app/models.py`: Tabelas do banco de dados (ORM).

`app/schemas.py`: Validação de dados (Pydantic).

`app/routers/`: Endpoints da API divididos por módulo (vendas, caixa, produtos, etc).

`app/database.py`: Configuração da conexão assíncrona.
