import pandas as pd
import numpy as np
import pickle
from sklearn.preprocessing import LabelEncoder

def safe_label_transform(series, label_encoder):
    mapping = dict(zip(label_encoder.classes_, label_encoder.transform(label_encoder.classes_)))
    return series.map(mapping).fillna(-1).astype(int)

def base_feature_engineering(df, verbose=True, 
                             le_country=None, le_loc=None, le_cat=None, 
                             fit_encoder=True):
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    pollutant_cols = ['pm25', 'pm10', 'o3', 'no2', 'so2', 'co']
    for col in pollutant_cols:
        lower = df[col].quantile(0.01)
        upper = df[col].quantile(0.99)
        df[col] = df[col].clip(lower, upper)
    df['dayofweek'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['dayofweek'].isin([5,6]).astype(int)
    df['total_pollutants'] = df[pollutant_cols].sum(axis=1)
    df['pm25_pm10_ratio'] = np.where(df['pm10'] != 0, df['pm25'] / df['pm10'], 0)

    if fit_encoder or le_country is None:
        le_country = LabelEncoder().fit(df['country'])
    df['country_encoded'] = safe_label_transform(df['country'], le_country)

    if fit_encoder or le_loc is None:
        le_loc = LabelEncoder().fit(df['loc'])
    df['loc_encoded'] = safe_label_transform(df['loc'], le_loc)

    if fit_encoder or le_cat is None:
        le_cat = LabelEncoder().fit(df['aqi_category'])
    df['aqi_cat_encoded'] = safe_label_transform(df['aqi_category'], le_cat)

    df['target'] = df['aqi_cat_encoded']

    return df, le_country, le_loc, le_cat

def prepare_for_tree_models(df_fe):
    cols_to_use = [
        'pm25', 'pm10', 'o3', 'no2', 'so2', 'co',
        'dayofweek', 'is_weekend',
        'total_pollutants', 'pm25_pm10_ratio',
        'country_encoded', 'loc_encoded'
    ]
    return df_fe[cols_to_use]

# Load model dan encoder (pastikan path benar)
with open('xgboost_final_model.pkl', 'rb') as f:
    best_xgb = pickle.load(f)

with open('le_country.pkl', 'rb') as f:
    le_country = pickle.load(f)

with open('le_loc.pkl', 'rb') as f:
    le_loc = pickle.load(f)

with open('le_cat.pkl', 'rb') as f:
    le_cat = pickle.load(f)

def predict_aqi_category(new_data: pd.DataFrame):
    df_fe, _, _, _ = base_feature_engineering(
        new_data,
        verbose=False,
        le_country=le_country,
        le_loc=le_loc,
        le_cat=le_cat,
        fit_encoder=False
    )
    X_infer = prepare_for_tree_models(df_fe)
    pred_encoded = best_xgb.predict(X_infer)[0]
    pred_label = le_cat.inverse_transform([pred_encoded])[0]
    pred_proba = best_xgb.predict_proba(X_infer)[0]

    summary = {
        "Good": "✅ Good : Kualitas udara sangat baik, aman untuk semua orang.",
        "Moderate": "ℹ️ Moderate: Kualitas udara cukup baik, namun mungkin berdampak bagi sebagian kecil kelompok sensitif.",
        "Unhealthy for Sensitive Groups": "⚠️ Unhealthy for Sensitive Groups: Orang dengan kondisi pernapasan, anak-anak, dan lansia sebaiknya mengurangi aktivitas luar ruangan.",
        "Unhealthy": "❗Unhealthy : Kualitas udara tidak sehat, semua orang bisa terpengaruh. Pertimbangkan memakai masker atau tetap di dalam ruangan.",
        "Very Unhealthy": "🚨 Very Unhealthy: Kondisi udara sangat buruk. Hindari aktivitas luar ruangan sebisa mungkin.",
        "Hazardous": "☠️ Hazardous : Bahaya serius bagi kesehatan. Semua orang sebaiknya tetap di dalam ruangan dan tutup ventilasi."
    }

    return {
        "predicted_category": pred_label,
        "probabilities": dict(zip(le_cat.classes_, pred_proba)),
        "summary": summary.get(pred_label, "ℹ️ Tidak ada informasi tambahan.")
    }

if __name__ == "__main__":
    # Contoh testing langsung
    new_data = pd.DataFrame([{
        'date': '2025-05-21',
        'pm25': 60,
        'pm10': 90,
        'o3': 35,
        'no2': 45,
        'so2': 15,
        'co': 0.7,
        'country': 'Indonesia',
        'loc': 'Jakarta',
        'aqi_category': 'Moderate'  # dummy untuk lewat preprocessing
    }])

    hasil = predict_aqi_category(new_data)
    print("🎯 Predicted AQI Category:", hasil["predicted_category"])
    print("📊 Probabilities:")
    for label, prob in hasil["probabilities"].items():
        print(f"{label:<35}: {prob:.4f}")
    print("\n📝 Hasil Akhir:")
    print(hasil["summary"])
