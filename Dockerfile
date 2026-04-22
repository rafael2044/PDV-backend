FROM python:3.11-slim

WORKDIR /app

# Evita que o Python grave arquivos .pyc e garante que os logs apareçam no console do Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala as dependências (assumindo que você usa requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

EXPOSE 8000

# Inicia o servidor FastAPI em modo de desenvolvimento
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
