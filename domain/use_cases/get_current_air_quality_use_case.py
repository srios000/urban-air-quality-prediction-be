from datetime import datetime, timezone
import pandas as pd
import uuid
from typing import Dict, Any, Optional

from domain.models.air_quality import (
    LocationContext, ExternalAirQualityData, PollutantConcentrations, AQIPredictionResult, GeocodedLocation
)
from domain.repositories.air_quality_service import AirQualityService
from domain.repositories.ml_model_repository import MLModelRepository
from domain.repositories.current_conditions_repository import CurrentConditionsRepository
from domain.repositories.location_service import LocationService
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class GetCurrentAirQualityUseCase:
    def __init__(
        self,
        air_quality_service: AirQualityService,
        ml_model_repository: MLModelRepository,
        current_conditions_repository: CurrentConditionsRepository,
        location_service: LocationService 
    ):
        self.air_quality_service = air_quality_service
        self.ml_model_repository = ml_model_repository
        self.current_conditions_repository = current_conditions_repository
        self.location_service = location_service

    async def execute(
        self,
        latitude: float,
        longitude: float,
        language_code: str = "en",
        make_prediction: bool = True
    ) -> Optional[Dict[str, Any]]:
        logger.info(f"Executing GetCurrentAirQualityUseCase for lat={latitude}, lon={longitude}")

        external_aq_data: Optional[ExternalAirQualityData] = await self.air_quality_service.get_current_air_quality(
            latitude=latitude,
            longitude=longitude,
            language_code=language_code
        )
        if not external_aq_data:
            logger.warning(f"Could not fetch external AQ data for lat={latitude}, lon={longitude}")
            return None

        location_context_to_use: Optional[LocationContext] = external_aq_data.location
        
        if not location_context_to_use:
             logger.warning(f"No initial location context in external_aq_data for lat={latitude}, lon={longitude}. Creating one.")
             location_context_to_use = LocationContext(latitude=latitude, longitude=longitude, city="Unknown", country="Unknown")
             external_aq_data.location = location_context_to_use

        if location_context_to_use.city == "Unknown" or not location_context_to_use.city:
            logger.info(f"City is '{location_context_to_use.city}'. Attempting reverse geocoding for lat={latitude}, lon={longitude}")
            try:
                reverse_geocoded_info: Optional[GeocodedLocation] = await self.location_service.reverse_geocode_location(
                    latitude=latitude, longitude=longitude
                )
                if reverse_geocoded_info:
                    logger.info(f"Reverse geocoding successful: City='{reverse_geocoded_info.city}', Country='{reverse_geocoded_info.country}'")
                    location_context_to_use.city = reverse_geocoded_info.city or location_context_to_use.city
                    location_context_to_use.country = reverse_geocoded_info.country or location_context_to_use.country
                    location_context_to_use.formatted_address = reverse_geocoded_info.formatted_address or location_context_to_use.formatted_address
                    location_context_to_use.place_id = reverse_geocoded_info.place_id or location_context_to_use.place_id
                else:
                    logger.warning(f"Reverse geocoding did not return information for lat={latitude}, lon={longitude}.")
            except Exception as e:
                logger.error(f"Error during reverse geocoding call for lat={latitude}, lon={longitude}: {e}", exc_info=True)
        
        external_aq_data.location = location_context_to_use

        pollutants_summary_response = {}
        if external_aq_data.pollutants:
            for p_detail in external_aq_data.pollutants:
                if hasattr(PollutantConcentrations, p_detail.code) and p_detail.concentration and p_detail.concentration.value is not None:
                    pollutants_summary_response[p_detail.code] = p_detail.concentration.value

        prediction_payload_for_response: Optional[Dict[str, Any]] = None
        aqi_prediction_result_domain: Optional[AQIPredictionResult] = None

        if make_prediction and external_aq_data.pollutants:
            pollutants_for_pred_dict = {}
            for p_detail in external_aq_data.pollutants:
                if hasattr(PollutantConcentrations, p_detail.code) and p_detail.concentration and p_detail.concentration.value is not None :
                    pollutants_for_pred_dict[p_detail.code] = p_detail.concentration.value

            pollutants_obj_data = {
                field_name: pollutants_for_pred_dict.get(field_name)
                for field_name in PollutantConcentrations.model_fields.keys()
            }
            prediction_request_date = datetime.now(timezone.utc).date()

            input_df_data = {
                'date': [prediction_request_date.isoformat()],
                'country': [location_context_to_use.country or "Unknown"],
                'loc': [location_context_to_use.city or "Unknown"],
                **{k: [v] for k,v in pollutants_obj_data.items()}
            }
            input_df = pd.DataFrame(input_df_data)
            try:
                aqi_prediction_result_domain = await self.ml_model_repository.get_aqi_prediction(input_df)
                if aqi_prediction_result_domain:
                    logger.info(f"Prediction made for lat={latitude}, lon={longitude} (Location: {location_context_to_use.city}, {location_context_to_use.country}): {aqi_prediction_result_domain.predicted_category}")
                    current_utc_timestamp = datetime.now(timezone.utc)
                    prediction_payload_for_response = {
                        "prediction_id": str(uuid.uuid4()),
                        "date": prediction_request_date.isoformat(),
                        "predicted_category": aqi_prediction_result_domain.predicted_category,
                        "probabilities": aqi_prediction_result_domain.probabilities,
                        "summary": (f"Air quality on {prediction_request_date.isoformat()} near "
                                    f"lat={latitude}, lon={longitude} (Location: {location_context_to_use.city or 'N/A'}, {location_context_to_use.country or 'N/A'}) "
                                    f"is predicted to be: {aqi_prediction_result_domain.predicted_category}."),
                        "timestamp": current_utc_timestamp,
                        "location_info": location_context_to_use.model_dump(mode='json'),
                        "used_measurements": {
                            "source": "Derived from current conditions via Google Air Quality API, enriched by Reverse Geocoding",
                            "timestamp": external_aq_data.fetch_timestamp if external_aq_data.fetch_timestamp else current_utc_timestamp,
                            "pollutants": pollutants_summary_response
                        },
                        "input_data": {
                            "date": prediction_request_date.isoformat(),
                            "country": location_context_to_use.country or "Unknown",
                            "loc": location_context_to_use.city or "Unknown",
                            **pollutants_obj_data
                        }
                    }
                else:
                    logger.warning(f"ML model did not return a prediction for lat={latitude}, lon={longitude}")
            except Exception as e:
                logger.error(f"Failed to make prediction for lat={latitude}, lon={longitude}: {e}", exc_info=True)

        try:
            await self.current_conditions_repository.save_current_conditions(
                external_aq_data=external_aq_data, 
                prediction_result=aqi_prediction_result_domain
            )
            logger.info(f"Saved current conditions for lat={latitude}, lon={longitude} (Location: {location_context_to_use.city}, {location_context_to_use.country}) to repository.")
        except Exception as e:
            logger.error(f"Failed to save current conditions for lat={latitude}, lon={longitude}: {e}", exc_info=True)

        response_payload = {
            "timestamp": datetime.now(timezone.utc),
            "location": location_context_to_use.model_dump(mode='json'),
            "current_pollutants_summary": pollutants_summary_response,
            "external_aq_data": external_aq_data.model_dump(mode='json'),
            "prediction": prediction_payload_for_response,
        }
        return response_payload