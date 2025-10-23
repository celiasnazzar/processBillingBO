from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OCR_BACKENDS: str = "doctr,ocrmypdf,tesseract"
    OCR_LANGS: str = "spa+eng+ita"
    MAX_RIGHT_DX: int = 900
    class Config:
        env_file = ".env"

settings = Settings()
