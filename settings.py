from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OCR_BACKENDS: str = "doctr,ocrmypdf,tesseract"
    OCR_LANGS: str = "spa+eng+ita"
    MAX_RIGHT_DX: int = 900

    # --- Base de datos cobro_proforma (misma configuración que cobro-gateway) ---
    DB_HOST: str = "192.168.1.239"
    DB_PORT: int = 3306
    DB_NAME: str = "cobro_proforma"
    DB_USER: str = "cobro_n8n"
    DB_PASSWORD: str = ""
    DB_CONNECT_TIMEOUT_S: int = 10
    # SSL con certificados de cliente (rutas a los ficheros).
    # Alternativa sin certificados: DB_SSL=required (cifra pero no valida el servidor).
    DB_SSL_CA: str = ""
    DB_SSL_CERT: str = ""
    DB_SSL_KEY: str = ""
    DB_SSL: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
