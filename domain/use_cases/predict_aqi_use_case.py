import pandas as pd
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, date, timezone

from domain.models.air_quality import (
    AQIPredictionInput, AQIPredictionResult,
    PollutantConcentrations, LocationContext, ExternalAirQualityData,
    PredictionToStore, StoredPrediction,
    StoredPredictionInputData, StoredPredictionLocationInfo, StoredPredictionUsedMeasurements,
    GeocodedLocation
)
from domain.repositories.prediction_repository import PredictionRepository
from domain.repositories.ml_model_repository import MLModelRepository
from domain.repositories.location_service import LocationService
from domain.repositories.air_quality_service import AirQualityService
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class PredictAQIUseCase:
    """
    Use case for predicting Air Quality Index (AQI).
    It can optionally auto-fill missing pollutant data using external services.
    """
    def __init__(
        self,
        prediction_repository: PredictionRepository,
        ml_model_repository: MLModelRepository,
        location_service: Optional[LocationService] = None,
        air_quality_service: Optional[AirQualityService] = None
    ):
        self.prediction_repository = prediction_repository
        self.ml_model_repository = ml_model_repository
        self.location_service = location_service
        self.air_quality_service = air_quality_service

    async def _auto_fill_pollutants(
        self,
        current_pollutants: PollutantConcentrations,
        location: LocationContext
    ) -> Tuple[PollutantConcentrations, Optional[StoredPredictionUsedMeasurements], Optional[GeocodedLocation]]:
        """
        Attempts to auto-fill missing pollutant data.
        Returns updated pollutants, used measurements info, and geocoded location details.
        """
        if not self.location_service or not self.air_quality_service:
            logger.warning("Location or AirQuality service not provided for auto-fill. Skipping.")
            return current_pollutants, None, None

        needs_filling = any(
            getattr(current_pollutants, p) is None for p in ["pm25", "pm10", "o3", "no2", "so2", "co"]
        )

        if not needs_filling:
            logger.info("No pollutants missing, auto-fill not required.")
            return current_pollutants, None, None

        logger.info(f"Attempting to auto-fill pollutants for {location.city}, {location.country}")

        geocoded_loc_details: Optional[GeocodedLocation] = None
        if location.latitude is None or location.longitude is None:
            geocoded_loc = await self.location_service.geocode_location(location.country, location.city)
            if not geocoded_loc or geocoded_loc.latitude is None or geocoded_loc.longitude is None:
                logger.warning(f"Could not geocode {location.city}, {location.country} for auto-fill.")
                return current_pollutants, None, None
            lat, lon = geocoded_loc.latitude, geocoded_loc.longitude
            location.latitude = lat
            location.longitude = lon
            location.formatted_address = geocoded_loc.formatted_address
            location.place_id = geocoded_loc.place_id
            geocoded_loc_details = geocoded_loc
        else:
            lat, lon = location.latitude, location.longitude
            geocoded_loc_details = GeocodedLocation(
                latitude=lat, longitude=lon, formatted_address=location.formatted_address or "",
                country=location.country, city=location.city, place_id=location.place_id
            )


        external_aq_data: Optional[ExternalAirQualityData] = await self.air_quality_service.get_current_air_quality(lat, lon)
        if not external_aq_data:
            logger.warning(f"Could not fetch external AQ data for auto-fill at lat={lat}, lon={lon}.")
            return current_pollutants, None, geocoded_loc_details

        updated_pollutants_dict = current_pollutants.model_dump()
        filled_pollutants_from_source: Dict[str, float] = {}
        filled_any = False

        for ext_pollutant in external_aq_data.pollutants:
            pollutant_code = ext_pollutant.code.lower()
            if hasattr(current_pollutants, pollutant_code) and getattr(current_pollutants, pollutant_code) is None:
                if ext_pollutant.concentration and ext_pollutant.concentration.value is not None:
                    value = ext_pollutant.concentration.value
                    updated_pollutants_dict[pollutant_code] = value
                    filled_pollutants_from_source[pollutant_code] = value
                    filled_any = True
                    logger.info(f"Auto-filled '{pollutant_code}' with value {value}")

        if not filled_any:
            logger.info("Auto-fill attempted, but no missing values were updated from external source.")
            return current_pollutants, None, geocoded_loc_details

        updated_pollutants = PollutantConcentrations(**updated_pollutants_dict)

        used_measurements = StoredPredictionUsedMeasurements(
            source=getattr(external_aq_data, 'source_api_name', "External Air Quality Service"),
            timestamp=external_aq_data.fetch_timestamp,
            pollutants=filled_pollutants_from_source
        )
        return updated_pollutants, used_measurements, geocoded_loc_details

    async def execute(
        self,
        prediction_date_str: str,
        pollutants_data: Dict[str, Optional[float]],
        location_data: Dict[str, str],
        auto_fill_missing: bool = False
    ) -> StoredPrediction:
        logger.info(f"Executing PredictAQIUseCase for date: {prediction_date_str}, location: {location_data}")

        try:
            parsed_prediction_date = datetime.strptime(prediction_date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"Invalid date format: {prediction_date_str}. Must be YYYY-MM-DD.")
            raise ValueError("Invalid date format for prediction_date_str. Must be YYYY-MM-DD.")

        initial_pollutants = PollutantConcentrations(**pollutants_data)
        location_context = LocationContext(
            country=location_data['country'],
            city=location_data.get('loc', location_data.get('city')),
            latitude=None,
            longitude=None,
            formatted_address=None,
            place_id=None
        )

        used_measurements_info: Optional[StoredPredictionUsedMeasurements] = None
        geocoded_location_details: Optional[GeocodedLocation] = None
        final_pollutants = initial_pollutants

        if auto_fill_missing:
            updated_pollutants, source_info, geocoded_info = await self._auto_fill_pollutants(
                initial_pollutants, location_context
            )
            if source_info:
                final_pollutants = updated_pollutants
                used_measurements_info = source_info
            if geocoded_info:
                geocoded_location_details = geocoded_info


        aqi_prediction_domain_input = AQIPredictionInput(
            prediction_date=parsed_prediction_date,
            pollutants=final_pollutants,
            location=location_context
        )
        
        input_df_data = {
            'date': [aqi_prediction_domain_input.prediction_date.isoformat()],
            'pm25': [aqi_prediction_domain_input.pollutants.pm25],
            'pm10': [aqi_prediction_domain_input.pollutants.pm10],
            'o3': [aqi_prediction_domain_input.pollutants.o3],
            'no2': [aqi_prediction_domain_input.pollutants.no2],
            'so2': [aqi_prediction_domain_input.pollutants.so2],
            'co': [aqi_prediction_domain_input.pollutants.co],
            'country': [aqi_prediction_domain_input.location.country],
            'loc': [aqi_prediction_domain_input.location.city]
        }
        input_df = pd.DataFrame(input_df_data)

        try:
            prediction_result_obj: AQIPredictionResult = await self.ml_model_repository.get_aqi_prediction(input_df)
        except Exception as e:
            logger.error(f"Error getting prediction from ML model: {e}", exc_info=True)
            raise RuntimeError(f"ML model prediction failed: {e}")

        
        input_data_for_storage = StoredPredictionInputData(
            date=prediction_date_str,
            pm25=initial_pollutants.pm25,
            pm10=initial_pollutants.pm10,
            o3=initial_pollutants.o3,
            no2=initial_pollutants.no2,
            so2=initial_pollutants.so2,
            co=initial_pollutants.co,
            country=location_data['country'],
            loc=location_data.get('loc', location_data.get('city')),
            auto_fill_pollutants=auto_fill_missing
        )

        location_info_for_storage: Optional[StoredPredictionLocationInfo] = None
        if location_context.latitude is not None and location_context.longitude is not None:
            location_info_for_storage = StoredPredictionLocationInfo(
                latitude=location_context.latitude,
                longitude=location_context.longitude,
                formatted_address=location_context.formatted_address,
                display_name=location_context.city,
                place_id=location_context.place_id,
                source=geocoded_location_details.source_api if geocoded_location_details and geocoded_location_details.source_api else "geocoding_service"
            )
        
        prediction_to_store_data = PredictionToStore(
            date=prediction_date_str,
            input_data=input_data_for_storage,
            predicted_category=prediction_result_obj.predicted_category,
            probabilities=prediction_result_obj.probabilities,
            summary=prediction_result_obj.summary_message,
            location_info=location_info_for_storage,
            used_measurements=used_measurements_info,
            timestamp=datetime.now(timezone.utc)
        )

        try:
            prediction_id = await self.prediction_repository.save_prediction(prediction_to_store_data)
        except Exception as e:
            logger.error(f"Error saving prediction to repository: {e}", exc_info=True)
            raise RuntimeError(f"Failed to save prediction: {e}")

        stored_prediction_data_dict = prediction_to_store_data.model_dump()
        stored_prediction_data_dict["id"] = prediction_id

        final_stored_prediction = StoredPrediction(**stored_prediction_data_dict)

        logger.info(f"Prediction successful. ID: {final_stored_prediction.id}, Category: {final_stored_prediction.predicted_category}")
        return final_stored_prediction