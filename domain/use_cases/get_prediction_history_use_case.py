from typing import List, Tuple, Optional
from datetime import date, datetime

from domain.models.air_quality import StoredPrediction
from domain.repositories.prediction_repository import PredictionRepository
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

class GetPredictionHistoryUseCase:
    """
    Use case for retrieving historical AQI predictions.
    """
    def __init__(self, prediction_repository: PredictionRepository):
        self.prediction_repository = prediction_repository

    async def execute(
        self,
        limit: int = 10,
        skip: int = 0,
        filter_date_str: Optional[str] = None
    ) -> Tuple[List[StoredPrediction], int]: 
        logger.info(f"Executing GetPredictionHistoryUseCase: limit={limit}, skip={skip}, date_filter='{filter_date_str}'")

        parsed_filter_date: Optional[date] = None
        if filter_date_str:
            try:
                parsed_filter_date = datetime.strptime(filter_date_str, "%Y-%m-%d").date()
            except ValueError:
                logger.error(f"Invalid date format for filter: {filter_date_str}")
                raise ValueError("Invalid date format for filter. Must be YYYY-MM-DD.")

        if parsed_filter_date:
            predictions, total_count_for_date = await self.prediction_repository.get_predictions_by_date(
                prediction_date=parsed_filter_date,
                limit=limit,
                skip=skip
            )
            logger.info(f"Retrieved {len(predictions)} predictions for date {parsed_filter_date} (total for date: {total_count_for_date}).")
            return predictions, total_count_for_date
        else:
            predictions, total_count = await self.prediction_repository.get_all_predictions(limit=limit, skip=skip)
            logger.info(f"Retrieved {len(predictions)} predictions (total available: {total_count}).")
            return predictions, total_count