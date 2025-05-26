from abc import ABC, abstractmethod
from typing import Optional, List, Tuple

from domain.models.air_quality import StoredCurrentConditions, ExternalAirQualityData, LocationContext, AQIPredictionResult
from app.models import HeatmapDataPoint

class CurrentConditionsRepository(ABC):
    """
    Interface for storing and retrieving current air quality conditions.
    """

    @abstractmethod
    async def save_current_conditions(
        self, 
        external_aq_data: ExternalAirQualityData,
        prediction_result: Optional[AQIPredictionResult] = None
    ) -> str:
        """
        Saves current air quality conditions data.

        Args:
            external_aq_data: The fetched external air quality data.
            prediction_result: Optional AQI prediction based on this data.
        
        Returns:
            The ID of the saved current conditions record.
        """
        pass

    @abstractmethod
    async def get_latest_conditions_by_location(
        self, 
        latitude: float, 
        longitude: float
    ) -> Optional[StoredCurrentConditions]:
        """
        Retrieves the most recent stored current conditions for a specific location.

        Args:
            latitude: Latitude of the location.
            longitude: Longitude of the location.

        Returns:
            The latest stored current conditions if found, otherwise None.
        """
        pass
    
    @abstractmethod
    async def get_all_current_conditions_history(
        self, 
        limit: int = 10, 
        skip: int = 0
    ) -> Tuple[List[StoredCurrentConditions], int]:
        """
        Retrieves history of all stored current conditions with pagination.

        Args:
            limit: Maximum number of records to return.
            skip: Number of records to skip.

        Returns:
            A tuple containing a list of stored current conditions and the total count.
        """
        pass

    @abstractmethod
    async def get_all_current_conditions_for_map(self) -> List[HeatmapDataPoint]:
        """
        Retrieves all current conditions formatted as heatmap data points.

        Returns:
            A list of HeatmapDataPoint objects.
        
        Raises:
            ConnectionError: If there's an issue with the database connection.
        """
        pass