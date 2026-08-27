import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NOME_FANTASIA: str
    CNPJ: str
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    URL_FRONTEND: str

    class Config:
        env_file = os.environ.get("PDV_ENV_FILE", ".env")

settings = Settings()