from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from domain.models.air_quality import GeocodedLocation

class LocationCacheRepository(ABC):
    """
    Interface for caching geocoded location data.
    """

    @abstractmethod
    async def get_geocoded_location(self, country: str, city: str) -> Optional[GeocodedLocation]:
        """
        Retrieves a geocoded location from the cache.

        Args:
            country: The country name.
            city: The city name.

        Returns:
            The cached GeocodedLocation if found and not expired, otherwise None.
        """
        pass

    @abstractmethod
    async def save_geocoded_location(
        self, 
        country: str, 
        city: str, 
        location_data: GeocodedLocation,
        ttl_seconds: Optional[int] = 86400
    ) -> None:
        """
        Saves a geocoded location to the cache with a Time-To-Live (TTL).

        Args:
            country: The country name.
            city: The city name.
            location_data: The GeocodedLocation object to cache.
            ttl_seconds: Time-to-live for the cache entry in seconds.
        """
        pass

    @abstractmethod
    async def get_reverse_geocoded_location(self, latitude: float, longitude: float) -> Optional[GeocodedLocation]:
        """
        Retrieves a reverse geocoded location from the cache.

        Args:
            latitude: The latitude.
            longitude: The longitude.

        Returns:
            The cached GeocodedLocation if found and not expired, otherwise None.
        """
        pass

    @abstractmethod
    async def save_reverse_geocoded_location(
        self, 
        latitude: float, 
        longitude: float, 
        location_data: GeocodedLocation,
        ttl_seconds: Optional[int] = 86400
    ) -> None:
        """
        Saves a reverse geocoded location to the cache with a Time-To-Live (TTL).

        Args:
            latitude: The latitude.
            longitude: The longitude.
            location_data: The GeocodedLocation object to cache.
            ttl_seconds: Time-to-live for the cache entry in seconds.
        """
        pass