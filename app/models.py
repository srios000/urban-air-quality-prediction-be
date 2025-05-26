from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, List, Any
from datetime import datetime

# --- Request Models ---

class PredictionRequest(BaseModel):
    """
    Request model for predicting air quality.
    """
    date: str = Field(..., example="2025-05-21", description="Date for the prediction in YYYY-MM-DD format.")
    pm25: Optional[float] = Field(None, example=60.0, description="Particulate Matter PM2.5 concentration (µg/m³).")
    pm10: Optional[float] = Field(None, example=90.0, description="Particulate Matter PM10 concentration (µg/m³).")
    o3: Optional[float] = Field(None, example=35.0, description="Ozone (O₃) concentration (µg/m³ or ppb.")
    no2: Optional[float] = Field(None, example=45.0, description="Nitrogen Dioxide (NO₂) concentration (µg/m³ or ppb).")
    so2: Optional[float] = Field(None, example=15.0, description="Sulfur Dioxide (SO₂) concentration (µg/m³ or ppb).")
    co: Optional[float] = Field(None, example=0.7, description="Carbon Monoxide (CO) concentration (mg/m³ or ppm).")
    country: str = Field(..., example="Indonesia", description="Country name for location context.")
    loc: str = Field(..., example="Jakarta", description="Location/City name for context.")
    auto_fill_pollutants: bool = Field(False, example=True, description="If true, attempts to fetch current pollutant data for the location using external APIs if specific pollutant values are not provided.")

    @validator('date')
    def validate_date_format(cls, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be in YYYY-MM-DD format")
        return value

class CurrentConditionsRequest(BaseModel):
    """
    Request model for fetching current air quality conditions by coordinates.
    """
    latitude: float = Field(..., example=37.419734, description="Latitude of the location.")
    longitude: float = Field(..., example=-122.0827784, description="Longitude of the location.")
    language_code: str = Field("en", example="en", description="Language code for localized health recommendations (e.g., 'en', 'id').")

class LocationRequest(BaseModel):
    """
    Request model for fetching air quality conditions by location name.
    """
    country: str = Field(..., example="Indonesia", description="Country name.")
    loc: str = Field(..., example="Jakarta", description="Location/City name.")
    language_code: str = Field("en", example="en", description="Language code for localized health recommendations.")


# --- Response Models ---

class LocationInfo(BaseModel):
    """
        Detailed information about a location.
    """
    model_config = ConfigDict(from_attributes=True)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    formatted_address: Optional[str] = None
    display_name: Optional[str] = None
    place_id: Optional[str] = None
    source: Optional[str] = Field(None, example="places_api", description="Source of the location data (e.g., 'places_api', 'cache').")
    country: Optional[str] = None 
    city: Optional[str] = None 

class UsedMeasurements(BaseModel):
    """
    Information about the measurements used, especially if auto-filled.
    """
    model_config = ConfigDict(from_attributes=True)
    source: str = Field(..., example="Google Air Quality API", description="Source of the pollutant data.")
    timestamp: datetime = Field(..., description="Timestamp of when the data was fetched.")
    pollutants: Dict[str, float] = Field(..., description="Pollutant values used for prediction.")

class PredictionResponse(BaseModel):
    """
    Response model for an air quality prediction.
    """
    model_config = ConfigDict(from_attributes=True)
    prediction_id: str = Field(..., description="Unique ID for this prediction record.")
    date: str = Field(..., description="Date for which the prediction was made.")
    predicted_category: str = Field(..., example="Moderate", description="Predicted air quality category.")
    probabilities: Dict[str, float] = Field(..., example={"Good": 0.2, "Moderate": 0.5, "Unhealthy": 0.3}, description="Probabilities for each AQI category.")
    summary: str = Field(..., example="ℹ️ Moderate: Kualitas udara cukup baik...", description="A human-readable summary and recommendation.")
    timestamp: datetime = Field(..., description="Timestamp of when the prediction was made.")
    location_info: Optional[LocationInfo] = Field(None, description="Geographical information if resolved.")
    used_measurements: Optional[UsedMeasurements] = Field(None, description="Details of pollutant measurements used, especially if auto-filled.")
    input_data: Optional[Dict[str, Any]] = Field(None, description="The input data used for the prediction, for traceability.")


class PollutantDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    display_name: str
    full_name: str
    concentration: Dict[str, Any]
    additional_info: Optional[Dict[str, Any]] = None

class AQIIndex(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    display_name: str
    aqi: int
    aqi_display: str
    color: Dict[str, float]
    category: str
    dominant_pollutant: Optional[str] = None

class CurrentConditionsData(BaseModel):
    """
    Detailed current air quality data from an external source like Google.
    """
    model_config = ConfigDict(from_attributes=True)
    indexes: List[AQIIndex] = Field(default_factory=list, description="List of AQI indexes (e.g., Universal AQI, local AQIs).")
    pollutants: List[PollutantDetail] = Field(default_factory=list, description="Detailed information for each pollutant.")
    health_recommendations: Dict[str, str] = Field(default_factory=dict, description="Health recommendations based on current conditions.")

class LocationAQIResponse(BaseModel):
    """
    Response model for air quality data fetched by location name or coordinates.
    """
    model_config = ConfigDict(from_attributes=True)
    timestamp: datetime = Field(..., description="Timestamp of when this data was processed/fetched.")
    location: LocationInfo = Field(..., description="Resolved location information.")
    current_pollutants_summary: Dict[str, float] = Field(..., description="Summary of key pollutant concentrations (pm25, pm10, o3, etc.).")
    external_aq_data: Optional[CurrentConditionsData] = Field(None, description="Raw or structured data from the external Air Quality API (e.g., Google).")
    prediction: Optional[PredictionResponse] = Field(None, description="An AQI prediction based on the fetched current conditions.")

class PredictionHistoryItem(PredictionResponse):
    """
    Represents a single prediction record in the history.
    Can extend PredictionResponse if history needs more/different fields.
    """
    model_config = ConfigDict(from_attributes=True)
    pass

class PredictionHistoryResponse(BaseModel):
    """
    Response model for a list of historical predictions.
    """
    model_config = ConfigDict(from_attributes=True)
    predictions: List[PredictionHistoryItem]
    total_count: int = Field(..., description="Total number of predictions available for the query (before pagination).")
    limit: int
    skip: int
    
class HeatmapDataPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    latitude: float = Field(..., example=1.439308, description="Latitude of the data point.")
    longitude: float = Field(..., example=103.766012, description="Longitude of the data point.")
    aqi: float = Field(..., example=69.0, description="Air Quality Index (AQI) value.")

class AllConditionsDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: List[HeatmapDataPoint] = Field(..., description="List of heatmap data points.")
    total_count: int = Field(..., example=100, description="Total number of valid data points returned.")

class ErrorResponse(BaseModel):
    """
    Standard error response model.
    """
    detail: str