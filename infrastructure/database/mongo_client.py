import os
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure
from typing import Optional, Any
from bson import ObjectId
import numpy as np

from core.config import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_mongo_client: Optional[MongoClient] = None
_db: Optional[Database] = None

async def connect_to_mongo():
    """
    Establishes a connection to MongoDB.
    This should be called during application startup.
    """
    global _mongo_client, _db
    settings = get_settings()
    
    if _mongo_client and _db:
        logger.info("MongoDB connection already established.")
        return

    logger.info(f"Attempting to connect to MongoDB at {settings.MONGO_URI} (DB: {settings.DB_NAME})")
    try:
        _mongo_client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        _mongo_client.admin.command('ismaster') 
        _db = _mongo_client[settings.DB_NAME]
        logger.info(f"Successfully connected to MongoDB: {settings.DB_NAME}")
        await initialize_collections_and_indexes() 
    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failed: {e}", exc_info=True)
        _mongo_client = None
        _db = None
        raise
    except ConfigurationError as e:
        logger.error(f"MongoDB configuration error: {e}", exc_info=True)
        _mongo_client = None
        _db = None
        raise

async def close_mongo_connection():
    """
    Closes the MongoDB connection.
    This should be called during application shutdown.
    """
    global _mongo_client, _db
    if _mongo_client:
        logger.info("Closing MongoDB connection.")
        _mongo_client.close()
        _mongo_client = None
        _db = None
        logger.info("MongoDB connection closed.")

def get_database() -> Database:
    """
    Returns the MongoDB database instance.
    Raises an exception if the database is not initialized.
    """
    if _db is None:
        logger.error("Database not initialized. Call connect_to_mongo first.")
        raise RuntimeError("Database not initialized. Ensure connect_to_mongo is called during app startup.")
    return _db

