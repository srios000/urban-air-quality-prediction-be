from pydantic import BaseModel, Field, field_validator, BeforeValidator, model_validator
from typing import Optional, Dict, List, Any
from typing_extensions import Annotated
from datetime import datetime, date
from bson import ObjectId

def object_id_to_str(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        return v
    if v is None:
        raise ValueError('ID field cannot be None if present')
    raise TypeError(f'ObjectId or string required for ID field, got {type(v)}')

class PollutantConcentrations(BaseModel):
    """
    Represents the concentration of various air pollutants.
    Units should be consistently managed or converted at the infrastructure/service layer.
    """
    pm25: Optional[float] = Field(None, description="PM2.5 concentration")
    pm10: Optional[float] = Field(None, description="PM10 concentration")
    o3: Optional[float] = Field(None, description="Ozone (O₃) concentration")
    no2: Optional[float] = Field(None, description="Nitrogen Dioxide (NO₂) concentration")
    so2: Optional[float] = Field(None, description="Sulfur Dioxide (SO₂) concentration")
    co: Optional[float] = Field(None, description="Carbon Monoxide (CO) concentration")

class LocationContext(BaseModel):
    """
    Geographical context for an air quality reading or prediction.
    """
    country: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    formatted_address: Optional[str] = None
    place_id: Optional[str] = None

class AQIPredictionInput(BaseModel):
    """
    Input data for making an AQI prediction.
    This is what the prediction use case primarily works with.
    """
    prediction_date: date
    pollutants: PollutantConcentrations
    location: LocationContext

    @field_validator('prediction_date', mode='before')
    @classmethod
    def parse_date_string(cls, value: Any) -> date:
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        raise TypeError("Invalid type for date, must be str, datetime.date or datetime.datetime")


class AQIPredictionResult(BaseModel):
    """
    Represents the outcome of an AQI prediction.
    """
    predicted_category: str
    probabilities: Dict[str, float]
    summary_message: str

class StoredPredictionInputData(BaseModel):
    """Corresponds to the 'input_data' field in the MongoDB document."""
    date: str = Field(..., example="2025-05-25", description="Date for the prediction in YYYY-MM-DD format.")
    pm25: Optional[float] = Field(None, example=60.0)
    pm10: Optional[float] = Field(None, example=90.0)
    o3: Optional[float] = Field(None, example=35.0)
    no2: Optional[float] = Field(None, example=45.0)
    so2: Optional[float] = Field(None, example=15.0)
    co: Optional[float] = Field(None, example=0.7)
    country: str = Field(..., example="中華民國")
    loc: str = Field(..., example="台北", description="Location/City name as provided in input.")
    auto_fill_pollutants: bool = Field(False, example=True)

class StoredPredictionLocationInfo(BaseModel):
    """Corresponds to the 'location_info' field in the MongoDB document."""
    latitude: Optional[float] = Field(None, example=25.0329636)
    longitude: Optional[float] = Field(None, example=121.5654268)
    formatted_address: Optional[str] = Field(None, example="Taipei City, Taiwan")
    display_name: Optional[str] = Field(None, example="Taipei City")
    place_id: Optional[str] = Field(None, example="ChIJi73bYWusQjQRgqQGXK260bw")
    source: Optional[str] = Field(None, example="places_api")

class StoredPredictionUsedMeasurements(BaseModel):
    """Corresponds to the 'used_measurements' field in the MongoDB document."""
    source: str = Field(..., example="Google Air Quality API")
    timestamp: datetime
    pollutants: Dict[str, float] = Field(..., example={"pm25": 16.43})

class PredictionToStore(BaseModel):
    """
    Represents all data for a single prediction event to be stored in MongoDB.
    This model matches the desired MongoDB document structure (excluding _id).
    """
    date: str = Field(..., example="2025-05-25", description="Top-level date string for the prediction.")
    input_data: StoredPredictionInputData
    predicted_category: str = Field(..., example="Moderate")
    probabilities: Dict[str, float] = Field(..., example={"Good": 0.2, "Moderate": 0.5})
    summary: str = Field(..., example="ℹ️ Moderate: Kualitas udara cukup baik...")
    location_info: Optional[StoredPredictionLocationInfo] = None
    used_measurements: Optional[StoredPredictionUsedMeasurements] = None
    timestamp: datetime

class StoredPrediction(PredictionToStore):
    """
    Represents a prediction as retrieved from the database, including its ID.
    Inherits all fields from PredictionToStore and adds the database 'id'.
    """
    id: Annotated[str, BeforeValidator(object_id_to_str)] = Field(
        ...,
        alias="_id",
        description="Unique ID for this prediction record from the database."
    )

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
    
class HeatmapDataPoint(BaseModel):
    latitude: float = Field(..., example=1.439308, description="Latitude of the data point.")
    longitude: float = Field(..., example=103.766012, description="Longitude of the data point.")
    aqi: float = Field(..., example=69.0, description="Air Quality Index (AQI) value.")

class StoredAQIPrediction(AQIPredictionResult):
    """
    Represents an AQI prediction as it is stored, including metadata.
    (This is the older model, ensure it's updated or removed if fully replaced by StoredPrediction)
    """
    id: str
    prediction_input: AQIPredictionInput
    prediction_timestamp: datetime
    external_data_source_info: Optional[Dict[str, Any]] = None


class ExternalPollutantConcentration(BaseModel):
    """Mirrors Google AQ API's concentration structure more accurately."""
    value: Optional[float] = None
    units: Optional[str] = None

class ExternalPollutantDetail(BaseModel):
    """
    Represents detailed pollutant information from an external source like Google AQ API.
    """
    code: str
    display_name: Optional[str] = Field(None, description="Display name of the pollutant, e.g., 'PM2.5'")
    full_name: Optional[str] = Field(None, description="Full name of the pollutant, e.g., 'Fine particulate matter'")
    concentration: Optional[ExternalPollutantConcentration] = Field(None, description="Concentration of the pollutant")
    additional_info: Optional[Dict[str, Any]] = Field(None)

    @model_validator(mode='before')
    @classmethod
    def adapt_pollutant_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            concentration_data = data.get('concentration')
            is_proper_concentration = isinstance(concentration_data, dict) or isinstance(concentration_data, ExternalPollutantConcentration)

            if not is_proper_concentration:
                value = data.get('value')
                units_val = data.get('units')
                if units_val is None:
                    units_val = data.get('unit')

                if value is not None:
                    data['concentration'] = {'value': value, 'units': units_val}
        return data

class ExternalAQIIndexInfo(BaseModel):
    name: str
    aqi_value: int
    category: str
    dominant_pollutant: Optional[str] = None

class ExternalAirQualityData(BaseModel):
    """
    Structured air quality data fetched from an external service.
    """
    fetch_timestamp: datetime
    location: LocationContext
    pollutants: List[ExternalPollutantDetail]
    aqi_indexes: List[ExternalAQIIndexInfo] = Field(default_factory=list)
    health_recommendations: Dict[str, str] = Field(default_factory=dict)
    raw_data: Optional[Dict[str, Any]] = None


class GeocodedLocation(BaseModel):
    """
    Represents a location after geocoding.
    """
    latitude: float
    longitude: float
    formatted_address: str
    country: Optional[str] = None
    city: Optional[str] = None
    place_id: Optional[str] = None
    source_api: Optional[str] = Field(None, description="e.g., 'google_places_api'")

class StoredCurrentConditions(BaseModel):
    """
    Represents current air quality conditions as stored in the database.
    """
    id: str
    fetch_timestamp: datetime
    location: LocationContext
    pollutants_summary: PollutantConcentrations
    external_data_details: Optional[ExternalAirQualityData] = None
    prediction_result: Optional[AQIPredictionResult] = None