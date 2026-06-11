from pydantic_settings import BaseSettings
from datetime import time


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "智慧零售损耗预警系统"
    
    DATABASE_URL: str = "sqlite:///./loss_warning.db"
    
    SECRET_KEY: str = "loss-warning-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    DEFAULT_LOSS_RATE_THRESHOLD: float = 3.0
    DEFAULT_EXPIRY_DAYS: int = 7
    DEFAULT_SHORTAGE_RATE_THRESHOLD: float = 2.0
    
    SCHEDULER_HOUR: int = 2
    SCHEDULER_MINUTE: int = 0
    
    class Config:
        case_sensitive = True


settings = Settings()
