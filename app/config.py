from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    NOME_FANTASIA: str
    CNPJ: str
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    URL_FRONTEND: str
    
    # Configurações NFC-e
    NFCE_HABILITADO: bool = False
    NFCE_CERTIFICADO_CAMINHO: str = ""
    NFCE_CERTIFICADO_SENHA: str = ""
    NFCE_CSC: str = ""
    NFCE_ID_CSC: str = ""
    NFCE_AMBIENTE: int = 2  # 1=Produção, 2=Homologação
    NFCE_UF: str = "SP"
    NFCE_SERIE: str = "1"
    NFCE_MUNICIPIO_IBGE: str = "3550308"  # Código IBGE do município (São Paulo padrão)
    
    class Config:
        env_file = ".env"

settings = Settings()