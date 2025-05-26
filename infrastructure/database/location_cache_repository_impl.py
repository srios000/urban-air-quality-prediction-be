from typing import Optional
from datetime import datetime, timedelta, timezone 
from pymongo.database import Database
from pydantic_core import ValidationError 
from domain.repositories.location_cache_repository import LocationCacheRepository
from domain.models.air_quality import GeocodedLocation
from infrastructure.database.mongo_client import get_database
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class MongoLocationCacheRepository(LocationCacheRepository):
    """
    MongoDB implementation of the LocationCacheRepository for geocoded and reverse geocoded data.
    Uses a TTL index on MongoDB for automatic expiration of cache entries.
    """
    def __init__(self):
        self._db: Database = get_database()
        self._locations_cache_collection = self._db["locations_cache"]

    def _generate_geocode_cache_key(self, country: str, city: str) -> str:
        return f"geocode:{country.lower().replace(' ', '_')}:{city.lower().replace(' ', '_')}"

    def _generate_reverse_geocode_cache_key(self, latitude: float, longitude: float) -> str:
        
        return f"revgeo:{latitude:.6f}:{longitude:.6f}"

    async def _get_location_from_cache(self, cache_key: str) -> Optional[GeocodedLocation]:
        logger.debug(f"Attempting to get location from cache with key: {cache_key}")
        try:
            document = self._locations_cache_collection.find_one({"cache_key": cache_key})
            
            if document:
                logger.info(f"Cache hit for key: {cache_key}")
                data_field = document.get('data', document) 
                return GeocodedLocation.model_validate(data_field)
            else:
                logger.info(f"Cache miss for key: {cache_key}")
                return None
        except ValidationError as ve:
            logger.error(f"Pydantic validation error for cache key {cache_key}: {ve}", exc_info=False)
            return None
        except Exception as e:
            logger.error(f"Error retrieving location for key {cache_key} from cache: {e}", exc_info=True)
            return None

    async def _save_location_to_cache(
        self, 
        cache_key: str, 
        location_data: GeocodedLocation, 
        ttl_seconds: Optional[int]
    ) -> None:
        logger.info(f"Saving location to cache with key: {cache_key}, TTL: {ttl_seconds}s")
        current_time_utc = datetime.now(timezone.utc)
        expire_at = current_time_utc + timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        
        cache_document = {
            "cache_key": cache_key,
            "data": location_data.model_dump(mode='json'), 
            "created_at": current_time_utc,
        }
        if expire_at:
            cache_document["expireAt"] = expire_at
        
        try:
            self._locations_cache_collection.update_one(
                {"cache_key": cache_key},
                {"$set": cache_document},
                upsert=True
            )
            logger.info(f"Successfully saved/updated location for key {cache_key} in cache.")
        except Exception as e:
            logger.error(f"Error saving location for key {cache_key} to cache: {e}", exc_info=True)

    async def get_geocoded_location(self, country: str, city: str) -> Optional[GeocodedLocation]:
        cache_key = self._generate_geocode_cache_key(country, city)
        return await self._get_location_from_cache(cache_key)

    async def save_geocoded_location(
        self, 
        country: str, 
        city: str, 
        location_data: GeocodedLocation,
        ttl_seconds: Optional[int] = 86400  
    ) -> None:
        cache_key = self._generate_geocode_cache_key(country, city)
        await self._save_location_to_cache(cache_key, location_data, ttl_seconds)

    async def get_reverse_geocoded_location(self, latitude: float, longitude: float) -> Optional[GeocodedLocation]:
        cache_key = self._generate_reverse_geocode_cache_key(latitude, longitude)
        return await self._get_location_from_cache(cache_key)

    async def save_reverse_geocoded_location(
        self, 
        latitude: float, 
        longitude: float, 
        location_data: GeocodedLocation,
        ttl_seconds: Optional[int] = 86400
    ) -> None:
        cache_key = self._generate_reverse_geocode_cache_key(latitude, longitude)
        await self._save_location_to_cache(cache_key, location_data, ttl_seconds)