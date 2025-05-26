import argparse
import uvicorn
from pathlib import Path
import sys

project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path: 
    sys.path.insert(0, str(project_root))

from infrastructure.logging.logger import setup_logging, get_logger
from core.config import get_settings, ensure_env_file 

setup_logging() 
logger = get_logger(__name__)

ensure_env_file()
settings = get_settings() 

def setup_pre_run_environment():
    """
    Set up any environment aspects needed before Uvicorn starts the app.
    Logging and .env creation are handled above.
    Database connections and ML models are loaded via FastAPI startup events.
    """
    logger.info("Pre-run environment setup...")
    logger.info(f"Application Name: {settings.APP_NAME}, Version: {settings.APP_VERSION}")
    logger.info(f"Running with DB: {settings.DB_NAME} on URI (first 20 chars): {settings.MONGO_URI[:20]}...")
    
    logger.info("Pre-run environment setup completed.")

def run_app(host: str, port: int, reload: bool, log_level: str):
    """
    Run the FastAPI application using Uvicorn.
    """
    logger.info(f"Starting Urban Air Quality API on http://{host}:{port} with reload={reload}, Uvicorn log level: {log_level}")
    try:
        
        uvicorn.run(
            "app.main_app:app", 
            host=host,
            port=port,
            reload=reload,
            log_level=log_level.lower() 
        )
    except ModuleNotFoundError as e:
        logger.error(f"Failed to import the FastAPI app. Ensure 'app.main_app:app' is correct and all dependencies are installed: {e}", exc_info=True)
        logger.error("Make sure you are running this script from the 'urban_air_quality_api' directory or that the Python path is correctly set.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Urban Air Quality Prediction API")
    
    default_host = settings.APP_HOST
    default_port = settings.APP_PORT
    default_log_level = settings.LOG_LEVEL 

    parser.add_argument(
        "--host", 
        default=default_host, 
        help=f"Host to bind to (default: {default_host})"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=default_port, 
        help=f"Port to bind to (default: {default_port})"
    )
    parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development (Uvicorn feature)"
    )
    parser.add_argument(
        "--log-level",
        default=default_log_level.lower(),
        type=str,
        choices=['critical', 'error', 'warning', 'info', 'debug', 'trace'],
        help=f"Uvicorn log level (default: {default_log_level.lower()})"
    )

    args = parser.parse_args()

    setup_pre_run_environment() 

    run_app(host=args.host, port=args.port, reload=args.reload, log_level=args.log_level)