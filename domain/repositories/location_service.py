from abc import ABC, abstractmethod
from typing import Optional

from domain.models.air_quality import GeocodedLocation

class LocationService(ABC):
    """
    Interface for an external geocoding service.
    """

    @abstractmethod
    async def geocode_location(self, country: str, city: str) -> Optional[GeocodedLocation]:
        """
        Geocodes a location (country, city) to get coordinates and other details.

        Args:
            country: The country name.
            city: The city name.

        Returns:
            A GeocodedLocation object if successful, otherwise None.
        """
        pass

    @abstractmethod
    async def reverse_geocode_location(self, latitude: float, longitude: float) -> Optional[GeocodedLocation]:
        """
        Reverse geocodes coordinates (latitude, longitude) to get location details including city and country.

        Args:
            latitude: The latitude.
            longitude: The longitude.

        Returns:
            A GeocodedLocation object if successful, otherwise None.
        """
        pass