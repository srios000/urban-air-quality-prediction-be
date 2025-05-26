from fastapi import APIRouter, HTTPException, Depends
from app.models import LocationRequest, LocationAQIResponse, ErrorResponse
from domain.use_cases.get_air_quality_for_location_use_case import GetAirQualityForLocationUseCase
from app.dependencies import get_air_quality_for_location_use_case
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/location-aqi",
    tags=["Location Air Quality"],
    responses={404: {"description": "Not found"}}
)

@router.post(
    "/",
    response_model=LocationAQIResponse,
    summary="Get Air Quality by Location Name",
    description="Fetches current air quality data for a specified location (country and city). "
                "Geocodes the location, retrieves AQ data, and optionally provides an AQI prediction.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation Error or Invalid Location"},
        404: {"model": ErrorResponse, "description": "Location not found or no AQI data available"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
async def get_aqi_by_location_name(
    request: LocationRequest,
    use_case: GetAirQualityForLocationUseCase = Depends(get_air_quality_for_location_use_case)
):
    logger.info(f"Received request for AQI by location: {request.country}, {request.loc}")
    try:
        result_dict = await use_case.execute(
            country=request.country,
            city=request.loc,
            language_code=request.language_code,
            make_prediction=True 
        )

        if result_dict is None:
            logger.warning(f"No data found or error for location: {request.country}, {request.loc}")
            raise HTTPException(status_code=404, detail="Air quality data not available for the specified location, or geocoding failed.")
        
        
        
        response = LocationAQIResponse.model_validate(result_dict)
        logger.info(f"Successfully fetched AQI data for location: {request.country}, {request.loc}")
        return response

    except ValueError as ve: 
        logger.warning(f"Validation error for location AQI request: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException: 
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching AQI by location name: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")