async def initialize_collections_and_indexes():
    """
    Initializes database with required collections and indexes if they don't exist.
    This is an idempotent operation.
    Pymongo operations are synchronous but called from an async context here;
    FastAPI will run them in a thread pool.
    """
    db = get_database()
    logger.info("Initializing collections and indexes...")
    
    
    if "predictions" not in db.list_collection_names():
        db.create_collection("predictions")
        logger.info("Created 'predictions' collection.")
    
    predictions_collection = db["predictions"]
    current_indexes_pred = predictions_collection.index_information()
    
    pred_date_index_name = "date_1" 
    pred_timestamp_index_name = "timestamp_-1"
    pred_category_index_name = "predicted_category_1"

    if pred_date_index_name not in current_indexes_pred:
        try:
            predictions_collection.create_index([("date", ASCENDING)], name=pred_date_index_name)
            logger.info(f"Created index '{pred_date_index_name}' on 'predictions.date'.")
        except OperationFailure as e:
            logger.warning(f"Could not create index '{pred_date_index_name}' on 'predictions.date (likely exists with different options or name)': {e}")
    else:
        logger.info(f"Index '{pred_date_index_name}' on 'predictions.date' already exists.")

    if pred_timestamp_index_name not in current_indexes_pred:
        try:
            predictions_collection.create_index([("timestamp", DESCENDING)], name=pred_timestamp_index_name)
            logger.info(f"Created index '{pred_timestamp_index_name}' on 'predictions.timestamp'.")
        except OperationFailure as e:
            logger.warning(f"Could not create index '{pred_timestamp_index_name}' on 'predictions.timestamp (likely exists with different options or name)': {e}")
    else:
        logger.info(f"Index '{pred_timestamp_index_name}' on 'predictions.timestamp' already exists.")
        
    if pred_category_index_name not in current_indexes_pred:
        try:
            predictions_collection.create_index([("predicted_category", ASCENDING)], name=pred_category_index_name)
            logger.info(f"Created index '{pred_category_index_name}' on 'predictions.predicted_category'.")
        except OperationFailure as e:
            logger.warning(f"Could not create index '{pred_category_index_name}' on 'predictions.predicted_category (likely exists with different options or name)': {e}")
    else:
        logger.info(f"Index '{pred_category_index_name}' on 'predictions.predicted_category' already exists.")

    if "current_conditions" not in db.list_collection_names(): 
        db.create_collection("current_conditions")
        logger.info("Created 'current_conditions' collection.")
    
    current_conditions_collection = db["current_conditions"]
    current_indexes_cc = current_conditions_collection.index_information()
    
    cc_timestamp_index_name = "timestamp_-1" 
    cc_location_index_name = "location_idx_cc" 

    if cc_timestamp_index_name not in current_indexes_cc:
        try:
            current_conditions_collection.create_index([("timestamp", DESCENDING)], name=cc_timestamp_index_name)
            logger.info(f"Created index '{cc_timestamp_index_name}' on 'current_conditions.timestamp'.")
        except OperationFailure as e: 
            logger.warning(f"Could not create index '{cc_timestamp_index_name}' on 'current_conditions.timestamp (likely exists with different options or name)': {e}")
    else:
        logger.info(f"Index '{cc_timestamp_index_name}' on 'current_conditions.timestamp' already exists.")

    if cc_location_index_name not in current_indexes_cc:
        try:
            current_conditions_collection.create_index(
                [("location.latitude", ASCENDING), ("location.longitude", ASCENDING)], 
                name=cc_location_index_name
            )
            logger.info(f"Created compound index '{cc_location_index_name}' on 'current_conditions.location.latitude_longitude'.")
        except OperationFailure as e:
            logger.warning(f"Could not create index '{cc_location_index_name}' on 'current_conditions.location (likely exists with different options or name)': {e}")
    else:
        logger.info(f"Index '{cc_location_index_name}' on 'current_conditions.location' already exists.")

    if "locations_cache" not in db.list_collection_names():
        db.create_collection("locations_cache")
        logger.info("Created 'locations_cache' collection.")
    
    locations_cache_collection = db["locations_cache"]
    current_indexes_lc = locations_cache_collection.index_information()
    lc_cache_key_index_name = "cache_key_1"
    lc_ttl_index_name = "expireAt_ttl_idx"

    if lc_cache_key_index_name not in current_indexes_lc:
        try:
            locations_cache_collection.create_index([("cache_key", ASCENDING)], name=lc_cache_key_index_name, unique=True)
            logger.info(f"Created unique index '{lc_cache_key_index_name}' on 'locations_cache.cache_key'.")
        except OperationFailure as e:
             logger.warning(f"Could not create index '{lc_cache_key_index_name}' on 'locations_cache.cache_key (likely exists with different options or name)': {e}")
    else:
        logger.info(f"Index '{lc_cache_key_index_name}' on 'locations_cache.cache_key' already exists.")

    if lc_ttl_index_name not in current_indexes_lc: 
        try:
            locations_cache_collection.create_index("expireAt", expireAfterSeconds=0, name=lc_ttl_index_name)
            logger.info(f"Created TTL index '{lc_ttl_index_name}' on 'locations_cache.expireAt'.")
        except OperationFailure as e:
            logger.warning(f"Could not create TTL index '{lc_ttl_index_name}' on 'locations_cache.expireAt (likely exists with different options or name)': {e}")
    else:
        logger.info(f"TTL Index '{lc_ttl_index_name}' on 'locations_cache.expireAt' already exists.")
    
    logger.info("Collections and indexes initialization check completed.")


def convert_to_serializable(obj: Any) -> Any:
    """
    Recursively converts MongoDB/BSON types and NumPy types to JSON serializable types.
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {convert_to_serializable(key): convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    from datetime import datetime as dt 
    if isinstance(obj, dt):
        return obj.isoformat()
    return obj

if __name__ == "__main__":
    import asyncio
    from infrastructure.logging.logger import setup_logging 
    setup_logging()
    
    async def main():
        try:
            await connect_to_mongo()
            db_instance = get_database()
            logger.info(f"Successfully got DB instance: {db_instance.name}")
            server_info = db_instance.client.server_info()
            logger.info(f"Server info: {server_info.get('version')}")
        except Exception as e:
            logger.error(f"Error during standalone mongo_client test: {e}", exc_info=True)
        finally:
            await close_mongo_connection()
    
    asyncio.run(main())
