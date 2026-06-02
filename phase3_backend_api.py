import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re
import os
import gzip

import json
from dotenv import load_dotenv
import urllib.request
import urllib.error

# Load environment variables
load_dotenv()

# Configure Gemini via REST API (lightweight, no grpc/protobuf deps)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    gemini_enabled = True
    print("Google Gemini AI agent enabled (REST API).")
else:
    gemini_enabled = False
    print("No valid Gemini API key found. Using fallback regex logic for chatbot.")


def call_gemini(prompt: str) -> str:
    """Call Gemini API using lightweight urllib (no google-genai dependency)."""
    if not gemini_enabled:
        return None

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None


app = FastAPI(
    title="Biofuel Optimization API",
    description="API to predict IC and Jet engine performance based on biofuel blend ratios.",
    version="1.0.0"
)

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Lightweight numpy-only inference engine ----------
# Replaces scikit-learn/joblib to stay under Vercel's 250 MB limit.

def _predict_tree(tree: dict, X: np.ndarray) -> np.ndarray:
    """Predict using a single exported decision tree. X shape: (n_samples, n_features)."""
    cl = tree["children_left"]
    cr = tree["children_right"]
    feat = tree["feature"]
    thresh = tree["threshold"]
    val = tree["value"]

    n_samples = X.shape[0]
    predictions = np.empty(n_samples)
    for i in range(n_samples):
        node = 0
        while cl[node] != -1:  # -1 = leaf
            if X[i, feat[node]] <= thresh[node]:
                node = cl[node]
            else:
                node = cr[node]
        predictions[i] = val[node]
    return predictions


def _predict_rf(forest_trees: list, X: np.ndarray) -> np.ndarray:
    """Predict using an exported RandomForest (list of trees). Returns mean."""
    preds = np.array([_predict_tree(t, X) for t in forest_trees])
    return preds.mean(axis=0)


def _predict_multi_output(model_data: list, X: np.ndarray) -> np.ndarray:
    """Predict for MultiOutput model (list of RandomForest exports)."""
    results = []
    for rf_trees in model_data:
        results.append(_predict_rf(rf_trees, X))
    return np.column_stack(results)


# 1. Load exported models from compressed JSON
MODELS_LOADED = False
scaler_mean = None
scaler_scale = None
ic_model_data = None
jet_model_data = None

try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, 'models_export.json.gz')
    with gzip.open(model_path, 'rt') as f:
        _data = json.load(f)

    scaler_mean = np.array(_data["scaler"]["mean"])
    scaler_scale = np.array(_data["scaler"]["scale"])
    ic_model_data = _data["ic_model"]
    jet_model_data = _data["jet_model"]
    del _data  # free memory
    MODELS_LOADED = True
    print("ML models loaded successfully (numpy-only inference).")
except Exception as e:
    print(f"Warning: Models not found: {e}. Please run phase2_ml_modeling.py and export models first.")

# Standard properties for physical property calculation
PROPERTIES = {
    'Diesel': {'Viscosity': 3.0, 'Density': 830, 'Flash_Point': 60, 'Calorific_Value': 43.0},
    'Coconut_Oil': {'Viscosity': 30.0, 'Density': 920, 'Flash_Point': 225, 'Calorific_Value': 37.0},
    'Castor_Oil': {'Viscosity': 250.0, 'Density': 960, 'Flash_Point': 260, 'Calorific_Value': 39.0},
    'IPA': {'Viscosity': 2.0, 'Density': 786, 'Flash_Point': 12, 'Calorific_Value': 30.0}
}

# 2. Define Request Schemas
class BlendInput(BaseModel):
    Diesel_pct: float
    Coconut_pct: float
    Castor_pct: float
    IPA_pct: float

class ChatQuery(BaseModel):
    query: str

