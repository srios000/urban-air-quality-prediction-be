from fastapi import APIRouter, HTTPException, Depends
from app.models import CurrentConditionsRequest, LocationAQIResponse, ErrorResponse 
from domain.use_cases.get_current_air_quality_use_case import GetCurrentAirQualityUseCase
from app.dependencies import get_current_air_quality_use_case
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/v1/current-conditions",
    tags=["Current Air Quality Conditions"],
    responses={404: {"description": "Not found"}}
)

@router.post(
    "/",
    response_model=LocationAQIResponse, 
    summary="Get Current Air Quality by Coordinates",
    description="Fetches current air quality data for specified latitude and longitude. "
                "Retrieves AQ data and optionally provides an AQI prediction.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation Error or Invalid Coordinates"},
        404: {"model": ErrorResponse, "description": "No AQI data available for the coordinates"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)
async def get_aqi_by_coordinates(
    request: CurrentConditionsRequest,
    use_case: GetCurrentAirQualityUseCase = Depends(get_current_air_quality_use_case)
):
    logger.info(f"Received request for current conditions by coordinates: lat={request.latitude}, lon={request.longitude}")
    try:
        result_dict = await use_case.execute(
            latitude=request.latitude,
            longitude=request.longitude,
            language_code=request.language_code,
            make_prediction=True 
        )

        if result_dict is None:
            logger.warning(f"No data found or error for coordinates: lat={request.latitude}, lon={request.longitude}")
            raise HTTPException(status_code=404, detail="Air quality data not available for the specified coordinates.")

        response = LocationAQIResponse.model_validate(result_dict)
        logger.info(f"Successfully fetched current conditions for coordinates: lat={request.latitude}, lon={request.longitude}")
        return response

    except ValueError as ve:
        logger.warning(f"Validation error for current conditions request: {ve}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching current conditions by coordinates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")