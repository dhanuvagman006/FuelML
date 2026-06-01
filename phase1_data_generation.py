import pandas as pd
import numpy as np

def generate_data():
    # Set random seed for reproducibility
    np.random.seed(42)

    # 1. Define theoretical properties 
    # Properties: Viscosity [cSt], Density [kg/m3], Flash Point [C], Calorific Value [MJ/kg]
    properties = {
        'Diesel': {'Viscosity': 3.0, 'Density': 830, 'Flash_Point': 60, 'Calorific_Value': 43.0},
        'Coconut_Oil': {'Viscosity': 30.0, 'Density': 920, 'Flash_Point': 225, 'Calorific_Value': 37.0},
        'Castor_Oil': {'Viscosity': 250.0, 'Density': 960, 'Flash_Point': 260, 'Calorific_Value': 39.0},
        'IPA': {'Viscosity': 2.0, 'Density': 786, 'Flash_Point': 12, 'Calorific_Value': 30.0}
    }

    print("Phase 1: Generating synthetic data...")
    # 2. Generate 500 rows of synthetic blend ratios
    n_samples = 500

    # Using Dirichlet distribution to ensure ratios sum to 1.
    # Alpha parameters [5, 1.5, 1.5, 1] chosen to heavily favor Diesel while allowing diverse blends.
    ratios = np.random.dirichlet((5, 1.5, 1.5, 1), n_samples)

    data = pd.DataFrame({
        'Diesel_pct': ratios[:, 0] * 100,
        'Coconut_pct': ratios[:, 1] * 100,
        'Castor_pct': ratios[:, 2] * 100,
        'IPA_pct': ratios[:, 3] * 100
    })

    # 3. Map blend ratios to physical properties using mixing rules/realistic deviations
    
    # Viscosity: Logarithmic mixing rule (Arrhenius/Refutas simplified)
    data['Viscosity_cSt'] = np.exp(
        (data['Diesel_pct']/100) * np.log(properties['Diesel']['Viscosity']) +
        (data['Coconut_pct']/100) * np.log(properties['Coconut_Oil']['Viscosity']) +
        (data['Castor_pct']/100) * np.log(properties['Castor_Oil']['Viscosity']) +
        (data['IPA_pct']/100) * np.log(properties['IPA']['Viscosity'])
    )

    # Density: Linear volume/mass mixing rule approximation
    data['Density_kgm3'] = (
        (data['Diesel_pct']/100) * properties['Diesel']['Density'] +
        (data['Coconut_pct']/100) * properties['Coconut_Oil']['Density'] +
        (data['Castor_pct']/100) * properties['Castor_Oil']['Density'] +
        (data['IPA_pct']/100) * properties['IPA']['Density']
    )

    # Flash Point: Non-linear. Highly volatile components (like IPA) disproportionately lower the blend's flash point.
    linear_fp = (
        (data['Diesel_pct']/100) * properties['Diesel']['Flash_Point'] +
        (data['Coconut_pct']/100) * properties['Coconut_Oil']['Flash_Point'] +
        (data['Castor_pct']/100) * properties['Castor_Oil']['Flash_Point'] +
        (data['IPA_pct']/100) * properties['IPA']['Flash_Point']
    )
    # Applying a non-linear deviation based on IPA concentration
    data['Flash_Point_C'] = linear_fp - (2.5 * data['IPA_pct'])
    data['Flash_Point_C'] = data['Flash_Point_C'].clip(lower=properties['IPA']['Flash_Point'])

    # Calorific Value: Linear mass mixing rule
    data['Calorific_Value_MJkg'] = (
        (data['Diesel_pct']/100) * properties['Diesel']['Calorific_Value'] +
        (data['Coconut_pct']/100) * properties['Coconut_Oil']['Calorific_Value'] +
        (data['Castor_pct']/100) * properties['Castor_Oil']['Calorific_Value'] +
        (data['IPA_pct']/100) * properties['IPA']['Calorific_Value']
    )

    # 4. Map physical properties to simulated engine performance metrics
    
    # --- IC Engine Metrics ---
    # BTE (Brake Thermal Efficiency, %): Higher Calorific Value -> Higher BTE. High Viscosity -> poor atomization -> lower BTE.
    data['IC_BTE_pct'] = 30.0 + (data['Calorific_Value_MJkg'] - 40) * 0.6 - (data['Viscosity_cSt'] - 3) * 0.05
    
    # BSFC (Brake Specific Fuel Consumption, g/kWh): Inverse to Calorific value. Higher viscosity increases BSFC.
    data['IC_BSFC_gkWh'] = 250 - (data['Calorific_Value_MJkg'] - 43) * 6 + (data['Viscosity_cSt'] - 3) * 0.5
    
    # NOx (ppm): Biofuels have bound oxygen, leading to better but hotter combustion -> higher NOx.
    data['IC_NOx_ppm'] = 500 + data['Coconut_pct'] * 2.5 + data['Castor_pct'] * 3.0 - data['IPA_pct'] * 1.5
    
    # Smoke Opacity (%): Oxygenates (Coconut, Castor, IPA) reduce soot and smoke.
    data['IC_Smoke_Opacity_pct'] = 45 - data['Coconut_pct'] * 0.4 - data['Castor_pct'] * 0.3 - data['IPA_pct'] * 0.6
    data['IC_Smoke_Opacity_pct'] = data['IC_Smoke_Opacity_pct'].clip(lower=2, upper=100)

    # --- Jet Engine Metrics ---
    # Thrust (kN): Driven by fuel mass flow (Density) and energy (Calorific Value).
    data['Jet_Thrust_kN'] = 12.0 + (data['Calorific_Value_MJkg'] - 43) * 0.25 + (data['Density_kgm3'] - 830) * 0.005
    
    # SFC (Specific Fuel Consumption, g/kNs): Inverse to Calorific Value.
    data['Jet_SFC_gkNs'] = 14.5 - (data['Calorific_Value_MJkg'] - 43) * 0.35 + (data['Viscosity_cSt'] - 3) * 0.02
    
    # EGT (Exhaust Gas Temperature, C): Correlates with CV and combustion characteristics.
    data['Jet_EGT_C'] = 620 - data['Calorific_Value_MJkg'] * 1.2 + data['Viscosity_cSt'] * 0.5 + data['Density_kgm3'] * 0.03

    # Add controlled Gaussian noise to simulate real-world experimental measurement variance
    noise = lambda scale: np.random.normal(0, scale, n_samples)
    data['IC_BTE_pct'] += noise(0.4)
    data['IC_BSFC_gkWh'] += noise(2.0)
    data['IC_NOx_ppm'] += noise(12.0)
    data['IC_Smoke_Opacity_pct'] += noise(1.5)
    data['Jet_Thrust_kN'] += noise(0.15)
    data['Jet_SFC_gkNs'] += noise(0.2)
    data['Jet_EGT_C'] += noise(3.5)

    # Save dataset
    output_path = 'biofuel_synthetic_data.csv'
    data.to_csv(output_path, index=False)
    print(f"Dataset successfully generated and saved to '{output_path}' with {len(data)} rows.")

if __name__ == "__main__":
    generate_data()
