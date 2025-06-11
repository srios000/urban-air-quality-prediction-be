from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from core.config import get_settings
from infrastructure.logging.logger import setup_logging, get_logger
from infrastructure.database.mongo_client import connect_to_mongo, close_mongo_connection
from infrastructure.ml.ml_model_repository_impl import ConcreteMLModelRepository

from app.api.v1 import prediction_router, location_router, current_conditions_router, map_data_router

setup_logging() 
logger = get_logger(__name__)

# --- App Initialization ---
settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API for urban air quality prediction and current conditions monitoring.",
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# --- Event Handlers (Startup/Shutdown) ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup: Initializing resources...")
    try:
        # 1. Connect to MongoDB
        await connect_to_mongo()
        logger.info("MongoDB connection established.")
        
        # 2. Load ML Model Resources
        ml_repo = ConcreteMLModelRepository()
        await ml_repo.load_resources()
        if ml_repo.are_resources_loaded():
            logger.info("ML Model resources loaded successfully.")
        else:
            logger.error("CRITICAL: ML Model resources failed to load on startup!")
            raise Exception("ML Model resources failed to load")
            
        logger.info("Application resources initialized.")
    except Exception as e:
        logger.error(f"CRITICAL: Error during application startup: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown: Closing resources...")
    await close_mongo_connection()
    logger.info("MongoDB connection closed.")
    logger.info("Application shutdown complete.")

# --- Exception Handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException caught: Status Code={exc.status_code}, Detail='{exc.detail}' Path='{request.url.path}'")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc} for request {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal server error occurred."}
    )


# --- Static Files ---
static_files_path = Path(__file__).parent.parent / "static"
if static_files_path.exists() and static_files_path.is_dir():
    app.mount("/static", StaticFiles(directory=static_files_path), name="static")
    logger.info(f"Serving static files from {static_files_path}")


# --- Root Endpoint ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False, tags=["Root"])
async def root():
    return f"""
    <html>
        <head>
            <title>Urban Air Quality API</title>
        </head>
        <body>
            <h1>Welcome to the {settings.APP_NAME} v{settings.APP_VERSION}</h1>
            <p>This API provides endpoints for air quality predictions and current conditions.</p>
            <p>Visit <a href="/docs">/docs</a> for the API documentation (Swagger UI).</p>
            <p>Or visit <a href="/redoc">/redoc</a> for ReDoc documentation.</p>
        </body>
    </html>
    """

# --- Include API Routers ---
app.include_router(prediction_router.router)
app.include_router(location_router.router)
app.include_router(current_conditions_router.router)
app.include_router(map_data_router.router)

logger.info("FastAPI application configured and routers included.")