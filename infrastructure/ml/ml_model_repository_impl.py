import pandas as pd
from typing import Optional
from domain.repositories.ml_model_repository import MLModelRepository
from domain.models.air_quality import AQIPredictionResult
from infrastructure.ml.model_operations import _model_resources, predict_aqi_category, load_ml_resources as load_ops_resources
from infrastructure.logging.logger import get_logger
logger = get_logger(__name__)
class ConcreteMLModelRepository(MLModelRepository):
    """
    Concrete implementation of MLModelRepository.
    This class wraps the model_operations module.
    """
    def __init__(self):
        pass

    async def load_resources(self) -> None:
        """
        Ensures that ML resources are loaded via the model_operations module.
        This method is idempotent.
        """
        if not _model_resources._loaded:
            logger.info("MLModelRepository: Triggering load of ML resources.")
            try:
                await load_ops_resources() 
                if _model_resources._loaded:
                    logger.info("MLModelRepository: ML resources loaded successfully.")
                else:
                    logger.error("MLModelRepository: ML resources failed to load after explicit call.")
                    raise RuntimeError("Failed to load ML resources via model_operations.")
            except Exception as e:
                logger.error(f"MLModelRepository: Error during ML resource loading: {e}", exc_info=True)
                raise 
        else:
            logger.info("MLModelRepository: ML resources were already loaded.")

    def are_resources_loaded(self) -> bool:
        """Checks if the ML resources are loaded."""
        return _model_resources._loaded

    async def get_aqi_prediction(self, input_features_df: pd.DataFrame) -> AQIPredictionResult:
        """
        Gets AQI prediction using the loaded model and feature engineering.
        """
        logger.info(f"MLModelRepository: Requesting AQI prediction for {len(input_features_df)} record(s).")
        if not self.are_resources_loaded():
            logger.error("MLModelRepository: ML resources not loaded. Attempting to load now.")
            await self.load_resources() 
            if not self.are_resources_loaded():
                 raise RuntimeError("ML resources are not loaded, and auto-load failed. Prediction aborted.")

        try:
            prediction_result: AQIPredictionResult = predict_aqi_category(input_features_df)
            logger.info("MLModelRepository: AQI prediction successful.")
            return prediction_result
        except RuntimeError as e: 
            logger.error(f"MLModelRepository: Runtime error during prediction: {e}", exc_info=True)
            raise 
        except Exception as e:
            logger.error(f"MLModelRepository: Unexpected error during prediction: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected ML prediction error: {e}")