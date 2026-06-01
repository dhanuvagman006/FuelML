import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import re
import os
import json
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    gemini_client = genai.Client(api_key=api_key)
    print("Google Gemini AI agent enabled.")
else:
    gemini_client = None
    print("No valid Gemini API key found. Using fallback regex logic for chatbot.")

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

# 1. Load trained models and feature scaler on startup
MODELS_LOADED = False
scaler = None
model_ic = None
model_jet = None

try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scaler = joblib.load(os.path.join(base_dir, 'feature_scaler.joblib'))
    model_ic = joblib.load(os.path.join(base_dir, 'model_ic_engine.joblib'))
    model_jet = joblib.load(os.path.join(base_dir, 'model_jet_engine.joblib'))
    MODELS_LOADED = True
    print("Machine Learning models and scaler loaded successfully.")
except Exception as e:
    print(f"Warning: Models or scaler not found: {e}. Please run phase2_ml_modeling.py first.")

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
        
    # Scale features
    try:
        features_scaled = scaler.transform([feature_list])
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error scaling features. Ensure models are loaded.")
    
    # Predict using models
    ic_preds = model_ic.predict(features_scaled)[0]
    jet_preds = model_jet.predict(features_scaled)[0]
    
    return {
        "input_blend": blend.model_dump(),
        "calculated_properties": {
            "Viscosity_cSt": round(feature_list[4], 2),
            "Density_kgm3": round(feature_list[5], 2),
            "Flash_Point_C": round(feature_list[6], 2),
            "Calorific_Value_MJkg": round(feature_list[7], 2)
        },
        "ic_engine_predictions": {
            "BTE_pct": round(ic_preds[0], 2),
            "BSFC_gkWh": round(ic_preds[1], 2),
            "NOx_ppm": round(ic_preds[2], 2),
            "Smoke_Opacity_pct": round(ic_preds[3], 2)
        },
        "jet_engine_predictions": {
            "Thrust_kN": round(jet_preds[0], 2),
            "SFC_gkNs": round(jet_preds[1], 2),
            "EGT_C": round(jet_preds[2], 2)
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
    
    if gemini_client:
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
            response = gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            res_text = response.text.replace('```json', '').replace('```', '').strip()
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
            if gemini_client:
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
                insight_response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=insight_prompt,
                )
                response_msg = insight_response.text.strip()
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
        if gemini_client:
            try:
                gen_prompt = f"You are a Biofuel Optimization AI. Answer this concisely: {text}"
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=gen_prompt,
                )
                return {"response": response.text.strip()}
            except:
                pass
                
        return {"response": "Hello! I am the Biofuel AI Assistant. You can ask me specific scenarios like 'What happens if I use 20% Castor oil and 5% IPA?'"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
