import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: str = os.getenv("ENV", "unit-test")
    jwt_algorithm: str
    jwt_public_key: str  # contiene direttamente la chiave, non un path
    mongo_uri: str
    mongo_db_name: str
    rabbitmq_username: str
    rabbitmq_password: str
    rabbitmq_url: str

    class Config:
        env_file = None  # nessun file .env, solo ENV

settings = Settings()