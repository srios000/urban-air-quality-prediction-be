from abc import ABC, abstractmethod
from typing import Optional

from domain.models.air_quality import ExternalAirQualityData

class AirQualityService(ABC):
    """
    Interface for an external service providing air quality data.
    """

    @abstractmethod
    async def get_current_air_quality(
        self, 
        latitude: float, 
        longitude: float, 
        language_code: str = "en"
    ) -> Optional[ExternalAirQualityData]:
        """
        Fetches current air quality data for the given coordinates.

        Args:
            latitude: Latitude of the location.
            longitude: Longitude of the location.
            language_code: Language code for localized results.

        Returns:
            An ExternalAirQualityData object if successful, otherwise None.
        """
        pass