def calculate_features(blend: BlendInput):
    """Helper function to calculate physical properties from blend ratios."""
    total = blend.Diesel_pct + blend.Coconut_pct + blend.Castor_pct + blend.IPA_pct
    if not (99.0 <= total <= 101.0):
        raise ValueError(f"Blend percentages must sum to 100. Current sum: {total}")
        
    d = blend.Diesel_pct / 100
    co = blend.Coconut_pct / 100
    ca = blend.Castor_pct / 100
    i = blend.IPA_pct / 100

    # Calculate physical properties using mixing rules
    viscosity = np.exp(
        d * np.log(PROPERTIES['Diesel']['Viscosity']) +
        co * np.log(PROPERTIES['Coconut_Oil']['Viscosity']) +
        ca * np.log(PROPERTIES['Castor_Oil']['Viscosity']) +
        i * np.log(PROPERTIES['IPA']['Viscosity'])
    )
    
    density = (
        d * PROPERTIES['Diesel']['Density'] +
        co * PROPERTIES['Coconut_Oil']['Density'] +
        ca * PROPERTIES['Castor_Oil']['Density'] +
        i * PROPERTIES['IPA']['Density']
    )
    
    linear_fp = (
        d * PROPERTIES['Diesel']['Flash_Point'] +
        co * PROPERTIES['Coconut_Oil']['Flash_Point'] +
        ca * PROPERTIES['Castor_Oil']['Flash_Point'] +
        i * PROPERTIES['IPA']['Flash_Point']
    )
    flash_point = max(PROPERTIES['IPA']['Flash_Point'], linear_fp - (2.5 * blend.IPA_pct))
    
    calorific_value = (
        d * PROPERTIES['Diesel']['Calorific_Value'] +
        co * PROPERTIES['Coconut_Oil']['Calorific_Value'] +
        ca * PROPERTIES['Castor_Oil']['Calorific_Value'] +
        i * PROPERTIES['IPA']['Calorific_Value']
    )
    
    return [blend.Diesel_pct, blend.Coconut_pct, blend.Castor_pct, blend.IPA_pct, 
            viscosity, density, flash_point, calorific_value]

# 3. Main Prediction Endpoint
@app.post("/api/predict")
def predict_performance(blend: BlendInput):
    """
    Accepts blend percentages, calculates resulting physical properties, 
    and predicts IC and Jet Engine performance metrics.
    """
    if not MODELS_LOADED:
        raise HTTPException(status_code=503, detail="ML models are not loaded. Please ensure model files exist.")
    
    try:
        feature_list = calculate_features(blend)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Scale features using exported scaler parameters
    features_arr = np.array([feature_list])
    features_scaled = (features_arr - scaler_mean) / scaler_scale
    
    # Predict using numpy-only inference
    ic_preds = _predict_multi_output(ic_model_data, features_scaled)[0]
    jet_preds = _predict_multi_output(jet_model_data, features_scaled)[0]
    
    return {
        "input_blend": blend.model_dump(),
        "calculated_properties": {
            "Viscosity_cSt": round(float(feature_list[4]), 2),
            "Density_kgm3": round(float(feature_list[5]), 2),
            "Flash_Point_C": round(float(feature_list[6]), 2),
            "Calorific_Value_MJkg": round(float(feature_list[7]), 2)
        },
        "ic_engine_predictions": {
            "BTE_pct": round(float(ic_preds[0]), 2),
            "BSFC_gkWh": round(float(ic_preds[1]), 2),
            "NOx_ppm": round(float(ic_preds[2]), 2),
            "Smoke_Opacity_pct": round(float(ic_preds[3]), 2)
        },
        "jet_engine_predictions": {
            "Thrust_kN": round(float(jet_preds[0]), 2),
            "SFC_gkNs": round(float(jet_preds[1]), 2),
            "EGT_C": round(float(jet_preds[2]), 2)
        }
    }

