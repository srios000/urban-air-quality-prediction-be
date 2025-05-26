from typing import List, Optional, Tuple, Any, Dict
from datetime import datetime, date, timezone
from bson import ObjectId

from pymongo.database import Database
from pymongo.results import InsertOneResult
from pymongo import DESCENDING

from domain.repositories.prediction_repository import PredictionRepository
from domain.models.air_quality import PredictionToStore, StoredPrediction, HeatmapDataPoint
from infrastructure.database.mongo_client import get_database
from infrastructure.logging.logger import get_logger
from pydantic_core import ValidationError

logger = get_logger(__name__)

class MongoPredictionRepository(PredictionRepository):
    """
    MongoDB implementation of the PredictionRepository interface.
    """
    def __init__(self):
        self._db: Database = get_database()
        self._predictions_collection = self._db["predictions"]

    async def save_prediction(self, prediction_data: PredictionToStore) -> str:
        logger.info(f"Saving prediction for date: {prediction_data.date} with new structure.")

        document_to_insert = prediction_data.model_dump(exclude_none=True)

        try:
            result: InsertOneResult = self._predictions_collection.insert_one(document_to_insert)
            if not result.inserted_id:
                logger.error("Failed to insert prediction into MongoDB (new structure), no ID returned.")
                raise ConnectionError("Failed to save prediction (new structure), no inserted ID.")

            prediction_id = str(result.inserted_id)
            logger.info(f"Prediction (new structure) saved successfully with ID: {prediction_id}")
            return prediction_id
        except Exception as e:
            logger.error(f"Error saving prediction (new structure) to MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error while saving prediction (new structure): {e}")

    def _map_doc_to_stored_prediction(self, doc: Optional[Dict[str, Any]]) -> Optional[StoredPrediction]:
        if not doc:
            return None

        doc_id_str = str(doc.get("_id", "Unknown ID"))

        try:
            stored_prediction = StoredPrediction.model_validate(doc)
            return stored_prediction
        except ValidationError as ve:
            
            logger.error(f"Pydantic validation error mapping document ID {doc_id_str} to StoredPrediction: {ve.errors()}", exc_info=False)
            return None
        except Exception as e:
            logger.error(f"Unexpected error mapping document ID {doc_id_str} to StoredPrediction: {e}", exc_info=True)
            return None

    async def get_prediction_by_id(self, prediction_id: str) -> Optional[StoredPrediction]:
        logger.info(f"Fetching prediction by ID (new structure): {prediction_id}")
        if not ObjectId.is_valid(prediction_id):
            logger.warning(f"Invalid ObjectId format for prediction_id: {prediction_id}")
            return None
        try:
            document = self._predictions_collection.find_one({"_id": ObjectId(prediction_id)})
            return self._map_doc_to_stored_prediction(document)
        except Exception as e:
            logger.error(f"Error fetching prediction by ID {prediction_id} (new structure) from MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error fetching prediction by ID (new structure): {e}")

    async def get_predictions_by_date(self, prediction_date: date, limit: int = 10, skip: int = 0) -> Tuple[List[StoredPrediction], int]:
        date_str = prediction_date.strftime("%Y-%m-%d")
        logger.info(f"Fetching predictions for date string: {date_str} (new structure), limit: {limit}, skip: {skip}")

        query = {"date": date_str}

        try:
            total_count_for_date = self._predictions_collection.count_documents(query)
            cursor = self._predictions_collection.find(query).sort("timestamp", DESCENDING).skip(skip).limit(limit)
            predictions = [self._map_doc_to_stored_prediction(doc) for doc in cursor]
            valid_predictions = [p for p in predictions if p is not None]
            logger.info(f"Retrieved {len(valid_predictions)} predictions for date {date_str}, total for date: {total_count_for_date}.")
            return valid_predictions, total_count_for_date
        except Exception as e:
            logger.error(f"Error fetching predictions by date {date_str} (new structure) from MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error fetching predictions by date (new structure): {e}")

    async def get_all_predictions(self, limit: int = 10, skip: int = 0) -> Tuple[List[StoredPrediction], int]:
        logger.info(f"Fetching all predictions (new structure), limit: {limit}, skip: {skip}")
        try:
            total_count = self._predictions_collection.count_documents({})
            cursor = self._predictions_collection.find({}).sort("timestamp", DESCENDING).skip(skip).limit(limit)

            predictions_list = []
            for doc in cursor:
                mapped_pred = self._map_doc_to_stored_prediction(doc)
                if mapped_pred:
                    predictions_list.append(mapped_pred)

            logger.info(f"Retrieved {len(predictions_list)} valid predictions (new structure), total available: {total_count}")
            return predictions_list, total_count
        except Exception as e:
            logger.error(f"Error fetching all predictions (new structure) from MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error fetching all predictions (new structure): {e}")
        
    async def get_all_predictions_for_map(self) -> List[HeatmapDataPoint]:
        logger.info("Fetching all predictions for map data.")
        heatmap_data_points = []
        try:
            cursor = self._predictions_collection.find({}) 

            for doc in cursor:
                try:
                    stored_pred = self._map_doc_to_stored_prediction(doc)

                    if stored_pred and stored_pred.location_info and \
                       stored_pred.location_info.latitude is not None and \
                       stored_pred.location_info.longitude is not None:
                        
                        aqi_value = 0.0
                        if stored_pred.predicted_category == "Good":
                            aqi_value = 25.0
                        elif stored_pred.predicted_category == "Moderate":
                            aqi_value = 75.0
                        elif stored_pred.predicted_category == "Unhealthy for Sensitive Groups":
                            aqi_value = 125.0
                        elif stored_pred.predicted_category == "Unhealthy":
                            aqi_value = 175.0
                        elif stored_pred.predicted_category == "Very Unhealthy":
                            aqi_value = 250.0
                        elif stored_pred.predicted_category == "Hazardous":
                            aqi_value = 350.0

                        heatmap_data_points.append(
                            HeatmapDataPoint(
                                latitude=stored_pred.location_info.latitude,
                                longitude=stored_pred.location_info.longitude,
                                aqi=aqi_value
                            )
                        )
                except Exception as e:
                    logger.warning(f"Could not process document ID {str(doc.get('_id'))} for heatmap: {e}", exc_info=False)

            logger.info(f"Retrieved {len(heatmap_data_points)} data points for map.")
            return heatmap_data_points
        except Exception as e:
            logger.error(f"Error fetching predictions for map from MongoDB: {e}", exc_info=True)
            raise ConnectionError(f"Database error fetching predictions for map: {e}")