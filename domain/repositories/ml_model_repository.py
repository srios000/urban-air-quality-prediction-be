from abc import ABC, abstractmethod
import pandas as pd
from domain.models.air_quality import AQIPredictionResult

class MLModelRepository(ABC):
    """
    Interface for interacting with the machine learning model for predictions.
    This abstracts the model loading, feature engineering, and prediction steps.
    """

    @abstractmethod
    async def get_aqi_prediction(self, input_features_df: pd.DataFrame) -> AQIPredictionResult:
        """
        Performs feature engineering and predicts AQI category.

        Args:
            input_features_df: A Pandas DataFrame containing the raw input features
                               (e.g., date, pollutant values, country, location).
                               The structure should be consistent with what the
                               feature engineering step expects.

        Returns:
            An AQIPredictionResult object containing the predicted category,
            probabilities, and a summary message.
        
        Raises:
            RuntimeError: If the model is not loaded or prediction fails.
        """
        pass

    @abstractmethod
    async def load_resources(self) -> None:
        """
        Ensures that all necessary ML resources (model, encoders) are loaded.
        This might be called at application startup.
        """
        pass

    @abstractmethod
    def are_resources_loaded(self) -> bool:
        """
        Checks if the ML resources are currently loaded.
        """
        pass

