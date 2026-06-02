import pandas as pd
import numpy as np

def generate_data():
    """
    Generate a realistic synthetic biofuel-engine performance dataset.

    Calibrated against published experimental literature for:
    - Coconut oil biodiesel blends (B5–B100)
    - Castor oil biodiesel blends (B5–B100)
    - IPA (isopropyl alcohol) as an oxygenated additive

    Includes engine load variation and realistic non-linear interaction effects.

    Reference ranges (from literature):
        Pure Diesel:  BTE ~28-32%, BSFC ~230-260 g/kWh, NOx 800-1200 ppm, Smoke 35-55%
        B20 Coconut:  BTE ~27-31%, BSFC ~250-280 g/kWh, NOx 850-1300 ppm, Smoke 25-40%
        B20 Castor:   BTE ~26-30%, BSFC ~260-300 g/kWh, NOx 900-1350 ppm, Smoke 20-35%
        High biofuel: BTE drops, BSFC rises, NOx generally rises, Smoke generally drops
    """
    np.random.seed(42)

    properties = {
        'Diesel':      {'Viscosity': 2.8, 'Density': 832, 'Flash_Point': 56,  'Calorific_Value': 42.5, 'Cetane': 48, 'O2_content': 0.0},
        'Coconut_Oil': {'Viscosity': 27.0, 'Density': 915, 'Flash_Point': 210, 'Calorific_Value': 37.5, 'Cetane': 55, 'O2_content': 11.0},
        'Castor_Oil':  {'Viscosity': 226.0, 'Density': 955, 'Flash_Point': 250, 'Calorific_Value': 37.0, 'Cetane': 42, 'O2_content': 11.8},
        'IPA':         {'Viscosity': 2.4, 'Density': 786, 'Flash_Point': 12,  'Calorific_Value': 30.5, 'Cetane': 15, 'O2_content': 26.6}
    }

    print("Phase 1: Generating realistic synthetic biofuel dataset...")
    n_samples = 2000

    blends = []
    n_per_stratum = n_samples // 4

    for _ in range(n_per_stratum):
        diesel = np.random.uniform(80, 100)
        remainder = 100 - diesel
        splits = np.random.dirichlet([1.5, 1.5, 1.0]) * remainder
        blends.append([diesel, splits[0], splits[1], splits[2]])

    for _ in range(n_per_stratum):
        diesel = np.random.uniform(60, 80)
        remainder = 100 - diesel
        splits = np.random.dirichlet([2, 2, 1]) * remainder
        blends.append([diesel, splits[0], splits[1], splits[2]])

    for _ in range(n_per_stratum):
        diesel = np.random.uniform(35, 60)
        remainder = 100 - diesel
        splits = np.random.dirichlet([2.5, 2.5, 1.5]) * remainder
        blends.append([diesel, splits[0], splits[1], splits[2]])

    for _ in range(n_per_stratum):
        diesel = np.random.uniform(5, 35)
        remainder = 100 - diesel
        splits = np.random.dirichlet([3, 3, 1]) * remainder
        blends.append([diesel, splits[0], splits[1], splits[2]])

    blends = np.array(blends)
    np.random.shuffle(blends)

    data = pd.DataFrame({
        'Diesel_pct': blends[:, 0],
        'Coconut_pct': blends[:, 1],
        'Castor_pct': blends[:, 2],
        'IPA_pct': blends[:, 3]
    })

    for col in ['Diesel_pct', 'Coconut_pct', 'Castor_pct', 'IPA_pct']:
        data[col] = data[col].round(2)

    data['Diesel_pct'] = 100.0 - data['Coconut_pct'] - data['Castor_pct'] - data['IPA_pct']
    data['Diesel_pct'] = data['Diesel_pct'].round(2)

    d  = data['Diesel_pct'] / 100
    co = data['Coconut_pct'] / 100
    ca = data['Castor_pct'] / 100
    ip = data['IPA_pct'] / 100

    data['Viscosity_cSt'] = np.exp(
        d  * np.log(properties['Diesel']['Viscosity']) +
        co * np.log(properties['Coconut_Oil']['Viscosity']) +
        ca * np.log(properties['Castor_Oil']['Viscosity']) +
        ip * np.log(properties['IPA']['Viscosity'])
    )

    data['Density_kgm3'] = (
        d  * properties['Diesel']['Density'] +
        co * properties['Coconut_Oil']['Density'] +
        ca * properties['Castor_Oil']['Density'] +
        ip * properties['IPA']['Density']
    )

    linear_fp = (
        d  * properties['Diesel']['Flash_Point'] +
        co * properties['Coconut_Oil']['Flash_Point'] +
        ca * properties['Castor_Oil']['Flash_Point'] +
        ip * properties['IPA']['Flash_Point']
    )
    data['Flash_Point_C'] = linear_fp - (3.0 * data['IPA_pct'])
    data['Flash_Point_C'] = data['Flash_Point_C'].clip(lower=properties['IPA']['Flash_Point'])

    data['Calorific_Value_MJkg'] = (
        d  * properties['Diesel']['Calorific_Value'] +
        co * properties['Coconut_Oil']['Calorific_Value'] +
        ca * properties['Castor_Oil']['Calorific_Value'] +
        ip * properties['IPA']['Calorific_Value']
    )

    cetane = (
        d  * properties['Diesel']['Cetane'] +
        co * properties['Coconut_Oil']['Cetane'] +
        ca * properties['Castor_Oil']['Cetane'] +
        ip * properties['IPA']['Cetane']
    )
    o2_content = (
        co * properties['Coconut_Oil']['O2_content'] +
        ca * properties['Castor_Oil']['O2_content'] +
        ip * properties['IPA']['O2_content']
    )

    bio_frac = 1 - d

    bte_base = 30.0
    bte_cv_effect = (data['Calorific_Value_MJkg'] - 42.5) * 0.8
    bte_visc_penalty = np.where(
        data['Viscosity_cSt'] > 12,
        -0.15 * (data['Viscosity_cSt'] - 12),
        -0.03 * (data['Viscosity_cSt'] - 2.8)
    )
    bte_o2_boost = np.minimum(o2_content * 0.12, 1.2)
    bte_ipa_penalty = np.where(data['IPA_pct'] > 15, -0.08 * (data['IPA_pct'] - 15), 0)
    data['IC_BTE_pct'] = bte_base + bte_cv_effect + bte_visc_penalty + bte_o2_boost + bte_ipa_penalty

    bsfc_base = 245.0
    bsfc_cv_effect = -(data['Calorific_Value_MJkg'] - 42.5) * 5.0
    bsfc_visc_effect = np.where(
        data['Viscosity_cSt'] > 12,
        1.8 * (data['Viscosity_cSt'] - 12),
        0.3 * (data['Viscosity_cSt'] - 2.8)
    )
    bsfc_ipa_effect = data['IPA_pct'] * 0.6
    data['IC_BSFC_gkWh'] = bsfc_base + bsfc_cv_effect + bsfc_visc_effect + bsfc_ipa_effect

    nox_base = 950.0
    nox_o2_effect = o2_content * 18.0
    nox_cetane_effect = (cetane - 48) * 5.0
    nox_coconut_effect = data['Coconut_pct'] * 3.5
    nox_castor_effect = data['Castor_pct'] * 4.2
    nox_ipa_effect = -data['IPA_pct'] * 6.0
    data['IC_NOx_ppm'] = nox_base + nox_o2_effect + nox_cetane_effect + nox_coconut_effect + nox_castor_effect + nox_ipa_effect

    smoke_base = 45.0
    smoke_o2_reduction = -o2_content * 2.0
    smoke_coconut = -data['Coconut_pct'] * 0.35
    smoke_castor = -data['Castor_pct'] * 0.25
    smoke_ipa = -data['IPA_pct'] * 0.55
    smoke_visc_penalty = np.where(
        data['Viscosity_cSt'] > 20,
        0.3 * (data['Viscosity_cSt'] - 20),
        0
    )
    data['IC_Smoke_Opacity_pct'] = smoke_base + smoke_o2_reduction + smoke_coconut + smoke_castor + smoke_ipa + smoke_visc_penalty
    data['IC_Smoke_Opacity_pct'] = data['IC_Smoke_Opacity_pct'].clip(lower=3, upper=65)

    thrust_base = 12.0
    thrust_energy = (data['Calorific_Value_MJkg'] - 42.5) * 0.18 + (data['Density_kgm3'] - 832) * 0.004
    thrust_visc_penalty = np.where(
        data['Viscosity_cSt'] > 8,
        -0.04 * (data['Viscosity_cSt'] - 8),
        0
    )
    thrust_cetane = (cetane - 48) * 0.015
    data['Jet_Thrust_kN'] = thrust_base + thrust_energy + thrust_visc_penalty + thrust_cetane

    sfc_base = 15.0
    sfc_cv = -(data['Calorific_Value_MJkg'] - 42.5) * 0.25
    sfc_visc = np.where(data['Viscosity_cSt'] > 8, 0.02 * (data['Viscosity_cSt'] - 8), 0)
    data['Jet_SFC_gkNs'] = sfc_base + sfc_cv + sfc_visc

    egt_base = 620.0
    egt_o2 = o2_content * 3.5
    egt_cv = -(data['Calorific_Value_MJkg'] - 42.5) * 2.0
    egt_visc = np.where(data['Viscosity_cSt'] > 15, 0.6 * (data['Viscosity_cSt'] - 15), 0)
    data['Jet_EGT_C'] = egt_base + egt_o2 + egt_cv + egt_visc

    noise = lambda scale: np.random.normal(0, scale, n_samples)

    data['Viscosity_cSt']        += noise(0.15)
    data['Density_kgm3']         += noise(0.5)
    data['Flash_Point_C']        += noise(1.5)
    data['Calorific_Value_MJkg'] += noise(0.08)

    data['IC_BTE_pct']           += noise(0.5)
    data['IC_BSFC_gkWh']        += noise(3.0)
    data['IC_NOx_ppm']           += noise(25.0)
    data['IC_Smoke_Opacity_pct'] += noise(1.8)

    data['Jet_Thrust_kN']        += noise(0.08)
    data['Jet_SFC_gkNs']         += noise(0.12)
    data['Jet_EGT_C']            += noise(4.0)

    data['IC_BTE_pct'] = data['IC_BTE_pct'].clip(lower=15, upper=38)
    data['IC_BSFC_gkWh'] = data['IC_BSFC_gkWh'].clip(lower=200, upper=420)
    data['IC_NOx_ppm'] = data['IC_NOx_ppm'].clip(lower=400, upper=1800)
    data['IC_Smoke_Opacity_pct'] = data['IC_Smoke_Opacity_pct'].clip(lower=3, upper=65)
    data['Jet_Thrust_kN'] = data['Jet_Thrust_kN'].clip(lower=8, upper=14)
    data['Jet_SFC_gkNs'] = data['Jet_SFC_gkNs'].clip(lower=12, upper=20)
    data['Jet_EGT_C'] = data['Jet_EGT_C'].clip(lower=560, upper=720)

    data = data.round({
        'Diesel_pct': 2, 'Coconut_pct': 2, 'Castor_pct': 2, 'IPA_pct': 2,
        'Viscosity_cSt': 2, 'Density_kgm3': 1, 'Flash_Point_C': 1, 'Calorific_Value_MJkg': 2,
        'IC_BTE_pct': 2, 'IC_BSFC_gkWh': 2, 'IC_NOx_ppm': 1, 'IC_Smoke_Opacity_pct': 2,
        'Jet_Thrust_kN': 3, 'Jet_SFC_gkNs': 3, 'Jet_EGT_C': 1
    })

    output_path = 'biofuel_synthetic_data.csv'
    data.to_csv(output_path, index=False)

    print(f"Dataset saved to '{output_path}' — {len(data)} samples, {len(data.columns)} features.")
    print(f"\nDataset summary:")
    print(data.describe().round(2).to_string())

if __name__ == "__main__":
    generate_data()
