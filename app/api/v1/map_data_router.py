from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from app.models import HeatmapDataPoint, AllConditionsDataResponse, ErrorResponse
from domain.repositories.current_conditions_repository import CurrentConditionsRepository
from domain.repositories.prediction_repository import PredictionRepository
from app.dependencies import get_current_conditions_repository, get_prediction_repository

from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/map-data",
    tags=["Backend Map Data"],
    responses={
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
        503: {"model": ErrorResponse, "description": "Service Unavailable (e.g., Database Error)"}
    }
)

@router.get(
    "/all",
    response_model=AllConditionsDataResponse,
    summary="Get All Current Conditions and Predictions Data for Heatmap",
    description="Fetches all stored current air quality conditions and predictions, transformed for heatmap display. "
                "Latitude, longitude, and AQI (or equivalent predicted value) are extracted. "
                "A default AQI is used if a specific value cannot be determined.",
    responses={
        404: {"model": ErrorResponse, "description": "No data available to display (could be empty after filtering)"}
    }
)
async def get_all_data_for_map(
    current_conditions_repo: CurrentConditionsRepository = Depends(get_current_conditions_repository),
    prediction_repo: PredictionRepository = Depends(get_prediction_repository)
):
    logger.info("Request received for /api/v1/map-data/all")
    try:
        current_conditions_heatmap_points: List[HeatmapDataPoint] = \
            await current_conditions_repo.get_all_current_conditions_for_map()
        logger.info(f"Retrieved {len(current_conditions_heatmap_points)} heatmap points from current conditions.")

        prediction_heatmap_points: List[HeatmapDataPoint] = \
            await prediction_repo.get_all_predictions_for_map()
        logger.info(f"Retrieved {len(prediction_heatmap_points)} heatmap points from predictions.")

        all_heatmap_points: List[HeatmapDataPoint] = current_conditions_heatmap_points + prediction_heatmap_points
        
        total_points = len(all_heatmap_points)
        logger.info(f"Total heatmap points from all sources: {total_points}")

        if not all_heatmap_points:
            logger.info("No data found from any source for the map.")
            raise HTTPException(status_code=404, detail="No map data available from any source.")
            
        
        logger.info(f"Successfully processed {total_points} valid data points for map from all sources.")
        return AllConditionsDataResponse(items=all_heatmap_points, total_count=total_points)

    except ConnectionError as ce:
        logger.error(f"Database connection error for /map-data/all: {ce}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service unavailable due to a database error: {str(ce)}")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in /map-data/all endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected internal error occurred: {str(e)}")

