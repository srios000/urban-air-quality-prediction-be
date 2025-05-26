from functools import lru_cache 
from fastapi import Depends 

# Infrastructure
from infrastructure.database.mongo_client import get_database 
from infrastructure.database.prediction_repository_impl import MongoPredictionRepository
from infrastructure.database.current_conditions_repository_impl import MongoCurrentConditionsRepository
from infrastructure.database.location_cache_repository_impl import MongoLocationCacheRepository
from infrastructure.services.google_places_service import GooglePlacesService
from infrastructure.services.google_air_quality_service import GoogleAirQualityService
from infrastructure.ml.ml_model_repository_impl import ConcreteMLModelRepository

# Domain (Repositories - Interfaces)
from domain.repositories.prediction_repository import PredictionRepository
from domain.repositories.current_conditions_repository import CurrentConditionsRepository
from domain.repositories.location_cache_repository import LocationCacheRepository
from domain.repositories.location_service import LocationService
from domain.repositories.air_quality_service import AirQualityService
from domain.repositories.ml_model_repository import MLModelRepository

# Domain (Use Cases)
from domain.use_cases.predict_aqi_use_case import PredictAQIUseCase
from domain.use_cases.get_prediction_history_use_case import GetPredictionHistoryUseCase
from domain.use_cases.get_air_quality_for_location_use_case import GetAirQualityForLocationUseCase
from domain.use_cases.get_current_air_quality_use_case import GetCurrentAirQualityUseCase

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# --- Repository and Service Instantiation ---

@lru_cache()
def get_prediction_repository() -> PredictionRepository:
    get_database() 
    return MongoPredictionRepository()

@lru_cache()
def get_current_conditions_repository() -> CurrentConditionsRepository:
    get_database()
    return MongoCurrentConditionsRepository()

@lru_cache()
def get_location_cache_repository() -> LocationCacheRepository:
    get_database()
    return MongoLocationCacheRepository()

@lru_cache()
def get_ml_model_repository() -> MLModelRepository:
    repo = ConcreteMLModelRepository()
    if not repo.are_resources_loaded():
        logger.warning("ML resources may not be loaded during MLModelRepository instantiation.")
    return repo


@lru_cache()
def get_location_service(
    cache_repo: LocationCacheRepository = Depends(get_location_cache_repository)
) -> LocationService:
    return GooglePlacesService(cache_repository=cache_repo)

@lru_cache()
def get_air_quality_service() -> AirQualityService:
    return GoogleAirQualityService()


# --- Use Case Instantiation ---
def get_predict_aqi_use_case(
    prediction_repo: PredictionRepository = Depends(get_prediction_repository),
    ml_model_repo: MLModelRepository = Depends(get_ml_model_repository),
    location_service: LocationService = Depends(get_location_service),
    air_quality_service: AirQualityService = Depends(get_air_quality_service)
) -> PredictAQIUseCase:
    return PredictAQIUseCase(
        prediction_repository=prediction_repo,
        ml_model_repository=ml_model_repo,
        location_service=location_service,
        air_quality_service=air_quality_service
    )

def get_prediction_history_use_case(
    prediction_repo: PredictionRepository = Depends(get_prediction_repository)
) -> GetPredictionHistoryUseCase:
    return GetPredictionHistoryUseCase(prediction_repository=prediction_repo)

def get_air_quality_for_location_use_case(
    location_service: LocationService = Depends(get_location_service),
    air_quality_service: AirQualityService = Depends(get_air_quality_service),
    ml_model_repo: MLModelRepository = Depends(get_ml_model_repository),
    current_conditions_repo: CurrentConditionsRepository = Depends(get_current_conditions_repository)
) -> GetAirQualityForLocationUseCase:
    return GetAirQualityForLocationUseCase(
        location_service=location_service,
        air_quality_service=air_quality_service,
        ml_model_repository=ml_model_repo,
        current_conditions_repository=current_conditions_repo
    )

def get_current_air_quality_use_case(
    air_quality_service: AirQualityService = Depends(get_air_quality_service),
    ml_model_repo: MLModelRepository = Depends(get_ml_model_repository),
    current_conditions_repo: CurrentConditionsRepository = Depends(get_current_conditions_repository),
    location_service: LocationService = Depends(get_location_service)
) -> GetCurrentAirQualityUseCase:
    return GetCurrentAirQualityUseCase(
        air_quality_service=air_quality_service,
        ml_model_repository=ml_model_repo,
        current_conditions_repository=current_conditions_repo,
        location_service=location_service
    )