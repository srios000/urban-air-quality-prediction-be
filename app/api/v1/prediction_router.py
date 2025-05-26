
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models import (
    PredictionRequest,
    PredictionResponse,
    PredictionHistoryResponse,
    PredictionHistoryItem,
    ErrorResponse,
    LocationInfo,
    UsedMeasurements
)
from domain.use_cases.predict_aqi_use_case import PredictAQIUseCase
from domain.use_cases.get_prediction_history_use_case import GetPredictionHistoryUseCase
from domain.models.air_quality import StoredPrediction
from app.dependencies import get_predict_aqi_use_case, get_prediction_history_use_case
from infrastructure.logging.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/predictions", 
    tags=["Predictions"], 
    responses={404: {"description": "Not found"}} 
)

@router.post(
    "/",
    response_model=PredictionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input data"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Predict Air Quality Index (AQI)",
    description="""
    Predicts the Air Quality Index based on provided pollutant data and location.
    - You can provide specific pollutant values (pm25, pm10, o3, no2, so2, co).
    - If `auto_fill_pollutants` is true and some pollutant values are missing,
      the API will attempt to fetch them from an external service (e.g., Google Air Quality API).
    - The `date` for prediction must be in YYYY-MM-DD format.
    """,
    tags=["Predictions"],
)
async def predict_aqi(
    request: PredictionRequest,
    use_case: PredictAQIUseCase = Depends(get_predict_aqi_use_case),
):
    logger.info(f"Received prediction request for date: {request.date}, location: {request.loc}, {request.country}, auto_fill: {request.auto_fill_pollutants}")
    try:
        pollutants_data = {
            "pm25": request.pm25,
            "pm10": request.pm10,
            "o3": request.o3,
            "no2": request.no2,
            "so2": request.so2,
            "co": request.co,
        }
        location_data = {"country": request.country, "loc": request.loc} 

        
        prediction_domain: StoredPrediction = await use_case.execute(
            prediction_date_str=request.date,
            pollutants_data=pollutants_data,
            location_data=location_data,
            auto_fill_missing=request.auto_fill_pollutants,
        )

        
        api_location_info = None
        if prediction_domain.location_info:
            api_location_info = LocationInfo(**prediction_domain.location_info.model_dump())

        api_used_measurements = None
        if prediction_domain.used_measurements:
            api_used_measurements = UsedMeasurements(**prediction_domain.used_measurements.model_dump())

        
        
        api_input_data_dict = prediction_domain.input_data.model_dump()


        response = PredictionResponse(
            prediction_id=prediction_domain.id,
            date=prediction_domain.date, 
            predicted_category=prediction_domain.predicted_category,
            probabilities=prediction_domain.probabilities,
            summary=prediction_domain.summary,
            timestamp=prediction_domain.timestamp, 
            location_info=api_location_info,
            used_measurements=api_used_measurements,
            input_data=api_input_data_dict
        )
        logger.info(f"Prediction successful for ID: {response.prediction_id}, Category: {response.predicted_category}")
        return response

    except ValueError as ve:
        logger.warning(f"Validation error in prediction request: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        logger.error(f"Runtime error during prediction: {re}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        logger.error(f"Unexpected error during prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during prediction.")


@router.get(
    "/history",
    response_model=PredictionHistoryResponse,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
    summary="Get AQI Prediction History",
    description="Retrieves a paginated list of past AQI predictions. Can be filtered by date.",
    tags=["Predictions"],
)
async def get_history(
    limit: int = Query(10, ge=1, le=100, description="Number of predictions to return."),
    skip: int = Query(0, ge=0, description="Number of predictions to skip for pagination."),
    date_filter: Optional[str] = Query(None, alias="date", description="Filter predictions by date (YYYY-MM-DD)."),
    use_case: GetPredictionHistoryUseCase = Depends(get_prediction_history_use_case),
):
    logger.info(f"Received request for prediction history: limit={limit}, skip={skip}, date_filter='{date_filter}'")
    try:
        
        predictions_domain, total_count = await use_case.execute(
            limit=limit, skip=skip, filter_date_str=date_filter
        )

        history_items: List[PredictionHistoryItem] = []
        for pred_domain in predictions_domain:
            
            
            api_location_info = None
            if pred_domain.location_info: 
                api_location_info = LocationInfo(**pred_domain.location_info.model_dump())

            
            api_used_measurements = None
            if pred_domain.used_measurements:
                api_used_measurements = UsedMeasurements(**pred_domain.used_measurements.model_dump())
            
            
            
            api_input_data_dict = None
            if pred_domain.input_data: 
                api_input_data_dict = pred_domain.input_data.model_dump()


            history_item = PredictionHistoryItem(
                prediction_id=pred_domain.id,
                date=pred_domain.date, 
                predicted_category=pred_domain.predicted_category,
                probabilities=pred_domain.probabilities,
                summary=pred_domain.summary,
                timestamp=pred_domain.timestamp, 
                location_info=api_location_info,
                used_measurements=api_used_measurements,
                input_data=api_input_data_dict
            )
            history_items.append(history_item)

        logger.info(f"Returning {len(history_items)} history items, total count: {total_count}")
        return PredictionHistoryResponse(
            predictions=history_items, total_count=total_count, limit=limit, skip=skip
        )
    except ValueError as ve: 
        logger.error(f"Value error in get_history: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching prediction history: {e}", exc_info=True)
        
        
        
        raise HTTPException(status_code=500, detail="Failed to retrieve prediction history.")

