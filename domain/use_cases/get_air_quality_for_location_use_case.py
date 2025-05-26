from typing import Optional, Dict, Any
from datetime import datetime, timezone
import pandas as pd
import uuid

from domain.models.air_quality import (
    LocationContext, ExternalAirQualityData, GeocodedLocation,
    PollutantConcentrations, AQIPredictionInput, AQIPredictionResult,
    StoredCurrentConditions
)
from domain.repositories.location_service import LocationService
from domain.repositories.air_quality_service import AirQualityService
from domain.repositories.ml_model_repository import MLModelRepository
from domain.repositories.current_conditions_repository import CurrentConditionsRepository
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class GetAirQualityForLocationUseCase:
    def __init__(
        self,
        location_service: LocationService,
        air_quality_service: AirQualityService,
        ml_model_repository: MLModelRepository,
        current_conditions_repository: CurrentConditionsRepository
    ):
        self.location_service = location_service
        self.air_quality_service = air_quality_service
        self.ml_model_repository = ml_model_repository
        self.current_conditions_repository = current_conditions_repository

    async def execute(
        self,
        country: str,
        city: str,
        language_code: str = "en",
        make_prediction: bool = True
    ) -> Optional[Dict[str, Any]]:
        logger.info(f"Executing GetAirQualityForLocationUseCase for {city}, {country}")

        geocoded_location: Optional[GeocodedLocation] = await self.location_service.geocode_location(country, city)
        if not geocoded_location or geocoded_location.latitude is None or geocoded_location.longitude is None:
            logger.warning(f"Could not geocode location: {city}, {country}")
            return None

        location_context = LocationContext(
            country=geocoded_location.country or country,
            city=geocoded_location.city or city,
            latitude=geocoded_location.latitude,
            longitude=geocoded_location.longitude,
            formatted_address=geocoded_location.formatted_address,
            place_id=geocoded_location.place_id
        )

        external_aq_data: Optional[ExternalAirQualityData] = await self.air_quality_service.get_current_air_quality(
            latitude=location_context.latitude,
            longitude=location_context.longitude,
            language_code=language_code
        )

        if not external_aq_data:
            logger.warning(f"Could not fetch external AQ data for {city}, {country}")
            return None

        external_aq_data.location = location_context

        pollutants_summary_response = {}
        if external_aq_data.pollutants:
            for p_detail in external_aq_data.pollutants:
                if hasattr(PollutantConcentrations, p_detail.code) and p_detail.concentration:
                    pollutants_summary_response[p_detail.code] = p_detail.concentration.value


        prediction_payload_for_response: Optional[Dict[str, Any]] = None
        aqi_prediction_result_domain: Optional[AQIPredictionResult] = None

        if make_prediction and external_aq_data.pollutants:
            pollutants_for_pred_dict = {}
            for p_detail in external_aq_data.pollutants:
                 if hasattr(PollutantConcentrations, p_detail.code) and p_detail.concentration:
                    pollutants_for_pred_dict[p_detail.code] = p_detail.concentration.value

            pollutants_obj_data = {
                field_name: pollutants_for_pred_dict.get(field_name)
                for field_name in PollutantConcentrations.model_fields.keys()
            }
            prediction_request_date = datetime.now(timezone.utc).date()

            input_df_data = {
                'date': [prediction_request_date.isoformat()],
                'country': [location_context.country],
                'loc': [location_context.city],
                **{k: [v] for k,v in pollutants_obj_data.items()}
            }
            input_df = pd.DataFrame(input_df_data)

            try:
                aqi_prediction_result_domain = await self.ml_model_repository.get_aqi_prediction(input_df)

                if aqi_prediction_result_domain:
                    logger.info(f"Prediction made for {city}, {country} based on current data: {aqi_prediction_result_domain.predicted_category}")
                    current_utc_timestamp = datetime.now(timezone.utc)

                    prediction_payload_for_response = {
                        "prediction_id": str(uuid.uuid4()),
                        "date": prediction_request_date.isoformat(),
                        "predicted_category": aqi_prediction_result_domain.predicted_category,
                        "probabilities": aqi_prediction_result_domain.probabilities,
                        "summary": (f"Air quality on {prediction_request_date.isoformat()} in "
                                    f"{location_context.city}, {location_context.country} "
                                    f"is predicted to be: {aqi_prediction_result_domain.predicted_category}."),
                        "timestamp": current_utc_timestamp,
                        "location_info": location_context.model_dump(mode='json'),
                        "used_measurements": {
                            "source": "Derived from current conditions via Google Air Quality API",
                            "timestamp": external_aq_data.data_time if hasattr(external_aq_data, 'data_time') and external_aq_data.data_time else current_utc_timestamp,
                            "pollutants": pollutants_summary_response
                        },
                        "input_data": {
                            "date": prediction_request_date.isoformat(),
                            "country": location_context.country,
                            "loc": location_context.city,
                            **pollutants_obj_data
                        }
                    }
                else:
                    logger.warning(f"ML model did not return a prediction for {city}, {country}")

            except Exception as e:
                logger.error(f"Failed to make prediction for {city}, {country}: {e}", exc_info=True)

        try:
            await self.current_conditions_repository.save_current_conditions(
                external_aq_data=external_aq_data,
                prediction_result=aqi_prediction_result_domain
            )
            logger.info(f"Saved current conditions for {city}, {country} to repository.")
        except Exception as e:
            logger.error(f"Failed to save current conditions for {city}, {country}: {e}", exc_info=True)

        response_payload = {
            "timestamp": datetime.now(timezone.utc),
            "location": location_context.model_dump(mode='json'),
            "current_pollutants_summary": pollutants_summary_response,
            "external_aq_data": external_aq_data.model_dump(mode='json'),
            "prediction": prediction_payload_for_response,
        }
        return response_payload