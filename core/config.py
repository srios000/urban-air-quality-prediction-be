import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from pathlib import Path
from functools import lru_cache
from typing import List

PROJECT_ROOT_CONFIG_PERSPECTIVE = Path(__file__).parent.parent.resolve()
ENV_PATH = PROJECT_ROOT_CONFIG_PERSPECTIVE / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
    # print(f"Loaded .env file from {ENV_PATH}")
else:
    print(f"Warning: .env file not found at {ENV_PATH}. Using environment variables or defaults.")

class Settings(BaseSettings):
    """
    Application settings.
    Values are loaded from environment variables.
    If an environment variable is not set, Pydantic will use the default value if provided.
    """
    APP_NAME: str = "Urban Air Quality Prediction API"
    APP_VERSION: str = "1.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    # MongoDB Settings
    MONGO_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "air_quality_db"

    # Google API Keys
    GOOGLE_API_KEY: str | None = None 
    GOOGLE_MAPS_API_KEY: str | None = None

    # ML Model Path
    MODEL_STORE_PATH: str = "infrastructure/ml/models_store" 

    # Label Encoder Filenames
    LE_COUNTRY_FILENAME: str = "le_country.pkl"
    LE_LOC_FILENAME: str = "le_loc.pkl"
    LE_CAT_FILENAME: str = "le_cat.pkl"
    MODEL_FILENAME: str = "xgboost_final_model.json"

    # CORS settings
    CORS_ALLOW_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Logging level
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = str(ENV_PATH) 
        env_file_encoding = 'utf-8'
        extra = 'ignore'

@lru_cache()
def get_settings() -> Settings:
    print("get_settings() called. Creating/returning Settings instance.")
    s = Settings()
    return s

def ensure_env_file():
    """Ensures .env file exists at the project root."""
    env_path_to_check = PROJECT_ROOT_CONFIG_PERSPECTIVE / ".env"
    if not env_path_to_check.exists():
        print(f".env file not found at {env_path_to_check}, creating a default one.")
        default_env_content = (
            "MONGO_URI=mongodb://localhost:27017\n"
            "DB_NAME=air_quality_db\n"
            "# Ensure these are uncommented and set in your actual .env file\n"
            "GOOGLE_API_KEY=\n"
            "GOOGLE_MAPS_API_KEY=\n" 
            "APP_HOST=0.0.0.0\n"
            "APP_PORT=8000\n"
            "LOG_LEVEL=INFO\n"
            "MODEL_STORE_PATH=infrastructure/ml/models_store\n"
        )
        try:
            with open(env_path_to_check, "w") as f:
                f.write(default_env_content)
            print(f"Default .env file created at {env_path_to_check}. Please configure your API keys.")
        except IOError as e:
            print(f"Error creating default .env file: {e}")

