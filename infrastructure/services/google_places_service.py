import httpx
from typing import Optional, Dict, Any
from domain.repositories.location_service import LocationService
from domain.repositories.location_cache_repository import LocationCacheRepository
from domain.models.air_quality import GeocodedLocation
from core.config import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class GooglePlacesService(LocationService):
    def __init__(self, cache_repository: LocationCacheRepository):
        self.settings = get_settings()
        self.cache_repository = cache_repository
        self.places_api_url = "https://places.googleapis.com/v1/places:searchText"
        self.geocoding_api_url = "https://maps.googleapis.com/maps/api/geocode/json" 
        if not self.settings.GOOGLE_MAPS_API_KEY:
            logger.warning("GOOGLE_MAPS_API_KEY is not configured. Geocoding services might fail.")

    def _get_api_key(self) -> Optional[str]:
        if not self.settings.GOOGLE_MAPS_API_KEY:
            logger.error("GOOGLE_MAPS_API_KEY is not set.")
            return None
        return self.settings.GOOGLE_MAPS_API_KEY

    async def geocode_location(self, country: str, city: str) -> Optional[GeocodedLocation]:
        logger.info(f"Geocoding location: City='{city}', Country='{country}'")
        api_key = self._get_api_key()
        if not api_key:
            return None

        cached_location = await self.cache_repository.get_geocoded_location(country, city)
        if cached_location:
            logger.info(f"Cache hit for geocoding: {city}, {country}")
            cached_location.source_api = "google_places_api (cached)" 
            return cached_location

        logger.info(f"Cache miss for geocoding: {city}, {country}. Calling Google Places API.")
        query = f"{city}, {country}"
        payload = {"textQuery": query, "languageCode": "en", "maxResultCount": 1}
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.addressComponents"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.places_api_url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            if not result.get("places"):
                logger.warning(f"No places found by Google Places API for query: '{query}'")
                return None
            
            place = result["places"][0]
            location_data = place.get("location", {})
            latitude = location_data.get("latitude")
            longitude = location_data.get("longitude")

            if latitude is None or longitude is None:
                logger.warning(f"Lat/Lng missing in Places API response for '{query}'.")
                return None

            parsed_city_from_api = None
            parsed_country_from_api = None
            address_components = place.get("addressComponents", [])
            for component in address_components:
                types = component.get("types", [])
                if not parsed_city_from_api and ("locality" in types or "administrative_area_level_2" in types):
                    parsed_city_from_api = component.get("longName")
                if not parsed_country_from_api and "country" in types:
                    parsed_country_from_api = component.get("longName")
            
            if not parsed_city_from_api:
                for component in address_components:
                    if "administrative_area_level_1" in component.get("types", []):
                         parsed_city_from_api = component.get("longName") 
                         break

            geocoded = GeocodedLocation(
                latitude=float(latitude),
                longitude=float(longitude),
                formatted_address=place.get("formattedAddress", f"{city}, {country}"),
                city=parsed_city_from_api or city,
                country=parsed_country_from_api or country,
                place_id=place.get("id"),
                source_api="google_places_api"
            )
            await self.cache_repository.save_geocoded_location(country, city, geocoded)
            logger.info(f"Successfully geocoded and cached: {geocoded.city}, {geocoded.country}")
            return geocoded
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Places API HTTP error for '{query}': {e.response.status_code} - {e.response.text}", exc_info=False)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during geocoding for '{query}': {e}", exc_info=True)
            return None

    async def reverse_geocode_location(self, latitude: float, longitude: float) -> Optional[GeocodedLocation]:
        logger.info(f"Reverse geocoding location: Lat='{latitude}', Lon='{longitude}'")
        api_key = self._get_api_key()
        if not api_key:
            return None

        cached_location = await self.cache_repository.get_reverse_geocoded_location(latitude, longitude)
        if cached_location:
            logger.info(f"Cache hit for reverse geocoding: Lat={latitude}, Lon={longitude}")
            cached_location.source_api = "google_geocoding_api (cached)"
            return cached_location

        logger.info(f"Cache miss for reverse geocoding: Lat={latitude}, Lon={longitude}. Calling Google Geocoding API.")
        
        params = {
            "latlng": f"{latitude},{longitude}",
            "key": api_key,
            "language": "en", 
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.geocoding_api_url, params=params)
                response.raise_for_status()
                result = response.json()

            if not result or result.get("status") != "OK" or not result.get("results"):
                logger.warning(f"No results or error from Google Geocoding API for lat={latitude}, lon={longitude}. Status: {result.get('status')}, Error: {result.get('error_message')}")
                return None
            
            place_data = result["results"][0]
            
            parsed_city_from_api = None
            parsed_country_from_api = None
            address_components = place_data.get("address_components", [])

            for component in address_components:
                types = component.get("types", [])
                if not parsed_city_from_api and ("locality" in types or "administrative_area_level_2" in types):
                    
                    parsed_city_from_api = component.get("long_name")
                if not parsed_country_from_api and "country" in types:
                    parsed_country_from_api = component.get("long_name")
            
            if not parsed_city_from_api:
                for component in address_components:
                    if "administrative_area_level_1" in component.get("types", []): 
                        parsed_city_from_api = component.get("long_name")
                        break
            city_to_use = parsed_city_from_api if parsed_city_from_api else "Unknown" 

            geocoded = GeocodedLocation(
                latitude=latitude, 
                longitude=longitude, 
                formatted_address=place_data.get("formatted_address", f"Lat: {latitude}, Lon: {longitude}"),
                city=city_to_use,
                country=parsed_country_from_api or "Unknown", 
                place_id=place_data.get("place_id"),
                source_api="google_geocoding_api"
            )

            await self.cache_repository.save_reverse_geocoded_location(latitude, longitude, geocoded)
            logger.info(f"Successfully reverse geocoded and cached: {geocoded.city}, {geocoded.country}")
            return geocoded
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Geocoding API HTTP error for lat={latitude}, lon={longitude}: {e.response.status_code} - {e.response.text}", exc_info=False)
            return None
        except Exception as e:
            logger.error(f"Unexpected error during reverse geocoding for lat={latitude}, lon={longitude}: {e}", exc_info=True)
            return None