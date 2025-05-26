import httpx 
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from domain.repositories.air_quality_service import AirQualityService
from domain.models.air_quality import (
    ExternalAirQualityData, 
    ExternalPollutantDetail, 
    ExternalAQIIndexInfo, 
    LocationContext,
    ExternalPollutantConcentration 
)
from core.config import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class GoogleAirQualityService(AirQualityService):
    """
    Implementation of the AirQualityService using Google Air Quality API.
    """
    def __init__(self):
        self.settings = get_settings()
        self.aq_api_url_base = "https://airquality.googleapis.com/v1/currentConditions:lookup" 
        if not self.settings.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY is not configured in settings. Air Quality API calls will likely fail.")

    def _parse_google_aq_response(self, response_data: Dict[str, Any], lat: float, lon: float) -> ExternalAirQualityData:
        api_country_code = response_data.get("regionCode")
        location_context = LocationContext(
            latitude=lat,
            longitude=lon,
            country=api_country_code if api_country_code else "Unknown", 
            city="Unknown" 
        )

        pollutants_list: List[ExternalPollutantDetail] = []
        for p_data in response_data.get("pollutants", []):
            concentration_dict = p_data.get("concentration", {}) 
            concentration_obj = ExternalPollutantConcentration(
                value=concentration_dict.get("value"), 
                units=concentration_dict.get("units")  
            )

            pollutants_list.append(ExternalPollutantDetail(
                code=p_data.get("code", "unknown").lower(),
                display_name=p_data.get("displayName", "Unknown Pollutant"),
                full_name=p_data.get("fullName", "Unknown Pollutant Full Name"),
                concentration=concentration_obj, 
                additional_info=p_data.get("additionalInfo")
            ))

        aqi_indexes_list: List[ExternalAQIIndexInfo] = []
        for idx_data in response_data.get("indexes", []):
            aqi_indexes_list.append(ExternalAQIIndexInfo(
                name=idx_data.get("displayName", idx_data.get("code", "Unknown Index")),
                aqi_value=int(idx_data.get("aqi", 0)), 
                category=idx_data.get("category", "Unknown"),
                dominant_pollutant=idx_data.get("dominantPollutant") 
            ))
        
        fetch_time_str = response_data.get("dateTime")
        fetch_timestamp = datetime.now(timezone.utc) 
        if fetch_time_str:
            try:
                
                parsed_time = datetime.fromisoformat(fetch_time_str.replace("Z", "+00:00"))
                if parsed_time.tzinfo is None:
                    fetch_timestamp = parsed_time.replace(tzinfo=timezone.utc)
                else:
                    fetch_timestamp = parsed_time.astimezone(timezone.utc)
            except ValueError:
                logger.warning(f"Could not parse dateTime '{fetch_time_str}' from Google AQ API. Using current time.")
        
        return ExternalAirQualityData(
            fetch_timestamp=fetch_timestamp,
            location=location_context,
            pollutants=pollutants_list,
            aqi_indexes=aqi_indexes_list,
            health_recommendations=response_data.get("healthRecommendations", {}),
            raw_data=response_data 
        )

    async def get_current_air_quality(
        self, 
        latitude: float, 
        longitude: float, 
        language_code: str = "en" 
    ) -> Optional[ExternalAirQualityData]:
        logger.info(f"Fetching current air quality from Google AQ API for lat={latitude}, lon={longitude}, lang={language_code}")

        if not self.settings.GOOGLE_API_KEY: 
            logger.error("Cannot fetch air quality: GOOGLE_API_KEY is not set or empty in settings.")
            return None

        request_url = f"{self.aq_api_url_base}?key={self.settings.GOOGLE_API_KEY}"
        
        payload = {
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            "extraComputations": [
                "HEALTH_RECOMMENDATIONS",
                "DOMINANT_POLLUTANT_CONCENTRATION",
                "POLLUTANT_CONCENTRATION",
                "LOCAL_AQI", 
                "POLLUTANT_ADDITIONAL_INFO"
            ],
            "universalAqi": True, 
            "languageCode": language_code
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client: 
                response = await client.post(request_url, json=payload)
                response.raise_for_status() 
                api_response_data = response.json()
            
            if not api_response_data: 
                logger.warning(f"Google AQ API returned empty or malformed JSON response for lat={latitude}, lon={longitude}")
                return None

            parsed_data = self._parse_google_aq_response(api_response_data, latitude, longitude)
            logger.info(f"Successfully fetched and parsed air quality data for lat={latitude}, lon={longitude}")
            return parsed_data

        except httpx.HTTPStatusError as e:
            error_body_text = e.response.text 
            if e.response.status_code == 400 and "Information is unavailable for this location" in error_body_text:
                 logger.warning(f"Google AQ API: Information unavailable for lat={latitude}, lon={longitude}. This is a valid API response indicating no data.")
                 return None 
            logger.error(f"Google AQ API HTTP error for lat={latitude}, lon={longitude}: {e.response.status_code} - Body: {error_body_text}", exc_info=False) 
            return None
        except httpx.RequestError as e: 
            logger.error(f"Google AQ API request error for lat={latitude}, lon={longitude}: {e}", exc_info=True)
            return None
        except Exception as e: 
            logger.error(f"Unexpected error fetching/parsing Google AQ data for lat={latitude}, lon={longitude}: {e}", exc_info=True)
            return None