from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from datetime import date
from domain.models.air_quality import PredictionToStore, StoredPrediction, StoredAQIPrediction
from app.models import HeatmapDataPoint

class PredictionRepository(ABC):
    """
    Interface for storing and retrieving AQI predictions.
    """

    @abstractmethod
    async def save_prediction(self, prediction_data: PredictionToStore) -> str:
        """
        Saves an AQI prediction to the repository using the new structured format.

        Args:
            prediction_data: The complete prediction data to store.

        Returns:
            The ID of the saved prediction.
        """
        pass

    @abstractmethod
    async def get_prediction_by_id(self, prediction_id: str) -> Optional[StoredPrediction]:
        """
        Retrieves a specific prediction by its ID using the new structured format.

        Args:
            prediction_id: The ID of the prediction.

        Returns:
            The stored prediction if found, otherwise None.
        """
        pass

    @abstractmethod
    async def get_predictions_by_date(
        self, prediction_date: date, limit: int = 10, skip: int = 0
    ) -> Tuple[List[StoredPrediction], int]:
        """
        Retrieves predictions for a specific date, with pagination, using the new structured format.

        Args:
            prediction_date: The date to filter predictions by.
            limit: Maximum number of predictions to return.
            skip: Number of predictions to skip (for pagination).

        Returns:
            A tuple containing a list of stored predictions for that date and the total count for that date.
        """
        pass

    @abstractmethod
    async def get_all_predictions(
        self, 
        limit: int = 100, 
        skip: int = 0,
        sort_by: str = "timestamp",
        sort_order: int = -1
    ) -> Tuple[List[StoredAQIPrediction], int]:
        """
        Retrieves all AQI predictions, with pagination and sorting.

        Args:
            limit: The maximum number of records to return.
            skip: The number of records to skip (for pagination).
            sort_by: Field to sort by (e.g., "timestamp", "predicted_aqi_value").
            sort_order: 1 for ascending, -1 for descending.

        Returns:
            A tuple containing a list of AQIPrediction objects and the total count of records.
        
        Raises:
            ConnectionError: If there's an issue with the database connection.
        """
        pass

    @abstractmethod
    async def get_all_predictions_for_map(self) -> List[HeatmapDataPoint]:
        """
        Retrieves all predictions formatted as heatmap data points.

        Returns:
            A list of HeatmapDataPoint objects.
        
        Raises:
            ConnectionError: If there's an issue with the database connection.
        """
        pass