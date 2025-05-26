from typing import Optional, List, Tuple, Any, Dict
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.database import Database
from pymongo.results import InsertOneResult
from pymongo import ReturnDocument, DESCENDING, ASCENDING
from domain.repositories.current_conditions_repository import CurrentConditionsRepository
from domain.models.air_quality import (
    StoredCurrentConditions, 
    ExternalAirQualityData, 
    LocationContext, 
    AQIPredictionResult, 
    PollutantConcentrations,
    ExternalAQIIndexInfo,
    HeatmapDataPoint
)
from infrastructure.database.mongo_client import get_database, convert_to_serializable
from infrastructure.logging.logger import get_logger
from pydantic_core import ValidationError


logger = get_logger(__name__)

class MongoCurrentConditionsRepository(CurrentConditionsRepository):
    """
    MongoDB implementation of the CurrentConditionsRepository interface.
    """
    def __init__(self):
        self._db: Database = get_database()
        self._current_conditions_collection = self._db["current_conditions"]

    def _map_doc_to_stored_conditions(self, doc: Optional[Dict[str, Any]]) -> Optional[StoredCurrentConditions]:
        if not doc:
            return None
        doc_id = doc.get("_id", "Unknown ID")
        try:
            location_data = doc.get("location")
            if not location_data or not isinstance(location_data, dict):
                logger.warning(f"Document ID {doc_id}: 'location' field is missing or not a dict for StoredCurrentConditions. Skipping.")
                return None
            location = LocationContext.model_validate(location_data)

            pollutants_summary_data = doc.get("pollutants_summary")
            if not pollutants_summary_data or not isinstance(pollutants_summary_data, dict):
                logger.warning(f"Document ID {doc_id}: 'pollutants_summary' field is missing or not a dict for StoredCurrentConditions. Skipping.")
                return None
            pollutants_summary = PollutantConcentrations.model_validate(pollutants_summary_data)
            
            external_data_details_raw = doc.get("external_data_details")
            external_data_details = ExternalAirQualityData.model_validate(external_data_details_raw) if external_data_details_raw and isinstance(external_data_details_raw, dict) else None
            
            prediction_result_raw = doc.get("prediction_result")
            prediction_result = AQIPredictionResult.model_validate(prediction_result_raw) if prediction_result_raw and isinstance(prediction_result_raw, dict) else None

            return StoredCurrentConditions(
                id=str(doc_id),
                fetch_timestamp=doc.get("fetch_timestamp"),
                location=location,
                pollutants_summary=pollutants_summary,
                external_data_details=external_data_details,
                prediction_result=prediction_result
            )
        except ValidationError as ve:
            logger.error(f"Pydantic validation error mapping document ID {doc_id} to StoredCurrentConditions: {ve}", exc_info=False)
            return None
        except Exception as e:
            logger.error(f"Unexpected error mapping document ID {doc_id} to StoredCurrentConditions: {e}", exc_info=True)
            return None

    async def save_current_conditions(
        self, 
        external_aq_data: ExternalAirQualityData,
        prediction_result: Optional[AQIPredictionResult] = None
    ) -> str:
        logger.info(f"Saving current conditions for location: {external_aq_data.location.city}, {external_aq_data.location.country}")
        
        pollutants_summary_dict = {}
        for p_detail in external_aq_data.pollutants:
            if hasattr(PollutantConcentrations, p_detail.code) and p_detail.concentration and p_detail.concentration.value is not None:
                 pollutants_summary_dict[p_detail.code] = p_detail.concentration.value
        
        pollutants_summary_obj = PollutantConcentrations(**pollutants_summary_dict)

        document_to_insert = {
            "fetch_timestamp": external_aq_data.fetch_timestamp, 
            "location": external_aq_data.location.model_dump(mode='json'),
            "pollutants_summary": pollutants_summary_obj.model_dump(mode='json'),
            "external_data_details": external_aq_data.model_dump(mode='json'),
            "prediction_result": prediction_result.model_dump(mode='json') if prediction_result else None,
            "coordinates": { 
                 "type": "Point",
                 "coordinates": [external_aq_data.location.longitude, external_aq_data.location.latitude]
            } if external_aq_data.location.longitude is not None and external_aq_data.location.latitude is not None else None
        }
        
        try:
            result: InsertOneResult = self._current_conditions_collection.insert_one(document_to_insert)
            if not result.inserted_id:
                logger.error("Failed to insert current conditions into MongoDB, no ID returned.")
                raise ConnectionError("Failed to save current conditions, no inserted ID.")
            
            record_id = str(result.inserted_id)
            logger.info(f"Current conditions saved successfully with ID: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"Error saving current conditions to MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error while saving current conditions: {e}")

    async def get_latest_conditions_by_location(
        self, 
        latitude: float, 
        longitude: float
    ) -> Optional[StoredCurrentConditions]:
        logger.info(f"Fetching latest conditions for location: lat={latitude}, lon={longitude}")
        query = {
            "location.latitude": latitude,
            "location.longitude": longitude
        }
        try:
            document = self._current_conditions_collection.find_one(
                query, 
                sort=[("fetch_timestamp", DESCENDING)]
            )
            return self._map_doc_to_stored_conditions(document)
        except Exception as e:
            logger.error(f"Error fetching latest conditions for lat={latitude}, lon={longitude}: {e}", exc_info=True)
            raise ConnectionError(f"Database error fetching latest conditions: {e}")

    async def get_all_current_conditions_history(
        self, 
        limit: int = 10, 
        skip: int = 0
    ) -> Tuple[List[StoredCurrentConditions], int]:
        logger.info(f"Fetching all current conditions history, limit: {limit}, skip: {skip}")
        try:
            total_count = self._current_conditions_collection.count_documents({})
            cursor = self._current_conditions_collection.find({}).sort("fetch_timestamp", DESCENDING).skip(skip).limit(limit)
            
            conditions_list = [self._map_doc_to_stored_conditions(doc) for doc in cursor]
            valid_conditions_list = [c for c in conditions_list if c is not None]
            
            logger.info(f"Retrieved {len(valid_conditions_list)} current conditions records, total available: {total_count}")
            return valid_conditions_list, total_count
        except Exception as e:
            logger.error(f"Error fetching all current conditions history from MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error fetching current conditions history: {e}")

    async def get_all_current_conditions_for_map(self) -> List[HeatmapDataPoint]:
            logger.info("Fetching all current conditions for map data.")
            heatmap_data_points = []
            try:
                cursor = self._current_conditions_collection.find({})

                for doc in cursor:
                    try:
                        location_data = doc.get("location")
                        external_data_details_raw = doc.get("external_data_details")

                        if not location_data or not isinstance(location_data, dict) or \
                        not external_data_details_raw or not isinstance(external_data_details_raw, dict):
                            logger.debug(f"Document ID {str(doc.get('_id'))} missing location or external_data_details. Skipping for heatmap.")
                            continue

                        latitude = location_data.get("latitude")
                        longitude = location_data.get("longitude")

                        if latitude is None or longitude is None:
                            logger.debug(f"Document ID {str(doc.get('_id'))} missing latitude or longitude. Skipping for heatmap.")
                            continue
                        
                        aqi_value = None
                        aqi_indexes_raw = external_data_details_raw.get("aqi_indexes")
                        
                        if aqi_indexes_raw and isinstance(aqi_indexes_raw, list) and len(aqi_indexes_raw) > 0:
                            universal_aqi = next((idx for idx in aqi_indexes_raw if isinstance(idx, dict) and idx.get("display_name", "").lower() == "universal aqi"), None)
                            if universal_aqi and universal_aqi.get("aqi") is not None:
                                aqi_value = float(universal_aqi.get("aqi"))
                            elif aqi_indexes_raw[0].get("aqi") is not None:
                                aqi_value = float(aqi_indexes_raw[0].get("aqi"))
                            elif aqi_indexes_raw[0].get("aqi_value") is not None:
                                aqi_value = float(aqi_indexes_raw[0].get("aqi_value"))


                        if aqi_value is None:
                            logger.debug(f"Document ID {str(doc.get('_id'))} could not determine AQI value from aqi_indexes. Skipping for heatmap.")
                            continue

                        heatmap_data_points.append(
                            HeatmapDataPoint(
                                latitude=float(latitude),
                                longitude=float(longitude),
                                aqi=aqi_value
                            )
                        )
                    except (ValueError, TypeError) as val_err: 
                        logger.warning(f"Error processing document ID {str(doc.get('_id'))} for heatmap (ValueError/TypeError): {val_err}", exc_info=False)
                    except Exception as e:
                        logger.warning(f"Unexpected error processing document ID {str(doc.get('_id'))} for heatmap: {e}", exc_info=False)
                
                logger.info(f"Retrieved {len(heatmap_data_points)} data points for current conditions map.")
                return heatmap_data_points
            except Exception as e:
                logger.error(f"Error fetching current conditions for map from MongoDB: {e}", exc_info=True)
                raise ConnectionError(f"Database error fetching current conditions for map: {e}")
