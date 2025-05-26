import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from typing import Tuple, Optional, Any
from datetime import datetime
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

DEFAULT_POLLUTANT_MEAN_VALUES = {
    'pm25': 25.0, 'pm10': 50.0, 'o3': 30.0, 
    'no2': 25.0, 'so2': 10.0, 'co': 0.5
}

def safe_label_transform(series: pd.Series, label_encoder: LabelEncoder) -> pd.Series:
    known_classes = list(label_encoder.classes_)
    transformed_series = series.apply(lambda x: label_encoder.transform([x])[0] if x in known_classes else -1)
    return transformed_series.astype(int)

def base_feature_engineering(
    df: pd.DataFrame,
    le_country: LabelEncoder,
    le_loc: LabelEncoder,
    verbose: bool = True 
) -> pd.DataFrame:
    df_processed = df.copy()
    
    if 'date' in df_processed.columns:
        try:
            if pd.api.types.is_string_dtype(df_processed['date']):
                df_processed['date'] = pd.to_datetime(df_processed['date'], errors='coerce')
            
            if df_processed['date'].isnull().any():
                logger.warning(f"NaN dates found, filling with current date for feature engineering.")
                df_processed['date'] = df_processed['date'].fillna(pd.Timestamp(datetime.now()))

            df_processed['dayofweek'] = df_processed['date'].dt.dayofweek
            df_processed['month'] = df_processed['date'].dt.month
            df_processed['is_weekend'] = df_processed['dayofweek'].isin([5, 6]).astype(int)
            df_processed['hour'] = df_processed['date'].dt.hour if hasattr(df_processed['date'].dt, 'hour') else 12
        except Exception as e:
            logger.error(f"Error processing date features: {e}. Using default values.", exc_info=True)
            df_processed['dayofweek'] = datetime.now().weekday()
            df_processed['month'] = datetime.now().month
            df_processed['is_weekend'] = (datetime.now().weekday() >= 5)
            df_processed['hour'] = 12

    pollutant_cols = ['pm25', 'pm10', 'o3', 'no2', 'so2', 'co']
    for col in pollutant_cols:
        if col in df_processed.columns:
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
            if df_processed[col].isnull().any():
                fill_value = DEFAULT_POLLUTANT_MEAN_VALUES.get(col, 0)
                if verbose:
                    logger.info(f"Filling {df_processed[col].isnull().sum()} missing values in '{col}' with {fill_value}.")
                df_processed[col] = df_processed[col].fillna(fill_value)
        else:
            fill_value = DEFAULT_POLLUTANT_MEAN_VALUES.get(col, 0)
            if verbose:
                logger.info(f"Column '{col}' not found, adding it with default value {fill_value}.")
            df_processed[col] = fill_value
        df_processed[col] = df_processed[col].astype(float)
        bounds = {
            'pm25': (0, 500), 'pm10': (0, 1000), 'o3': (0, 400),
            'no2': (0, 300), 'so2': (0, 200), 'co': (0, 50)
        }
        lower_bound, upper_bound = bounds.get(col, (None, None))
        if lower_bound is not None and upper_bound is not None:
            df_processed[col] = df_processed[col].clip(lower_bound, upper_bound)

    df_processed['total_pollutants'] = df_processed[pollutant_cols].sum(axis=1)
    df_processed['pm25_pm10_ratio'] = np.where(
        df_processed['pm10'] > 0, 
        df_processed['pm25'] / df_processed['pm10'], 
        0 
    )

    if 'country' in df_processed.columns and le_country:
        df_processed['country_encoded'] = safe_label_transform(df_processed['country'], le_country)
    else:
        logger.warning("Country column missing or encoder not provided. Setting 'country_encoded' to -1.")
        df_processed['country_encoded'] = -1
        
    if 'loc' in df_processed.columns and le_loc:
        df_processed['loc_encoded'] = safe_label_transform(df_processed['loc'], le_loc)
    else:
        logger.warning("Location (loc) column missing or encoder not provided. Setting 'loc_encoded' to -1.")
        df_processed['loc_encoded'] = -1
    
    if verbose:
        logger.info(f"Feature engineering completed. DataFrame columns: {df_processed.columns.tolist()}")
    return df_processed


def prepare_data_for_model(df_engineered: pd.DataFrame) -> pd.DataFrame:
    """
    Selects the final set of features required by the XGBoost model.
    This list MUST match the features the model was trained on.
    """
    cols_to_use = [
        'pm25', 'pm10', 'o3', 'no2', 'so2', 'co', 
        'dayofweek', 'is_weekend', 
        'total_pollutants', 'pm25_pm10_ratio', 
        'country_encoded', 'loc_encoded' 
    ]
    
    missing_cols = [col for col in cols_to_use if col not in df_engineered.columns]
    if missing_cols:
        logger.error(f"Critical features for model input missing after engineering: {missing_cols}. This indicates a problem.")
        for col in missing_cols:
            df_engineered[col] = 0 
            logger.warning(f"Filled missing critical model feature '{col}' with 0.")

    try:
        df_model_input = df_engineered[cols_to_use]
    except KeyError as e:
        logger.error(f"KeyError when selecting model features: {e}. Available columns: {df_engineered.columns.tolist()}", exc_info=True)
        raise ValueError(f"One or more required model features are missing: {e}")

    logger.info(f"Data prepared for model with columns: {df_model_input.columns.tolist()}")
    return df_model_input
