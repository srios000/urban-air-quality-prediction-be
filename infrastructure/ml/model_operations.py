import os
import pickle
import pandas as pd
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from core.config import get_settings
from infrastructure.logging.logger import get_logger
from infrastructure.ml.feature_engineering import base_feature_engineering, prepare_data_for_model
from domain.models.air_quality import AQIPredictionResult 

logger = get_logger(__name__)

class ModelResources:
    """
    A container for the loaded ML model and encoders.
    This helps manage these resources and ensures they are loaded only once.
    """
    def __init__(self):
        self.model: Optional[XGBClassifier] = None
        self.le_country: Optional[LabelEncoder] = None
        self.le_loc: Optional[LabelEncoder] = None
        self.le_cat: Optional[LabelEncoder] = None 
        self._loaded = False

    def load(self):
        if self._loaded:
            logger.info("Model and encoders already loaded.")
            return

        settings = get_settings()
        
        project_root = Path(__file__).parent.parent.parent.resolve() 
        model_store_path = project_root / settings.MODEL_STORE_PATH
        
        model_file = model_store_path / settings.MODEL_FILENAME
        le_country_file = model_store_path / settings.LE_COUNTRY_FILENAME
        le_loc_file = model_store_path / settings.LE_LOC_FILENAME
        le_cat_file = model_store_path / settings.LE_CAT_FILENAME

        logger.info(f"Attempting to load ML model from: {model_file}")
        logger.info(f"Attempting to load LabelEncoder (Country) from: {le_country_file}")
        logger.info(f"Attempting to load LabelEncoder (Location) from: {le_loc_file}")
        logger.info(f"Attempting to load LabelEncoder (Category) from: {le_cat_file}")

        try:
            self.model = XGBClassifier()
            self.model.load_model(str(model_file))             
            with open(le_country_file, "rb") as f:
                self.le_country = pickle.load(f)
            
            with open(le_loc_file, "rb") as f:
                self.le_loc = pickle.load(f)
            
            with open(le_cat_file, "rb") as f:
                self.le_cat = pickle.load(f)
            
            self._loaded = True
            logger.info("ML Model and all encoders loaded successfully.")

        except FileNotFoundError as e:
            logger.error(f"Error loading model or encoders: {e}. One or more files not found. Ensure paths are correct and files exist.", exc_info=True)
            
            
            
            self._loaded = False 
            raise RuntimeError(f"Failed to load critical ML resources: {e}") 
        except Exception as e:
            logger.error(f"An unexpected error occurred during model loading: {e}", exc_info=True)
            self._loaded = False
            raise RuntimeError(f"Unexpected error loading ML resources: {e}")

_model_resources = ModelResources()

async def load_ml_resources(): 
    """Loads ML resources. Can be called at application startup."""
    if not _model_resources._loaded:
        logger.info("Initiating loading of ML resources...")
        try:
            _model_resources.load()
        except RuntimeError as e:
            logger.error(f"Fatal error during ML resource loading: {e}", exc_info=True)
            
            raise 
    else:
        logger.info("ML resources are already loaded.")

def predict_aqi_category(input_data_df: pd.DataFrame) -> AQIPredictionResult:
    """
    Predicts the air quality category based on the input DataFrame.
    The input DataFrame should contain raw features (date, pollutants, location).
    Feature engineering is performed internally.
    """
    if not _model_resources._loaded or not _model_resources.model or \
       not _model_resources.le_country or not _model_resources.le_loc or \
       not _model_resources.le_cat:
        logger.error("ML model or encoders are not loaded. Prediction cannot proceed.")
        
        raise RuntimeError("ML resources not available for prediction.")

    try:
        df_fe = base_feature_engineering(
            input_data_df,
            le_country=_model_resources.le_country,
            le_loc=_model_resources.le_loc,
            verbose=False 
        )
        
        X_infer = prepare_data_for_model(df_fe)
        logger.debug(f"Data for inference (X_infer shape: {X_infer.shape}):\n{X_infer.head().to_string()}")

        pred_encoded_array = _model_resources.model.predict(X_infer)
        pred_proba_array = _model_resources.model.predict_proba(X_infer)

        if not pred_encoded_array.size or not pred_proba_array.size:
            logger.error("Model prediction returned empty arrays.")
            raise ValueError("Model prediction failed to produce output.")
        
        pred_encoded = pred_encoded_array[0]
        pred_proba = pred_proba_array[0]
        
        predicted_category_label = _model_resources.le_cat.inverse_transform([pred_encoded])[0]
        
        probabilities: Dict[str, float] = {
            str(cat): float(prob) 
            for cat, prob in zip(_model_resources.le_cat.classes_, pred_proba)
        }
        
        summary_messages_map = {
            "Good": "✅ Good: Air quality is considered satisfactory, and air pollution poses little or no risk.",
            "Moderate": "ℹ️ Moderate: Air quality is acceptable; however, for some pollutants there may be a moderate health concern for a very small number of people who are unusually sensitive to air pollution.",
            "Unhealthy for Sensitive Groups": "⚠️ Unhealthy for Sensitive Groups: Members of sensitive groups may experience health effects. The general public is not likely to be affected.",
            "Unhealthy": "❗ Unhealthy: Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.",
            "Very Unhealthy": "🚨 Very Unhealthy: Health alert: everyone may experience more serious health effects.",
            "Hazardous": "☠️ Hazardous: Health warnings of emergency conditions. The entire population is more likely to be affected."
        }
        summary = summary_messages_map.get(str(predicted_category_label), "ℹ️ No specific summary available for this category.")
        return AQIPredictionResult(
            predicted_category=str(predicted_category_label),
            probabilities=probabilities,
            summary_message=summary
        )
    except Exception as e:
        logger.error(f"Error during AQI prediction pipeline: {e}", exc_info=True)
        
        raise RuntimeError(f"Prediction failed: {e}")