# 4. Chatbot NLP Endpoint
@app.post("/api/chatbot")
def chatbot_interaction(query: ChatQuery):
    """
    Parses a natural language query using Gemini AI (if configured),
    or falls back to regex to extract percentages.
    """
    text = query.query
    
    # Default state
    blend = {"Diesel_pct": 100.0, "Coconut_pct": 0.0, "Castor_pct": 0.0, "IPA_pct": 0.0}
    found_custom = False
    
    if gemini_enabled:
        prompt = f"""
        Extract fuel blend percentages from the following user query.
        The valid fuel types are: Diesel, Coconut, Castor, IPA.
        If a percentage is specified for any of these, extract it.
        Return ONLY a JSON object with keys 'Diesel_pct', 'Coconut_pct', 'Castor_pct', 'IPA_pct'. 
        If some are missing, balance Diesel_pct so they sum to 100.
        If the query doesn't specify percentages but asks a general question, return a JSON object with a single key 'general_query': true.
        Query: "{text}"
        """
        try:
            res_text = call_gemini(prompt)
            if res_text:
                res_text = res_text.replace('```json', '').replace('```', '').strip()
                parsed = json.loads(res_text)
                
                if not parsed.get('general_query'):
                    blend["Diesel_pct"] = float(parsed.get('Diesel_pct', 100.0))
                    blend["Coconut_pct"] = float(parsed.get('Coconut_pct', 0.0))
                    blend["Castor_pct"] = float(parsed.get('Castor_pct', 0.0))
                    blend["IPA_pct"] = float(parsed.get('IPA_pct', 0.0))
                    
                    # Auto balance just in case
                    total_custom = blend["Coconut_pct"] + blend["Castor_pct"] + blend["IPA_pct"]
                    if blend["Diesel_pct"] == 100.0 and total_custom > 0 and total_custom <= 100:
                        blend["Diesel_pct"] = 100.0 - total_custom
                        
                    found_custom = True
        except Exception as e:
            print("Gemini Parsing Error:", e)
            # fallback to regex if LLM fails to return valid JSON
            pass
            
    if not found_custom:
        # Simple regex parsing fallback
        text_lower = text.lower()
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*%\s*(castor|coconut|ipa|diesel)', text_lower)
        if matches:
            total_custom = 0
            for val, f_type in matches:
                val_float = float(val)
                if f_type == 'castor': blend["Castor_pct"] = val_float
                elif f_type == 'coconut': blend["Coconut_pct"] = val_float
                elif f_type == 'ipa': blend["IPA_pct"] = val_float
                elif f_type == 'diesel': blend["Diesel_pct"] = val_float
                
                if f_type != 'diesel':
                    total_custom += val_float
            if blend["Diesel_pct"] == 100.0 and total_custom > 0 and total_custom <= 100:
                blend["Diesel_pct"] = 100.0 - total_custom
            found_custom = True

    if found_custom:
        try:
            b_input = BlendInput(**blend)
            results = predict_performance(b_input)
            
            # Ask Gemini to generate the response based on the ML results!
            if gemini_enabled:
                insight_prompt = f"""
                You are a Biofuel Optimization AI. 
                The user asked: "{text}"
                Our ML model predicts the following for this blend ({blend}):
                IC Engine BTE: {results['ic_engine_predictions']['BTE_pct']}%
                Jet Engine Thrust: {results['jet_engine_predictions']['Thrust_kN']} kN
                Viscosity: {results['calculated_properties']['Viscosity_cSt']} cSt
                Flash Point: {results['calculated_properties']['Flash_Point_C']} C
                Provide a short, concise, and helpful engineering response summarizing these results and any potential issues (e.g., high viscosity). Keep it to 2-3 sentences. Do not use markdown.
                """
                response_msg = call_gemini(insight_prompt)
                if not response_msg:
                    response_msg = (
                        f"Based on your query, I analyzed a blend of {blend['Diesel_pct']}% Diesel, "
                        f"{blend['Coconut_pct']}% Coconut, {blend['Castor_pct']}% Castor, and {blend['IPA_pct']}% IPA. "
                        f"This yields an estimated IC Engine Thermal Efficiency (BTE) of {results['ic_engine_predictions']['BTE_pct']}% "
                        f"and Jet Engine Thrust of {results['jet_engine_predictions']['Thrust_kN']} kN."
                    )
            else:
                response_msg = (
                    f"Based on your query, I analyzed a blend of {blend['Diesel_pct']}% Diesel, "
                    f"{blend['Coconut_pct']}% Coconut, {blend['Castor_pct']}% Castor, and {blend['IPA_pct']}% IPA. "
                    f"This yields an estimated IC Engine Thermal Efficiency (BTE) of {results['ic_engine_predictions']['BTE_pct']}% "
                    f"and Jet Engine Thrust of {results['jet_engine_predictions']['Thrust_kN']} kN."
                )
                if blend['Castor_pct'] > 15:
                    response_msg += " ⚠️ Note: High Castor oil content significantly increases viscosity."
            
            return {"response": response_msg, "parsed_blend": blend, "predictions": results}
        except Exception as e:
            return {"response": f"I understood the blend but encountered an error processing it: {str(e)}"}
            
    else:
        # General knowledge querying using Gemini
        if gemini_enabled:
            try:
                gen_prompt = f"You are a Biofuel Optimization AI. Answer this concisely: {text}"
                response_text = call_gemini(gen_prompt)
                if response_text:
                    return {"response": response_text.strip()}
            except:
                pass
                
        return {"response": "Hello! I am the Biofuel AI Assistant. You can ask me specific scenarios like 'What happens if I use 20% Castor oil and 5% IPA?'"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
