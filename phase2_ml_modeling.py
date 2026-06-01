import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.multioutput import MultiOutputRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
import joblib

def train_models():
    print("Phase 2: Machine Learning Modeling...")
    
    # 1. Load the synthetic dataset
    print("Loading dataset 'biofuel_synthetic_data.csv'...")
    try:
        data = pd.read_csv('biofuel_synthetic_data.csv')
    except FileNotFoundError:
        print("Error: Dataset not found. Please run phase1_data_generation.py first.")
        return

    # 2. Clean data, perform train-test split, and scale features
    features = [
        'Diesel_pct', 'Coconut_pct', 'Castor_pct', 'IPA_pct', 
        'Viscosity_cSt', 'Density_kgm3', 'Flash_Point_C', 'Calorific_Value_MJkg'
    ]

    ic_targets = ['IC_BTE_pct', 'IC_BSFC_gkWh', 'IC_NOx_ppm', 'IC_Smoke_Opacity_pct']
    jet_targets = ['Jet_Thrust_kN', 'Jet_SFC_gkNs', 'Jet_EGT_C']

    # Checking for any missing values (Cleaning step)
    data = data.dropna()

    X = data[features]
    y_ic = data[ic_targets]
    y_jet = data[jet_targets]

    # Train-test split (80% training, 20% testing)
    X_train, X_test, y_ic_train, y_ic_test, y_jet_train, y_jet_test = train_test_split(
        X, y_ic, y_jet, test_size=0.2, random_state=42
    )

    # Scale the features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Save the scaler for future use in API/Frontend
    joblib.dump(scaler, 'feature_scaler.joblib')
    print("Feature scaler saved as 'feature_scaler.joblib'.")

    # 3. Train Multi-Output Regression models
    print("\nTraining Model A (IC Engine Performance)...")
    # Using RandomForestRegressor which natively supports multi-output, but wrapping in MultiOutputRegressor
    # ensures explicit independent regressors per target or compatibility with other regressors like XGBoost.
    rf_ic = RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42)
    model_a = MultiOutputRegressor(rf_ic)
    model_a.fit(X_train_scaled, y_ic_train)

    print("Training Model B (Jet Engine Performance)...")
    rf_jet = RandomForestRegressor(n_estimators=150, max_depth=10, random_state=42)
    model_b = MultiOutputRegressor(rf_jet)
    model_b.fit(X_train_scaled, y_jet_train)

    # 4. Evaluation metrics and save models
    def evaluate_model(model, X_test, y_test, model_name):
        predictions = model.predict(X_test)
        rmse = np.sqrt(mean_squared_error(y_test, predictions, multioutput='raw_values'))
        r2 = r2_score(y_test, predictions, multioutput='raw_values')
        
        print(f"\n--- Evaluation Metrics for {model_name} ---")
        for i, target in enumerate(y_test.columns):
            print(f"Target: {target}")
            print(f"  RMSE: {rmse[i]:.4f}")
            print(f"  R² Score: {r2[i]:.4f}")

    evaluate_model(model_a, X_test_scaled, y_ic_test, "Model A (IC Engine)")
    evaluate_model(model_b, X_test_scaled, y_jet_test, "Model B (Jet Engine)")

    # Save models
    joblib.dump(model_a, 'model_ic_engine.joblib')
    joblib.dump(model_b, 'model_jet_engine.joblib')
    print("\nModels successfully trained and saved as 'model_ic_engine.joblib' and 'model_jet_engine.joblib'.")

if __name__ == "__main__":
    train_models()
