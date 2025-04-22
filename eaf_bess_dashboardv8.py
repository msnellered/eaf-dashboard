#Okay, let's integrate the BESS technology selection dropdown and update the parameter handling.
#
#This involves several steps:
#
#1.  **Define Data:** Create a dictionary holding the parameters for each battery technology. We'll use the PNNL report (provided via OCR) and the user's supercapacitor specs as primary sources, making educated guesses or using placeholders where data is missing.
#2.  **Update Layout:** Modify the BESS Parameters section in the Dash layout to include the dropdown, the example company display, and the new input fields grouped logically.
#3.  **Update Callbacks:**
#    *   Add a callback to update the input fields when the technology dropdown changes.
#    *   Modify the `update_bess_params_store` callback to read from the new inputs.
#    *   Modify the calculation functions (`calculate_incentives`, `calculate_financial_metrics`) to use the new, more detailed parameters from the store.
#
#Here's the modified code:
#
#```python
# --- START OF FILE eaf_bess_dashboardv6_enhanced_bess.py ---

import dash
# Use dash_bootstrap_components for better layout options like Cards
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback_context, ALL, dash_table
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import json
from datetime import datetime
import calendar
import traceback  # For detailed error logging

# --- numpy_financial fallback (keep as is) ---
try:
    import numpy_financial as npf
except ImportError:
    print(
        "WARNING: numpy_financial package is required for accurate financial calculations."
        " Please install it with: pip install numpy-financial"
    )
    # ... (keep the DummyNPF class as defined before) ...
    class DummyNPF:
        def npv(self, rate, values):
            print(
                "WARNING: Using simplified NPV calculation. Install numpy-financial for accurate results."
            )
            if rate <= -1: return float("nan")
            try: return sum(values[i] / ((1 + rate) ** i) for i in range(len(values)))
            except ZeroDivisionError: return float("nan")
        def irr(self, values):
            print("WARNING: IRR calculation requires numpy-financial. Install with: pip install numpy-financial")
            if not values or values[0] >= 0: return float("nan")
            r_low, r_high = -0.99, 1.0; max_iter = 100; tolerance = 1e-6
            for _ in range(max_iter):
                r_mid = (r_low + r_high) / 2
                if abs(r_high - r_low) < tolerance: return r_mid
                try: npv_mid = sum(values[i] / ((1 + r_mid) ** i) for i in range(len(values)))
                except ZeroDivisionError: npv_mid = float("inf") if values[0] < 0 else float("-inf")
                if abs(npv_mid) < tolerance: return r_mid
                if npv_mid < 0: r_low = r_mid
                else: r_high = r_mid
            return float("nan")
    npf = DummyNPF()


# --- Initialize the Dash app with Bootstrap themes ---
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP], # Use Bootstrap
    suppress_callback_exceptions=True,
)
server = app.server
app.title = "Battery Profitability Tool"

# --- Default Parameters (Utility, EAF, Financial - keep as is) ---
# ... (default_utility_params, default_financial_params, default_incentive_params remain the same) ...
default_utility_params = {
    "energy_rates": {"off_peak": 50, "mid_peak": 100, "peak": 150},
    "demand_charge": 10,
    "tou_periods_raw": [ (0.0, 8.0, "off_peak"), (8.0, 10.0, "peak"), (10.0, 16.0, "mid_peak"), (16.0, 20.0, "peak"), (20.0, 24.0, "off_peak")],
    "tou_periods_filled": [ (0.0, 8.0, "off_peak"), (8.0, 10.0, "peak"), (10.0, 16.0, "mid_peak"), (16.0, 20.0, "peak"), (20.0, 24.0, "off_peak")],
    "seasonal_rates": False, "winter_months": [11, 12, 1, 2, 3], "summer_months": [6, 7, 8, 9], "shoulder_months": [4, 5, 10],
    "winter_multiplier": 1.0, "summer_multiplier": 1.2, "shoulder_multiplier": 1.1,
}
default_financial_params = {
    "wacc": 0.131, "project_lifespan": 30, "tax_rate": 0.2009,
    "inflation_rate": 0.024, "salvage_value": 0.1, # Note: Salvage might be replaced by disposal cost
}
default_incentive_params = {
    "itc_enabled": False, "itc_percentage": 30, "ceic_enabled": False, "ceic_percentage": 30,
    "bonus_credit_enabled": False, "bonus_credit_percentage": 10, "sgip_enabled": False, "sgip_amount": 400,
    "ess_enabled": False, "ess_amount": 280, "mabi_enabled": False, "mabi_amount": 250,
    "cs_enabled": False, "cs_amount": 225, "custom_incentive_enabled": False,
    "custom_incentive_type": "per_kwh", "custom_incentive_amount": 100, "custom_incentive_description": "Custom incentive",
}


# --- BESS Technology Data ---
# Sources: PNNL 2022 Report (OCR), User Input, Educated Estimates
# Note: Costs vary widely. These are illustrative defaults.
# SB = Storage Block, BOS = Balance of System (Storage specific), PCS = Power Conversion System
# EPC = Engineering, Procurement, Construction (often includes installation, commissioning)
bess_technology_data = {
    "LFP": {
        "example_product": "Tesla Megapack 2XL (Illustrative)",
        # Capex
        "sb_bos_cost_per_kwh": 210,  # PNNL Fig 4.3 (10MW/4hr) - SB+SBOS combined for simplicity here
        "pcs_cost_per_kw": 75,       # PNNL Fig 4.3 (10MW/4hr) - Power Equipment
        "epc_cost_per_kwh": 56,      # PNNL Fig 4.3 (10MW/4hr) - EPC
        "sys_integration_cost_per_kwh": 42, # PNNL Fig 4.3 (10MW/4hr) - System Integration
        # Opex
        "fixed_om_per_kw_yr": 5,     # PNNL p.17 estimate
        "rte_percent": 86,           # PNNL Table 4.4 (AC-AC Inverter Level)
        "insurance_percent_yr": 0.5, # Placeholder estimate
        # Decommissioning
        "disconnect_cost_per_kwh": 2, # Placeholder estimate
        "recycling_cost_per_kwh": 1,  # Low cost/value for LFP recycling
        # Performance
        "cycle_life": 4000,          # PNNL Table 4.3 (Adjusted 80% DOD) -> Using a common estimate
        "dod_percent": 95,           # Higher DoD often possible for LFP
        "calendar_life": 16,         # PNNL p.19
    },
    "NMC": {
        "example_product": "Samsung SDI E3 (Illustrative)",
        # Capex
        "sb_bos_cost_per_kwh": 250,  # PNNL Fig 4.5 (10MW/4hr) - SB+SBOS estimate
        "pcs_cost_per_kw": 75,       # PNNL Fig 4.5 (10MW/4hr) - Power Equipment
        "epc_cost_per_kwh": 63,      # PNNL Fig 4.5 (10MW/4hr) - EPC
        "sys_integration_cost_per_kwh": 48, # PNNL Fig 4.5 (10MW/4hr) - System Integration
        # Opex
        "fixed_om_per_kw_yr": 6,     # PNNL p.17 estimate (slightly higher than LFP)
        "rte_percent": 86,           # PNNL Table 4.4 (AC-AC Inverter Level)
        "insurance_percent_yr": 0.5, # Placeholder estimate
        # Decommissioning
        "disconnect_cost_per_kwh": 2, # Placeholder estimate
        "recycling_cost_per_kwh": -2, # Potential value from NMC recycling (negative cost)
        # Performance
        "cycle_life": 3500,          # PNNL Table 4.3 -> Using a common estimate, lower than LFP typically
        "dod_percent": 90,           # Often limited slightly more than LFP
        "calendar_life": 13,         # PNNL p.19
    },
    "Redox Flow (Vanadium)": {
        "example_product": "Invinity VS3 / Generic VRFB (Illustrative)",
        # Capex
        "sb_bos_cost_per_kwh": 250,  # PNNL Fig 4.10 (10MW/4hr) - SB+SBOS estimate (highly duration dependent)
        "pcs_cost_per_kw": 138,      # PNNL Fig 4.10 (10MW/4hr) - PCS + DC-DC
        "epc_cost_per_kwh": 70,      # PNNL Fig 4.10 (10MW/4hr) - EPC estimate
        "sys_integration_cost_per_kwh": 60, # PNNL Fig 4.10 (10MW/4hr) - System Integration estimate
        # Opex
        "fixed_om_per_kw_yr": 7,     # PNNL p.39 estimate
        "rte_percent": 68,           # PNNL Table 4.9 (AC-AC Inverter Level) - Lower RTE
        "insurance_percent_yr": 0.6, # Placeholder estimate
        # Decommissioning
        "disconnect_cost_per_kwh": 3, # Placeholder estimate
        "recycling_cost_per_kwh": 5,  # Electrolyte recovery/recycling cost
        # Performance
        "cycle_life": 15000,         # Very high cycle life
        "dod_percent": 100,          # Typically 100% DoD capable
        "calendar_life": 20,         # Stack life often ~12-15, electrolyte longer
    },
     "Sodium-Ion": {
        "example_product": "Natron Energy BlueTray 4000 (Illustrative - High Power Focus)",
        # Capex - Natron focuses on high power, data is scarce for grid scale energy apps
        "sb_bos_cost_per_kwh": 300,  # Placeholder - Potentially lower energy cost than Li-ion?
        "pcs_cost_per_kw": 100,      # Placeholder - Might be similar to Li-ion
        "epc_cost_per_kwh": 60,      # Placeholder
        "sys_integration_cost_per_kwh": 50, # Placeholder
        # Opex
        "fixed_om_per_kw_yr": 5,     # Placeholder - Potentially low O&M
        "rte_percent": 90,           # Claimed high RTE
        "insurance_percent_yr": 0.5, # Placeholder
        # Decommissioning
        "disconnect_cost_per_kwh": 2, # Placeholder
        "recycling_cost_per_kwh": 3,  # Recycling infrastructure less mature than Li-ion
        # Performance
        "cycle_life": 10000,         # Claimed high cycle life
        "dod_percent": 100,
        "calendar_life": 20,         # Placeholder
    },
    "Iron-Air": {
        "example_product": "Form Energy (Illustrative - Long Duration Focus)",
        # Capex - Designed for very low energy cost, potentially higher power cost
        "sb_bos_cost_per_kwh": 30,   # Target is very low (<$20/kWh eventually) - Placeholder
        "pcs_cost_per_kw": 300,      # Placeholder - Power components might be more complex/costly
        "epc_cost_per_kwh": 20,      # Placeholder
        "sys_integration_cost_per_kwh": 15, # Placeholder
        # Opex
        "fixed_om_per_kw_yr": 8,     # Placeholder - Might involve air handling etc.
        "rte_percent": 50,           # Lower RTE expected for metal-air
        "insurance_percent_yr": 0.7, # Placeholder
        # Decommissioning
        "disconnect_cost_per_kwh": 3, # Placeholder
        "recycling_cost_per_kwh": 1,  # Iron is cheap/recyclable
        # Performance
        "cycle_life": 10000,         # Expected high cycle count
        "dod_percent": 100,
        "calendar_life": 20,         # Placeholder
    },
    "Hybrid Supercapacitor": {
        "example_product": "Generic Hybrid Supercapacitor System",
        # Capex - User provided cost, split estimate between SB/PCS
        "sb_bos_cost_per_kwh": 900,  # High energy cost ($/kWh)
        "pcs_cost_per_kw": 100,      # Power cost ($/kW) assumed lower part of total
        "epc_cost_per_kwh": 50,      # Placeholder
        "sys_integration_cost_per_kwh": 50, # Placeholder
        # Opex - User provided
        "fixed_om_per_kw_yr": 2 * (1000/1), # Convert $2/kWh/yr to $/kW/yr (Assume 1h duration for conversion -> Needs refinement based on actual power/energy ratio) -> Let's use a direct input for O&M $/kWh/yr instead
        "rte_percent": 98,
        "insurance_percent_yr": 0.1,
        # Decommissioning - User provided
        "disconnect_cost_per_kwh": 0.5, # Estimate
        "recycling_cost_per_kwh": 1.0,
        # Performance - User provided
        "cycle_life": 100000,
        "dod_percent": 100,
        "calendar_life": 30,
        # Add the specific O&M format needed
        "om_cost_per_kwh_yr": 2, # From user spec
    },
}

# --- Default BESS Parameters Store Structure ---
# Initialize with LFP defaults
default_bess_params_store = {
    "technology": "LFP",
    "capacity": 40,  # MWh - User still defines overall size
    "power_max": 20, # MW - User still defines overall size
    **bess_technology_data["LFP"] # Populate with LFP details
}
# Adjust supercap default O&M structure
if "fixed_om_per_kw_yr" in bess_technology_data["Hybrid Supercapacitor"]:
    del bess_technology_data["Hybrid Supercapacitor"]["fixed_om_per_kw_yr"]


# --- Nucor Mill Data (keep as is) ---
# ... (nucor_mills dictionary remains the same) ...
nucor_mills = { "West Virginia": { "location": "Apple Grove, WV", "type": "Sheet", "eaf_count": 2, "eaf_type": "DC", "eaf_manufacturer": "SMS", "eaf_size": 190, "cycles_per_day": 26, "tons_per_year": 3000000, "days_per_year": 300, "cycle_duration": 36, "utility": "Appalachian Power", "grid_cap": 50, }, "Auburn": { "location": "Auburn, NY", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Unknown", "eaf_size": 60, "cycles_per_day": 28, "tons_per_year": 510000, "days_per_year": 300, "cycle_duration": 36, "utility": "New York State Electric & Gas", "grid_cap": 25, }, "Birmingham": { "location": "Birmingham, AL", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Unknown", "eaf_size": 52, "cycles_per_day": 20, "tons_per_year": 310000, "days_per_year": 300, "cycle_duration": 36, "utility": "Alabama Power", "grid_cap": 20, }, "Arkansas": { "location": "Blytheville, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "Demag", "eaf_size": 150, "cycles_per_day": 28, "tons_per_year": 2500000, "days_per_year": 300, "cycle_duration": 38, "utility": "Entergy Arkansas", "grid_cap": 45, }, "Kankakee": { "location": "Bourbonnais, IL", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", "eaf_size": 73, "cycles_per_day": 39, "tons_per_year": 850000, "days_per_year": 300, "cycle_duration": 36, "utility": "ComEd", "grid_cap": 30, }, "Brandenburg": { "location": "Brandenburg, KY", "type": "Sheet", "eaf_count": 1, "eaf_type": "DC", "eaf_manufacturer": "Danieli", "eaf_size": 150, "cycles_per_day": 27, "tons_per_year": 1200000, "days_per_year": 300, "cycle_duration": 36, "utility": "LG&E KU", "grid_cap": 45, }, "Hertford": { "location": "Cofield, NC", "type": "Plate", "eaf_count": 1, "eaf_type": "DC", "eaf_manufacturer": "MAN GHH", "eaf_size": 150, "cycles_per_day": 30, "tons_per_year": 1350000, "days_per_year": 300, "cycle_duration": 36, "utility": "Dominion Energy", "grid_cap": 45, }, "Crawfordsville": { "location": "Crawfordsville, IN", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "Brown-Boveri", "eaf_size": 118, "cycles_per_day": 27, "tons_per_year": 1890000, "days_per_year": 300, "cycle_duration": 36, "utility": "Duke Energy", "grid_cap": 40, }, "Darlington": { "location": "Darlington, SC", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", "eaf_size": 110, "cycles_per_day": 30, "tons_per_year": 980000, "days_per_year": 300, "cycle_duration": 36, "utility": "Duke Energy", "grid_cap": 40, }, "Decatur": { "location": "Decatur, AL", "type": "Sheet", "eaf_count": 2, "eaf_type": "DC", "eaf_manufacturer": "NKK-SE", "eaf_size": 165, "cycles_per_day": 20, "tons_per_year": 2000000, "days_per_year": 300, "cycle_duration": 36, "utility": "Alabama Power", "grid_cap": 48, }, "Gallatin": { "location": "Ghent, KY", "type": "Sheet", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "NKK-SE, Danieli", "eaf_size": 175, "cycles_per_day": 27, "tons_per_year": 2800000, "days_per_year": 300, "cycle_duration": 36, "utility": "Kentucky Utilities", "grid_cap": 53, }, "Hickman": { "location": "Hickman, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", "eaf_size": 150, "cycles_per_day": 22, "tons_per_year": 2000000, "days_per_year": 300, "cycle_duration": 36, "utility": "Mississippi County Electric Cooperative", "grid_cap": 45, }, "Berkeley": { "location": "Huger, SC", "type": "Sheet/Beam Mill", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "MAN GHH", "eaf_size": 154, "cycles_per_day": 26, "tons_per_year": 2430000, "days_per_year": 300, "cycle_duration": 36, "utility": "Santee Cooper", "grid_cap": 46, }, "Texas": { "location": "Jewett, TX", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "SMS Concast", "eaf_size": 100, "cycles_per_day": 33, "tons_per_year": 1000000, "days_per_year": 300, "cycle_duration": 36, "utility": "Oncor Electric Delivery", "grid_cap": 30, }, "Kingman": { "location": "Kingman, AZ", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", "eaf_size": 100, "cycles_per_day": 21, "tons_per_year": 630000, "days_per_year": 300, "cycle_duration": 36, "utility": "UniSource Energy Services", "grid_cap": 30, }, "Marion": { "location": "Marion, OH", "type": "Bar Mill/Sign Pos", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "?", "eaf_size": 100, "cycles_per_day": 40, "tons_per_year": 1200000, "days_per_year": 300, "cycle_duration": 36, "utility": "AEP Ohio", "grid_cap": 30, }, "Nebraska": { "location": "Norfolk, NE", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "MAN GHH", "eaf_size": 95, "cycles_per_day": 35, "tons_per_year": 1000000, "days_per_year": 300, "cycle_duration": 36, "utility": "Nebraska Public Power District", "grid_cap": 29, }, "Utah": { "location": "Plymouth, UT", "type": "Bar", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "Fuchs", "eaf_size": 51, "cycles_per_day": 42, "tons_per_year": 1290000, "days_per_year": 300, "cycle_duration": 36, "utility": "Rocky Mountain Power", "grid_cap": 15, }, "Seattle": { "location": "Seattle, WA", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "Fuchs", "eaf_size": 100, "cycles_per_day": 29, "tons_per_year": 855000, "days_per_year": 300, "cycle_duration": 36, "utility": "Seattle City Light", "grid_cap": 30, }, "Sedalia": { "location": "Sedalia, MO", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "Danieli", "eaf_size": 40, "cycles_per_day": 39, "tons_per_year": 470000, "days_per_year": 300, "cycle_duration": 36, "utility": "Evergy", "grid_cap": 12, }, "Tuscaloosa": { "location": "Tuscaloosa, AL", "type": "Plate", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", "eaf_size": 122, "cycles_per_day": 17, "tons_per_year": 610000, "days_per_year": 300, "cycle_duration": 36, "utility": "Alabama Power", "grid_cap": 37, }, "Florida": { "location": "Frostproof, FL", "type": "?", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", "eaf_size": 40, "cycles_per_day": 38, "tons_per_year": 450000, "days_per_year": 300, "cycle_duration": 36, "utility": "Duke Energy Florida", "grid_cap": 12, }, "Jackson": { "location": "Flowood, MS", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "?", "eaf_size": 50, "cycles_per_day": 33, "tons_per_year": 490000, "days_per_year": 300, "cycle_duration": 36, "utility": "Entergy Mississippi (Assumed)", "grid_cap": 15, }, "Nucor-Yamato": { "location": "Blytheville, AR", "type": "Structural (implied)", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "?", "eaf_size": 150, "cycles_per_day": 25, "tons_per_year": 2500000, "days_per_year": 300, "cycle_duration": 36, "utility": "Mississippi County Electric Cooperative", "grid_cap": 45, }, "Custom": { "location": "Custom Location", "type": "Custom", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Custom", "eaf_size": 100, "cycles_per_day": 24, "tons_per_year": 1000000, "days_per_year": 300, "cycle_duration": 36, "utility": "Custom Utility", "grid_cap": 35, }, }

# --- Utility Rate Data (keep as is) ---
# ... (utility_rates dictionary and placeholder update logic remains the same) ...
utility_rates = { "Appalachian Power": { "energy_rates": {"off_peak": 45, "mid_peak": 90, "peak": 135}, "demand_charge": 12, "tou_periods": [ (0, 7, "off_peak"), (7, 11, "peak"), (11, 16, "mid_peak"), (16, 20, "peak"), (20, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [11, 12, 1, 2], "summer_months": [6, 7, 8, 9], "shoulder_months": [3, 4, 5, 10], "winter_multiplier": 1.0, "summer_multiplier": 1.3, "shoulder_multiplier": 1.1, }, "New York State Electric & Gas": { "energy_rates": {"off_peak": 60, "mid_peak": 110, "peak": 180}, "demand_charge": 15, "tou_periods": [ (0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "mid_peak"), (17, 21, "peak"), (21, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [11, 12, 1, 2, 3], "summer_months": [6, 7, 8], "shoulder_months": [4, 5, 9, 10], "winter_multiplier": 1.2, "summer_multiplier": 1.5, "shoulder_multiplier": 1.3, }, "Alabama Power": { "energy_rates": {"off_peak": 40, "mid_peak": 80, "peak": 120}, "demand_charge": 10, "tou_periods": [ (0, 8, "off_peak"), (8, 11, "peak"), (11, 15, "mid_peak"), (15, 19, "peak"), (19, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [12, 1, 2], "summer_months": [6, 7, 8, 9], "shoulder_months": [3, 4, 5, 10, 11], "winter_multiplier": 0.9, "summer_multiplier": 1.4, "shoulder_multiplier": 1.0, }, "Entergy Arkansas": { "energy_rates": {"off_peak": 42, "mid_peak": 85, "peak": 130}, "demand_charge": 11, "tou_periods": [ (0, 7, "off_peak"), (7, 10, "peak"), (10, 16, "mid_peak"), (16, 19, "peak"), (19, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [11, 12, 1, 2], "summer_months": [6, 7, 8, 9], "shoulder_months": [3, 4, 5, 10], "winter_multiplier": 0.9, "summer_multiplier": 1.3, "shoulder_multiplier": 1.0, }, "ComEd": { "energy_rates": {"off_peak": 48, "mid_peak": 95, "peak": 140}, "demand_charge": 13, "tou_periods": [ (0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "mid_peak"), (17, 21, "peak"), (21, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [11, 12, 1, 2, 3], "summer_months": [6, 7, 8], "shoulder_months": [4, 5, 9, 10], "winter_multiplier": 1.1, "summer_multiplier": 1.6, "shoulder_multiplier": 1.2, }, "LG&E KU": { "energy_rates": {"off_peak": 44, "mid_peak": 88, "peak": 125}, "demand_charge": 12.5, "tou_periods": [ (0, 7, "off_peak"), (7, 11, "peak"), (11, 17, "mid_peak"), (17, 21, "peak"), (21, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [11, 12, 1, 2], "summer_months": [6, 7, 8, 9], "shoulder_months": [3, 4, 5, 10], "winter_multiplier": 1.0, "summer_multiplier": 1.35, "shoulder_multiplier": 1.1, }, "Dominion Energy": { "energy_rates": {"off_peak": 47, "mid_peak": 94, "peak": 138}, "demand_charge": 13.5, "tou_periods": [ (0, 6, "off_peak"), (6, 11, "peak"), (11, 16, "mid_peak"), (16, 20, "peak"), (20, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [12, 1, 2, 3], "summer_months": [6, 7, 8, 9], "shoulder_months": [4, 5, 10, 11], "winter_multiplier": 1.05, "summer_multiplier": 1.45, "shoulder_multiplier": 1.15, }, "Duke Energy": { "energy_rates": {"off_peak": 46, "mid_peak": 92, "peak": 135}, "demand_charge": 14, "tou_periods": [ (0, 7, "off_peak"), (7, 10, "peak"), (10, 16, "mid_peak"), (16, 20, "peak"), (20, 24, "off_peak"), ], "seasonal_rates": True, "winter_months": [11, 12, 1, 2], "summer_months": [6, 7, 8, 9], "shoulder_months": [3, 4, 5, 10], "winter_multiplier": 0.95, "summer_multiplier": 1.4, "shoulder_multiplier": 1.1, }, "Kentucky Utilities": {}, "Mississippi County Electric Cooperative": { "energy_rates": {"off_peak": 32.72, "mid_peak": 32.72, "peak": 32.72}, "demand_charge": 12.28, "tou_periods": [(0, 24, "off_peak")], "seasonal_rates": False, "winter_months": default_utility_params["winter_months"], "summer_months": default_utility_params["summer_months"], "shoulder_months": default_utility_params["shoulder_months"], "winter_multiplier": 1.0, "summer_multiplier": 1.0, "shoulder_multiplier": 1.0, }, "Santee Cooper": { "energy_rates": {"off_peak": 37.50, "mid_peak": 37.50, "peak": 57.50}, "demand_charge": 19.26, "tou_periods": [(0, 13, "off_peak"), (13, 22, "peak"), (22, 24, "off_peak")], "seasonal_rates": True, "winter_months": [1, 2, 3, 4, 5, 9, 10, 11, 12], "summer_months": [6, 7, 8], "shoulder_months": [], "winter_multiplier": 1.0, "summer_multiplier": 1.0, "shoulder_multiplier": 1.0, }, "Oncor Electric Delivery": {}, "UniSource Energy Services": { "energy_rates": {"off_peak": 52.5, "mid_peak": 52.5, "peak": 77.5}, "demand_charge": 16.5, "tou_periods": [(0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "off_peak"), (17, 21, "peak"), (21, 24, "off_peak")], "seasonal_rates": True, "winter_months": [11, 12, 1, 2, 3, 4], "summer_months": [5, 6, 7, 8, 9, 10], "shoulder_months": [], "winter_multiplier": 0.85, "summer_multiplier": 1.15, "shoulder_multiplier": 1.0, }, "AEP Ohio": {}, "Nebraska Public Power District": { "energy_rates": {"off_peak": 19.3, "mid_peak": 19.3, "peak": 34.4}, "demand_charge": 19.0, "tou_periods": default_utility_params["tou_periods_filled"], "seasonal_rates": True, "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], "summer_months": [6, 7, 8, 9], "shoulder_months": [], "winter_multiplier": 0.9, "summer_multiplier": 1.1, "shoulder_multiplier": 1.0, }, "Rocky Mountain Power": { "energy_rates": {"off_peak": 24.7, "mid_peak": 24.7, "peak": 48.5}, "demand_charge": 15.79, "tou_periods": [(0, 6, "off_peak"), (6, 9, "peak"), (9, 15, "off_peak"), (15, 22, "peak"), (22, 24, "off_peak")], "seasonal_rates": True, "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], "summer_months": [6, 7, 8, 9], "shoulder_months": [], "winter_multiplier": 0.95, "summer_multiplier": 1.05, "shoulder_multiplier": 1.0, }, "Seattle City Light": { "energy_rates": {"off_peak": 55.30, "mid_peak": 55.30, "peak": 110.70}, "demand_charge": 5.13, "tou_periods": [(0, 6, "off_peak"), (6, 22, "peak"), (22, 24, "off_peak")], "seasonal_rates": False, "winter_months": default_utility_params["winter_months"], "summer_months": default_utility_params["summer_months"], "shoulder_months": default_utility_params["shoulder_months"], "winter_multiplier": 1.0, "summer_multiplier": 1.0, "shoulder_multiplier": 1.0, }, "Evergy": { "energy_rates": {"off_peak": 32.59, "mid_peak": 37.19, "peak": 53.91}, "demand_charge": 9.69, "tou_periods": [(0, 24, "off_peak")], "seasonal_rates": True, "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], "summer_months": [6, 7, 8, 9], "shoulder_months": [], "winter_multiplier": 0.69, "summer_multiplier": 1.31, "shoulder_multiplier": 1.0, }, "Duke Energy Florida": {}, "Entergy Mississippi (Assumed)": { "energy_rates": {"off_peak": 41.0, "mid_peak": 41.0, "peak": 67.0}, "demand_charge": 16.75, "tou_periods": [(0, 6, "off_peak"), (6, 10, "peak"), (10, 12, "off_peak"), (12, 20, "peak"), (20, 24, "off_peak")], "seasonal_rates": True, "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], "summer_months": [6, 7, 8, 9], "shoulder_months": [], "winter_multiplier": 0.84, "summer_multiplier": 1.16, "shoulder_multiplier": 1.0, }, "Custom Utility": default_utility_params, }
placeholder_utilities = [ "Kentucky Utilities", "Oncor Electric Delivery", "AEP Ohio", "Duke Energy Florida", ]
for util_key in placeholder_utilities:
    if util_key in utility_rates:
        # Use update to merge defaults, preserving any existing keys if needed
        # For simple cases, direct assignment is fine:
        utility_rates[util_key] = utility_rates["Custom Utility"].copy()


# --- Helper Functions (keep fill_tou_gaps, get_month_season_multiplier, calculate_eaf_profile, calculate_grid_bess_power) ---
# ... (Helper functions remain the same) ...
def fill_tou_gaps(periods):
    if not periods: return [(0.0, 24.0, "off_peak")]
    clean_periods = []
    for period in periods:
        try:
            if len(period) == 3:
                start, end, rate = float(period[0]), float(period[1]), str(period[2])
                if 0 <= start < end <= 24: clean_periods.append((start, end, rate))
                else: print(f"Warning: Skipping invalid TOU period data: {period}")
            else: print(f"Warning: Skipping malformed TOU period data: {period}")
        except (TypeError, ValueError, IndexError): print(f"Warning: Skipping invalid TOU period data: {period}"); continue
    clean_periods.sort(key=lambda x: x[0])
    for i in range(len(clean_periods) - 1):
        if clean_periods[i][1] > clean_periods[i + 1][0]: print(f"Warning: Overlapping TOU periods detected between {clean_periods[i]} and {clean_periods[i+1]}.")
    filled_periods = []; current_time = 0.0
    for start, end, rate in clean_periods:
        if start > current_time: filled_periods.append((current_time, start, "off_peak"))
        filled_periods.append((start, end, rate)); current_time = end
    if current_time < 24.0: filled_periods.append((current_time, 24.0, "off_peak"))
    if not filled_periods: filled_periods.append((0.0, 24.0, "off_peak"))
    return filled_periods

def get_month_season_multiplier(month, seasonal_data):
    if not seasonal_data.get("seasonal_rates", False): return 1.0
    if month in seasonal_data.get("winter_months", []): return seasonal_data.get("winter_multiplier", 1.0)
    elif month in seasonal_data.get("summer_months", []): return seasonal_data.get("summer_multiplier", 1.0)
    elif month in seasonal_data.get("shoulder_months", []): return seasonal_data.get("shoulder_multiplier", 1.0)
    else: print(f"Warning: Month {month} not found in any defined season. Using multiplier 1.0."); return 1.0

def calculate_eaf_profile(time_minutes, eaf_size=100, cycle_duration=36):
    if cycle_duration <= 0: return np.zeros_like(time_minutes)
    eaf_power = np.zeros_like(time_minutes); scale = (eaf_size / 100) ** 0.6 if eaf_size > 0 else 0
    ref_duration = 28.0; bore_in_end_frac = 3 / ref_duration; main_melting_end_frac = 17 / ref_duration; melting_end_frac = 20 / ref_duration
    for i, t_actual in enumerate(time_minutes):
        t_norm_actual_cycle = t_actual / cycle_duration if cycle_duration > 0 else 0
        freq_scale = ref_duration / cycle_duration if cycle_duration > 0 else 1
        if t_norm_actual_cycle <= bore_in_end_frac:
            phase_progress = t_norm_actual_cycle / bore_in_end_frac if bore_in_end_frac > 0 else 0
            eaf_power[i] = (15 + (25 - 15) * phase_progress) * scale
        elif t_norm_actual_cycle <= main_melting_end_frac:
            eaf_power[i] = (55 + 5 * np.sin(t_actual * 0.5 * freq_scale)) * scale
        elif t_norm_actual_cycle <= melting_end_frac:
            phase_progress = ((t_norm_actual_cycle - main_melting_end_frac) / (melting_end_frac - main_melting_end_frac)) if (melting_end_frac > main_melting_end_frac) else 0
            eaf_power[i] = (50 - (50 - 40) * phase_progress) * scale
        else:
            eaf_power[i] = (20 + 5 * np.sin(t_actual * 0.3 * freq_scale)) * scale
    return eaf_power

def calculate_grid_bess_power(eaf_power, grid_cap, bess_power_max):
    grid_power = np.zeros_like(eaf_power); bess_power = np.zeros_like(eaf_power)
    grid_cap = max(0, grid_cap); bess_power_max = max(0, bess_power_max)
    for i, p_eaf in enumerate(eaf_power):
        p_eaf = max(0, p_eaf)
        if p_eaf > grid_cap:
            discharge_needed = p_eaf - grid_cap; actual_discharge = min(discharge_needed, bess_power_max)
            bess_power[i] = actual_discharge; grid_power[i] = p_eaf - actual_discharge
        else: grid_power[i] = p_eaf; bess_power[i] = 0
    return grid_power, bess_power


# --- Billing Calculation Functions (keep as is for now, financial calcs will use new params) ---
# ... (create_monthly_bill_with_bess, create_monthly_bill_without_bess, calculate_annual_billings remain the same for now) ...
# Note: These functions primarily use EAF params, Utility params, and BESS power_max.
# The detailed BESS cost/performance affects the *financial* outcome, not the raw billing simulation here.
def create_monthly_bill_with_bess(eaf_params, bess_params, utility_params, days_in_month, month_number):
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)
    energy_rates = {r: rate * seasonal_mult for r, rate in utility_params.get("energy_rates", {}).items()}
    demand_charge = utility_params.get("demand_charge", 0) * seasonal_mult
    filled_tou_periods = utility_params.get("tou_periods_filled", [(0.0, 24.0, "off_peak")])
    eaf_size = eaf_params.get("eaf_size", 100)
    cycle_duration_min = eaf_params.get("cycle_duration_input", eaf_params.get("cycle_duration", 36))
    if cycle_duration_min <= 0: cycle_duration_min = 36
    time_step_min = cycle_duration_min / 200; time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min)
    grid_cap = eaf_params.get("grid_cap", 50); bess_power_max = bess_params.get("power_max", 20) # Use overall power_max
    grid_power_cycle, bess_power_cycle = calculate_grid_bess_power(eaf_power_cycle, grid_cap, bess_power_max)
    peak_demand_kw = np.max(grid_power_cycle) * 1000 if len(grid_power_cycle) > 0 else 0
    bess_energy_cycle_discharged = np.sum(bess_power_cycle) * (time_step_min / 60)
    grid_energy_cycle = np.sum(grid_power_cycle) * (time_step_min / 60)
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}; total_energy_cost = 0; total_grid_energy_month = 0
    cycles_per_day = eaf_params.get("cycles_per_day", 24)
    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start; period_fraction = period_hours / 24.0
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month
            period_cost = energy_in_period_month * energy_rates[period]
            tou_energy_costs[period] += period_cost; total_energy_cost += period_cost; total_grid_energy_month += energy_in_period_month
        else: print(f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict.")
    demand_cost = peak_demand_kw * demand_charge; total_bill = total_energy_cost + demand_cost
    return {"energy_cost": total_energy_cost, "demand_cost": demand_cost, "total_bill": total_bill, "peak_demand_kw": peak_demand_kw, "energy_consumed_mwh": total_grid_energy_month, "tou_breakdown": tou_energy_costs, "bess_discharged_per_cycle_mwh": bess_energy_cycle_discharged}

def create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month_number):
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)
    energy_rates = {r: rate * seasonal_mult for r, rate in utility_params.get("energy_rates", {}).items()}
    demand_charge = utility_params.get("demand_charge", 0) * seasonal_mult
    filled_tou_periods = utility_params.get("tou_periods_filled", [(0.0, 24.0, "off_peak")])
    eaf_size = eaf_params.get("eaf_size", 100)
    cycle_duration_min = eaf_params.get("cycle_duration_input", eaf_params.get("cycle_duration", 36))
    if cycle_duration_min <= 0: cycle_duration_min = 36
    time_step_min = cycle_duration_min / 200; time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min)
    grid_power_cycle = eaf_power_cycle
    peak_demand_kw = np.max(grid_power_cycle) * 1000 if len(grid_power_cycle) > 0 else 0
    grid_energy_cycle = np.sum(grid_power_cycle) * (time_step_min / 60)
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}; total_energy_cost = 0; total_grid_energy_month = 0
    cycles_per_day = eaf_params.get("cycles_per_day", 24)
    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start; period_fraction = period_hours / 24.0
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month
            period_cost = energy_in_period_month * energy_rates[period]
            tou_energy_costs[period] += period_cost; total_energy_cost += period_cost; total_grid_energy_month += energy_in_period_month
        else: print(f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict.")
    demand_cost = peak_demand_kw * demand_charge; total_bill = total_energy_cost + demand_cost
    return {"energy_cost": total_energy_cost, "demand_cost": demand_cost, "total_bill": total_bill, "peak_demand_kw": peak_demand_kw, "energy_consumed_mwh": total_grid_energy_month, "tou_breakdown": tou_energy_costs}

def calculate_annual_billings(eaf_params, bess_params, utility_params):
    monthly_bills_with_bess = []; monthly_bills_without_bess = []; monthly_savings = []
    year = 2025
    if "tou_periods_filled" not in utility_params or not utility_params["tou_periods_filled"]:
        raw_periods = utility_params.get("tou_periods_raw", default_utility_params["tou_periods_raw"])
        utility_params["tou_periods_filled"] = fill_tou_gaps(raw_periods)
        print("Warning: Filled TOU periods were missing, generated them.")
    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]
        bill_with_bess = create_monthly_bill_with_bess(eaf_params, bess_params, utility_params, days_in_month, month)
        bill_without_bess = create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month)
        savings = bill_without_bess["total_bill"] - bill_with_bess["total_bill"]
        monthly_bills_with_bess.append(bill_with_bess); monthly_bills_without_bess.append(bill_without_bess); monthly_savings.append(savings)
    annual_bill_with_bess = sum(bill["total_bill"] for bill in monthly_bills_with_bess)
    annual_bill_without_bess = sum(bill["total_bill"] for bill in monthly_bills_without_bess)
    annual_savings = sum(monthly_savings)
    return {"monthly_bills_with_bess": monthly_bills_with_bess, "monthly_bills_without_bess": monthly_bills_without_bess, "monthly_savings": monthly_savings, "annual_bill_with_bess": annual_bill_with_bess, "annual_bill_without_bess": annual_bill_without_bess, "annual_savings": annual_savings}


# --- Incentive Calculation Function ---
# Needs modification to calculate total_cost based on new parameters
def calculate_incentives(bess_params, incentive_params):
    """Calculate total incentives based on selected programs."""
    total_incentive = 0
    incentive_breakdown = {}

    # --- Calculate Initial BESS Cost from components ---
    capacity_mwh = bess_params.get("capacity", 0)
    power_mw = bess_params.get("power_max", 0)
    capacity_kwh = capacity_mwh * 1000
    power_kw = power_mw * 1000

    sb_bos_cost = bess_params.get("sb_bos_cost_per_kwh", 0) * capacity_kwh
    pcs_cost = bess_params.get("pcs_cost_per_kw", 0) * power_kw
    epc_cost = bess_params.get("epc_cost_per_kwh", 0) * capacity_kwh
    sys_int_cost = bess_params.get("sys_integration_cost_per_kwh", 0) * capacity_kwh

    # Summing component costs for total initial capital cost
    # Note: This is a simplified sum. Real project costs involve more nuance.
    total_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost
    # --- End Cost Calculation ---


    def get_incentive_param(key, default): return incentive_params.get(key, default)

    itc_enabled = get_incentive_param("itc_enabled", False); itc_perc = get_incentive_param("itc_percentage", 30) / 100.0
    itc_amount = total_cost * itc_perc if itc_enabled else 0
    ceic_enabled = get_incentive_param("ceic_enabled", False); ceic_perc = get_incentive_param("ceic_percentage", 30) / 100.0
    ceic_amount = total_cost * ceic_perc if ceic_enabled else 0
    bonus_enabled = get_incentive_param("bonus_credit_enabled", False); bonus_perc = get_incentive_param("bonus_credit_percentage", 10) / 100.0
    bonus_amount = total_cost * bonus_perc if bonus_enabled else 0
    sgip_enabled = get_incentive_param("sgip_enabled", False); sgip_rate = get_incentive_param("sgip_amount", 400)
    sgip_amount = capacity_kwh * sgip_rate if sgip_enabled else 0
    ess_enabled = get_incentive_param("ess_enabled", False); ess_rate = get_incentive_param("ess_amount", 280)
    ess_amount = capacity_kwh * ess_rate if ess_enabled else 0
    mabi_enabled = get_incentive_param("mabi_enabled", False); mabi_rate = get_incentive_param("mabi_amount", 250)
    mabi_amount = capacity_kwh * mabi_rate if mabi_enabled else 0
    cs_enabled = get_incentive_param("cs_enabled", False); cs_rate = get_incentive_param("cs_amount", 225)
    cs_amount = capacity_kwh * cs_rate if cs_enabled else 0
    custom_enabled = get_incentive_param("custom_incentive_enabled", False); custom_type = get_incentive_param("custom_incentive_type", "per_kwh")
    custom_rate = get_incentive_param("custom_incentive_amount", 100); custom_desc = get_incentive_param("custom_incentive_description", "Custom")
    custom_amount = 0
    if custom_enabled:
        if custom_type == "per_kwh": custom_amount = capacity_kwh * custom_rate
        elif custom_type == "percentage": custom_amount = total_cost * (custom_rate / 100.0)

    applied_federal_base = 0; federal_base_desc = ""
    if itc_enabled and ceic_enabled:
        if itc_amount >= ceic_amount: applied_federal_base = itc_amount; federal_base_desc = "Investment Tax Credit (ITC)"
        else: applied_federal_base = ceic_amount; federal_base_desc = "Clean Electricity Investment Credit (CEIC)"
    elif itc_enabled: applied_federal_base = itc_amount; federal_base_desc = "Investment Tax Credit (ITC)"
    elif ceic_enabled: applied_federal_base = ceic_amount; federal_base_desc = "Clean Electricity Investment Credit (CEIC)"

    if applied_federal_base > 0: total_incentive += applied_federal_base; incentive_breakdown[federal_base_desc] = applied_federal_base
    if bonus_amount > 0: total_incentive += bonus_amount; incentive_breakdown["Bonus Credits"] = bonus_amount
    if sgip_amount > 0: total_incentive += sgip_amount; incentive_breakdown["CA Self-Generation Incentive Program"] = sgip_amount
    if ess_amount > 0: total_incentive += ess_amount; incentive_breakdown["CT Energy Storage Solutions"] = ess_amount
    if mabi_amount > 0: total_incentive += mabi_amount; incentive_breakdown["NY Market Acceleration Bridge Incentive"] = mabi_amount
    if cs_amount > 0: total_incentive += cs_amount; incentive_breakdown["MA Connected Solutions"] = cs_amount
    if custom_amount > 0: total_incentive += custom_amount; incentive_breakdown[custom_desc] = custom_amount

    return {"total_incentive": total_incentive, "breakdown": incentive_breakdown, "calculated_initial_cost": total_cost}


# --- Financial Metrics Calculation Function ---
# Needs significant modification to use new parameters
def calculate_financial_metrics(
    bess_params, financial_params, eaf_params, annual_savings, incentives_results
):
    """Calculate NPV, IRR, payback period, etc. using detailed BESS parameters."""

    # --- Get Parameters ---
    # BESS Parameters from store
    capacity_mwh = bess_params.get("capacity", 0)
    power_mw = bess_params.get("power_max", 0)
    capacity_kwh = capacity_mwh * 1000
    power_kw = power_mw * 1000

    sb_bos_cost_per_kwh = bess_params.get("sb_bos_cost_per_kwh", 0)
    pcs_cost_per_kw = bess_params.get("pcs_cost_per_kw", 0)
    epc_cost_per_kwh = bess_params.get("epc_cost_per_kwh", 0)
    sys_int_cost_per_kwh = bess_params.get("sys_integration_cost_per_kwh", 0)

    # Opex params
    fixed_om_per_kw_yr = bess_params.get("fixed_om_per_kw_yr", 0)
    om_cost_per_kwh_yr = bess_params.get("om_cost_per_kwh_yr", None) # Specific for supercap
    insurance_percent_yr = bess_params.get("insurance_percent_yr", 0)

    # Decommissioning params
    disconnect_cost_per_kwh = bess_params.get("disconnect_cost_per_kwh", 0)
    recycling_cost_per_kwh = bess_params.get("recycling_cost_per_kwh", 0) # Can be negative

    # Performance params
    cycle_life = bess_params.get("cycle_life", 5000)
    calendar_life = bess_params.get("calendar_life", 15) # Years
    # Note: RTE is not directly used in cash flow calc, but affects savings which is an input
    # Note: DoD affects how cycle life translates to years, handled below

    # Financial Parameters
    years = int(financial_params.get("project_lifespan", 30))
    wacc = financial_params.get("wacc", 0.131)
    inflation_rate = financial_params.get("inflation_rate", 0.024)
    tax_rate = financial_params.get("tax_rate", 0.2009)
    # Salvage value is replaced by decommissioning costs

    # EAF Parameters for battery life calculation
    days_per_year = eaf_params.get("days_per_year", 300)
    cycles_per_day = eaf_params.get("cycles_per_day", 24) # Assuming 1 cycle = 1 full DoD equiv discharge/charge

    # --- Initial Calculations ---
    # Calculate Initial Capital Cost (same as in calculate_incentives)
    sb_bos_cost = sb_bos_cost_per_kwh * capacity_kwh
    pcs_cost = pcs_cost_per_kw * power_kw
    epc_cost = epc_cost_per_kwh * capacity_kwh
    sys_int_cost = sys_int_cost_per_kwh * capacity_kwh
    total_initial_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost

    # Net Initial Cost (Year 0)
    net_initial_cost = total_initial_cost - incentives_results.get("total_incentive", 0)
    if net_initial_cost < 0: print("Warning: Total incentives exceed calculated initial BESS cost.")

    # Calculate Annual O&M Cost (Year 1)
    fixed_om_cost = fixed_om_per_kw_yr * power_kw
    # Handle supercap specific O&M
    if om_cost_per_kwh_yr is not None:
         om_kwh_cost = om_cost_per_kwh_yr * capacity_kwh
         initial_om_cost = om_kwh_cost # Use this if provided
    else:
         initial_om_cost = fixed_om_cost # Otherwise use fixed $/kW/yr

    insurance_cost = (insurance_percent_yr / 100.0) * total_initial_cost # Insurance based on gross cost
    total_initial_om_cost = initial_om_cost + insurance_cost

    # --- Battery Life & Replacement Calculation ---
    if days_per_year <= 0 or cycles_per_day <= 0 or cycle_life <= 0:
        cycles_per_year_equiv = 0
        battery_life_years_cycles = float('inf')
    else:
        # Assuming cycles_per_day represents equivalent full DoD cycles
        cycles_per_year_equiv = cycles_per_day * days_per_year
        battery_life_years_cycles = cycle_life / cycles_per_year_equiv if cycles_per_year_equiv > 0 else float('inf')

    # Effective battery life is minimum of calendar and cycle life
    battery_replacement_interval = min(calendar_life, battery_life_years_cycles)
    if battery_replacement_interval <= 0: battery_replacement_interval = float('inf') # Avoid division by zero if life is 0

    # --- Cash Flow Calculation Loop ---
    cash_flows = [-net_initial_cost]  # Year 0: Net initial investment

    for year in range(1, years + 1):
        # Inflated Savings and O&M Costs
        savings_t = annual_savings * ((1 + inflation_rate) ** (year - 1))
        o_m_cost_t = total_initial_om_cost * ((1 + inflation_rate) ** (year - 1))

        # Recurring Replacement Cost Logic
        replacement_cost_year = 0
        # Check if a replacement is due *at the beginning* of this year
        if battery_replacement_interval != float('inf') and year > 1 and np.isclose((year - 1) % battery_replacement_interval, 0):
             # Replacement cost is the *original* total cost, inflated to the replacement year
             # Assume no incentives on replacements
             inflated_replacement_cost = total_initial_cost * ((1 + inflation_rate) ** (year - 1))
             replacement_cost_year = inflated_replacement_cost
             # print(f"DEBUG: Battery replacement cost ${replacement_cost_year:,.0f} applied in year {year}")

        # EBT (Earnings Before Tax) - Simplified (no depreciation modeled here)
        ebt = savings_t - o_m_cost_t - replacement_cost_year

        # Taxes
        taxes = ebt * tax_rate if ebt > 0 else 0

        # Net Cash Flow (After Tax, Before Decommissioning)
        net_cash_flow = savings_t - o_m_cost_t - replacement_cost_year - taxes

        # Decommissioning Costs (Applied ONLY in the final year)
        if year == years:
            # Calculate decommissioning cost (Disconnect + Recycling)
            decomm_cost_base = (disconnect_cost_per_kwh + recycling_cost_per_kwh) * capacity_kwh
            # Inflate decommissioning cost to the final year
            inflated_decomm_cost = decomm_cost_base * ((1 + inflation_rate) ** (year - 1))
            # Assume decommissioning cost is tax-deductible (reduces tax burden or is an expense)
            # This is complex - simplest is to treat it as an after-tax cash outflow
            decomm_cost_after_tax = inflated_decomm_cost # Simplification: treat as direct outflow
            # print(f"DEBUG: Decommissioning Cost: Base=${decomm_cost_base:,.0f}, Applied=${decomm_cost_after_tax:,.0f} in year {year}")

            net_cash_flow -= decomm_cost_after_tax # Subtract cost in final year

        cash_flows.append(net_cash_flow)
    # --- End of Cash Flow Loop ---

    # --- Calculate Financial Metrics ---
    npv_val = float('nan'); irr_val = float('nan')
    try:
        if wacc > -1: npv_val = npf.npv(wacc, cash_flows)
        else: print("Warning: WACC <= -1, cannot calculate NPV.")
    except Exception as e: print(f"Error calculating NPV: {e}")

    try:
        if cash_flows and len(cash_flows) > 1 and cash_flows[0] < 0 and any(cf > 0 for cf in cash_flows[1:]):
            irr_val = npf.irr(cash_flows)
            if irr_val is None or np.isnan(irr_val): irr_val = float("nan")
        else: irr_val = float('nan')
    except Exception as e: print(f"Error calculating IRR: {e}"); irr_val = float('nan')

    # --- Payback Period Calculation ---
    cumulative_cash_flow = cash_flows[0]; payback_years = float('inf')
    if cumulative_cash_flow >= 0: payback_years = 0.0
    else:
        for year_pbk in range(1, len(cash_flows)):
            current_year_cf = cash_flows[year_pbk]
            if cumulative_cash_flow + current_year_cf >= 0:
                fraction_needed = abs(cumulative_cash_flow) / current_year_cf if current_year_cf > 0 else 0
                payback_years = (year_pbk - 1) + fraction_needed
                break
            cumulative_cash_flow += current_year_cf

    return {
        "npv": npv_val,
        "irr": irr_val,
        "payback_years": payback_years,
        "cash_flows": cash_flows,
        "net_initial_cost": net_initial_cost,
        "total_initial_cost": total_initial_cost, # Gross cost before incentives
        "battery_life_years": battery_replacement_interval, # Effective life used for replacement
        "annual_savings_year1": annual_savings,
        "initial_om_cost_year1": total_initial_om_cost,
    }


# --- Optimization Function (Needs update to pass base params correctly) ---
def optimize_battery_size(
    eaf_params, utility_params, financial_params, incentive_params, bess_base_params # bess_base_params now contains tech-specific costs/perf
):
    """Find optimal battery size (Capacity MWh, Power MW) for best ROI using NPV as metric"""
    capacity_options = np.linspace(5, 100, 10)
    power_options = np.linspace(2, 50, 10)
    best_npv = -float("inf"); best_capacity = None; best_power = None; best_metrics = None
    optimization_results = []
    print(f"Starting optimization: {len(capacity_options)} capacities, {len(power_options)} powers...")
    count = 0; total_combinations = len(capacity_options) * len(power_options)

    for capacity in capacity_options:
        for power in power_options:
            count += 1
            print(f"  Testing {count}/{total_combinations}: Cap={capacity:.1f} MWh, Pow={power:.1f} MW")
            c_rate = power / capacity if capacity > 0 else float("inf")
            if not (0.2 <= c_rate <= 2.5):
                print(f"    Skipping C-rate {c_rate:.2f} (out of range 0.2-2.5)")
                continue

            # Create test BESS parameters: Start with base tech params, override size
            test_bess_params = bess_base_params.copy()
            test_bess_params["capacity"] = capacity
            test_bess_params["power_max"] = power

            try:
                billing_results = calculate_annual_billings(eaf_params, test_bess_params, utility_params)
                annual_savings = billing_results["annual_savings"]
                # Pass the *test* params (with size) to incentives calc
                incentive_results = calculate_incentives(test_bess_params, incentive_params)
                # Pass the *test* params (with size) to financial calc
                metrics = calculate_financial_metrics(test_bess_params, financial_params, eaf_params, annual_savings, incentive_results)

                current_result = {
                    "capacity": capacity, "power": power, "npv": metrics["npv"], "irr": metrics["irr"],
                    "payback_years": metrics["payback_years"], "annual_savings": annual_savings,
                    "net_initial_cost": metrics["net_initial_cost"],
                }
                optimization_results.append(current_result)

                if pd.notna(metrics["npv"]) and metrics["npv"] > best_npv:
                    best_npv = metrics["npv"]; best_capacity = capacity; best_power = power
                    best_metrics = metrics # Store full metrics for the best combo
                    print(f"    *** New best NPV found: ${best_npv:,.0f} ***")

            except Exception as e:
                print(f"    Error during optimization step (Cap={capacity:.1f}, Pow={power:.1f}): {e}")
                optimization_results.append({"capacity": capacity, "power": power, "npv": float("nan"), "error": str(e)})

    print("Optimization finished.")
    return {"best_capacity": best_capacity, "best_power": best_power, "best_npv": best_npv, "best_metrics": best_metrics, "all_results": optimization_results}


# --- Application Layout ---
# Helper function to create input groups for BESS parameters
def create_bess_input_group(label, input_id, value, unit, type="number", step=None, min_val=0):
    return dbc.Row(
        [
            dbc.Label(label, html_for=input_id, width=6),
            dbc.Col(
                dcc.Input(
                    id=input_id, type=type, value=value, className="form-control form-control-sm",
                    step=step, min=min_val
                ),
                width=4,
            ),
            dbc.Col(html.Span(unit, className="input-group-text input-group-text-sm"), width=2) # Simple span for unit
        ],
        className="mb-2 align-items-center",
    )

app.layout = dbc.Container(fluid=True, className="bg-light min-vh-100 py-4", children=[
    # Stores
    dcc.Store(id="eaf-params-store", data=nucor_mills["Custom"]),
    dcc.Store(id="utility-params-store", data=utility_rates["Custom Utility"]),
    dcc.Store(id="bess-params-store", data=default_bess_params_store), # Use new default
    dcc.Store(id="financial-params-store", data=default_financial_params),
    dcc.Store(id="incentive-params-store", data=default_incentive_params),
    dcc.Store(id="calculation-results-store", data={}),
    dcc.Store(id="optimization-results-store", data={}),

    html.H1("Battery Profitability Tool", className="mb-4 text-center"),
    # Error Containers
    dbc.Alert(id="validation-error-container", color="danger", is_open=False, style={"max-width": "800px", "margin": "10px auto"}),
    dbc.Alert(id="calculation-error-container", color="warning", is_open=False, style={"max-width": "800px", "margin": "10px auto"}),

    # Tabs
    dbc.Tabs(id="main-tabs", active_tab="tab-mill", children=[
        # Mill Selection Tab (keep as is)
        dbc.Tab(label="1. Mill Selection", tab_id="tab-mill", children=[
             dbc.Container(py=4, children=[
                html.H3("Select Nucor Mill", className="mb-3"),
                html.P("Choose a mill to pre-fill parameters, or select 'Custom' to enter values manually.", className="text-muted mb-4"),
                html.Div([
                    html.Label("Mill Selection:", className="form-label"),
                    dcc.Dropdown(id="mill-selection-dropdown", options=[{"label": f"Nucor Steel {mill}", "value": mill} for mill in nucor_mills.keys()], value="Custom", clearable=False, className="form-select mb-3"),
                ], className="mb-4"),
                dbc.Card(id="mill-info-card", className="mb-4"),
                html.Div(dbc.Button("Continue to Parameters", id="continue-to-params-button", n_clicks=0, color="primary", className="mt-3"), className="d-flex justify-content-center"),
             ])
        ]), # End Tab 1

        # Parameters Tab (Modify BESS section)
        dbc.Tab(label="2. System Parameters", tab_id="tab-params", children=[
            dbc.Container(py=4, children=[
                dbc.Row([
                    # Left Column: Utility & EAF (keep as is)
                    dbc.Col(md=6, children=[
                        dbc.Card(className="p-3 mb-4", children=[ # Utility Card
                            html.H4("Utility Rates", className="mb-3"),
                            html.Div([ html.Label("Utility Provider:", className="form-label"), dcc.Dropdown(id="utility-provider-dropdown", options=[{"label": utility, "value": utility} for utility in utility_rates.keys()], value="Custom Utility", clearable=False, className="form-select mb-3"), ], className="mb-3"),
                            html.Div([ html.Label("Off-Peak Rate ($/MWh):", className="form-label"), dcc.Input(id="off-peak-rate", type="number", value=default_utility_params["energy_rates"]["off_peak"], min=0, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Mid-Peak Rate ($/MWh):", className="form-label"), dcc.Input(id="mid-peak-rate", type="number", value=default_utility_params["energy_rates"]["mid_peak"], min=0, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Peak Rate ($/MWh):", className="form-label"), dcc.Input(id="peak-rate", type="number", value=default_utility_params["energy_rates"]["peak"], min=0, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Demand Charge ($/kW/month):", className="form-label"), dcc.Input(id="demand-charge", type="number", value=default_utility_params["demand_charge"], min=0, className="form-control"), ], className="mb-2"),
                            dbc.Checklist(id="seasonal-rates-toggle", options=[{"label": "Enable Seasonal Rate Variations", "value": "enabled"}], value=["enabled"] if default_utility_params["seasonal_rates"] else [], switch=True, className="mb-3"),
                            html.Div(id="seasonal-rates-container", className="mb-3 border p-2 rounded", style={"display": "none"}),
                            html.H5("Time-of-Use Periods", className="mb-2"),
                            html.P("Define periods covering 24 hours. Gaps will be filled with Off-Peak.", className="small text-muted"),
                            html.Div(id="tou-periods-container"),
                            dbc.Button("Add TOU Period", id="add-tou-period-button", n_clicks=0, size="sm", outline=True, color="success", className="mt-2"),
                        ]),
                        dbc.Card(className="p-3", children=[ # EAF Card
                            html.H4("EAF Parameters", className="mb-3"),
                            html.Div([ html.Label("EAF Size (tons):", className="form-label"), dcc.Input(id="eaf-size", type="number", value=nucor_mills["Custom"]["eaf_size"], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Number of EAFs:", className="form-label"), dcc.Input(id="eaf-count", type="number", value=nucor_mills["Custom"]["eaf_count"], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Grid Power Limit (MW):", className="form-label"), dcc.Input(id="grid-cap", type="number", value=nucor_mills["Custom"]["grid_cap"], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("EAF Cycles per Day:", className="form-label"), dcc.Input(id="cycles-per-day", type="number", value=nucor_mills["Custom"]["cycles_per_day"], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Avg. Cycle Duration (minutes):", className="form-label"), dcc.Input(id="cycle-duration", type="number", value=nucor_mills["Custom"]["cycle_duration"], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Operating Days per Year:", className="form-label"), dcc.Input(id="days-per-year", type="number", value=nucor_mills["Custom"]["days_per_year"], min=1, max=366, className="form-control"), ], className="mb-2"),
                        ]),
                    ]), # End Left Column

                    # Right Column: BESS & Financial (Modify BESS)
                    dbc.Col(md=6, children=[
                        dbc.Card(className="p-3 mb-4", children=[ # BESS Card - MODIFIED
                            html.H4("BESS Parameters", className="mb-3"),
                            # --- Overall Size Inputs ---
                            create_bess_input_group("Total Energy Capacity:", "bess-capacity", default_bess_params_store['capacity'], "MWh", min_val=0.1),
                            create_bess_input_group("Total Power Rating:", "bess-power", default_bess_params_store['power_max'], "MW", min_val=0.1),
                            html.Hr(),
                            # --- Technology Selection ---
                            html.Div([
                                dbc.Label("Select BESS Technology:", html_for="bess-technology-dropdown"),
                                dcc.Dropdown(
                                    id="bess-technology-dropdown",
                                    options=[{'label': tech, 'value': tech} for tech in bess_technology_data.keys()],
                                    value=default_bess_params_store['technology'], # Default to LFP
                                    clearable=False,
                                    className="mb-2"
                                ),
                                html.P(id="bess-example-product", className="small text-muted fst-italic")
                            ], className="mb-3"),
                            html.Hr(),

                            # --- Detailed Parameters ---
                            dbc.Card([ # Capex Card
                                dbc.CardHeader("Capex"),
                                dbc.CardBody([
                                    create_bess_input_group("SB + BOS Cost:", "bess-sb-bos-cost", default_bess_params_store['sb_bos_cost_per_kwh'], "$/kWh"),
                                    create_bess_input_group("PCS Cost:", "bess-pcs-cost", default_bess_params_store['pcs_cost_per_kw'], "$/kW"),
                                    create_bess_input_group("System Integration:", "bess-sys-int-cost", default_bess_params_store['sys_integration_cost_per_kwh'], "$/kWh"),
                                    create_bess_input_group("EPC Cost:", "bess-epc-cost", default_bess_params_store['epc_cost_per_kwh'], "$/kWh"),
                                ])
                            ], className="mb-3"),

                            dbc.Card([ # Opex Card
                                dbc.CardHeader("Opex"),
                                dbc.CardBody([
                                    # Conditional O&M Input
                                    html.Div(id='bess-opex-inputs-container'),
                                    create_bess_input_group("Round Trip Efficiency:", "bess-rte", default_bess_params_store['rte_percent'], "%", min_val=1, max_val=100),
                                    create_bess_input_group("Insurance Rate:", "bess-insurance", default_bess_params_store['insurance_percent_yr'], "%/yr", step=0.01),
                                ])
                            ], className="mb-3"),

                            dbc.Card([ # Decommissioning Card
                                dbc.CardHeader("Decommissioning"),
                                dbc.CardBody([
                                    create_bess_input_group("Disconnect/Removal:", "bess-disconnect-cost", default_bess_params_store['disconnect_cost_per_kwh'], "$/kWh", min_val=None), # Allow negative later?
                                    create_bess_input_group("Recycling/Disposal:", "bess-recycling-cost", default_bess_params_store['recycling_cost_per_kwh'], "$/kWh", min_val=None), # Allow negative
                                ])
                            ], className="mb-3"),

                            dbc.Card([ # Performance Card
                                dbc.CardHeader("Performance"),
                                dbc.CardBody([
                                    create_bess_input_group("Cycle Life:", "bess-cycle-life", default_bess_params_store['cycle_life'], "cycles", min_val=100),
                                    create_bess_input_group("Depth of Discharge:", "bess-dod", default_bess_params_store['dod_percent'], "%", min_val=1, max_val=100),
                                    create_bess_input_group("Calendar Life:", "bess-calendar-life", default_bess_params_store['calendar_life'], "years", min_val=1),
                                ])
                            ]),
                        ]), # End BESS Card

                        dbc.Card(className="p-3", children=[ # Financial Card (keep as is)
                            html.H4("Financial Parameters", className="mb-3"),
                            html.Div([ html.Label("WACC (%):", className="form-label"), dcc.Input(id="wacc", type="number", value=round(default_financial_params["wacc"] * 100, 1), min=0, max=100, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Project Lifespan (years):", className="form-label"), dcc.Input(id="project-lifespan", type="number", value=default_financial_params["project_lifespan"], min=1, max=50, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Tax Rate (%):", className="form-label"), dcc.Input(id="tax-rate", type="number", value=default_financial_params["tax_rate"] * 100, min=0, max=100, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Inflation Rate (%):", className="form-label"), dcc.Input(id="inflation-rate", type="number", value=default_financial_params["inflation_rate"] * 100, min=-5, max=100, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Salvage Value (% of initial BESS cost):", className="form-label"), dcc.Input(id="salvage-value", type="number", value=default_financial_params["salvage_value"] * 100, min=0, max=100, className="form-control"), html.P("Note: Salvage value may be overridden by decommissioning costs.", className="small text-muted")], className="mb-2"),
                        ]), # End Financial Card
                    ]), # End Right Column
                ]), # End Param Row
                html.Div(dbc.Button("Continue to Incentives", id="continue-to-incentives-button", n_clicks=0, color="primary", className="mt-4 mb-3"), className="d-flex justify-content-center"),
            ])
        ]), # End Tab 2

        # Incentives Tab (keep as is)
        dbc.Tab(label="3. Battery Incentives", tab_id="tab-incentives", children=[
            dbc.Container(py=4, children=[
                 html.H3("Battery Incentive Programs", className="mb-4 text-center"),
                 html.P("Select applicable incentives. Ensure values are correct for your location/project.", className="text-muted mb-4 text-center"),
                 # ... (Incentive layout remains the same) ...
                 dbc.Row([
                     dbc.Col(md=6, children=[ # Federal
                         dbc.Card(className="p-3 mb-4", children=[
                             html.H4("Federal Incentives", className="mb-3"),
                             html.Div([ dbc.Checklist(id="itc-enabled", options=[{"label": " Investment Tax Credit (ITC)", "value": "enabled"}], value=["enabled"] if default_incentive_params["itc_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("ITC Percentage (%):", html_for="itc-percentage", size="sm"), dcc.Input(id="itc-percentage", type="number", value=default_incentive_params["itc_percentage"], min=0, max=100, className="form-control form-control-sm"), ], className="mb-2 ms-4"), html.P("Tax credit on capital expenditure.", className="text-muted small ms-4"), ], className="mb-3"),
                             html.Div([ dbc.Checklist(id="ceic-enabled", options=[{"label": " Clean Electricity Investment Credit (CEIC)", "value": "enabled"}], value=["enabled"] if default_incentive_params["ceic_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("CEIC Percentage (%):", html_for="ceic-percentage", size="sm"), dcc.Input(id="ceic-percentage", type="number", value=default_incentive_params["ceic_percentage"], min=0, max=100, className="form-control form-control-sm"), ], className="mb-2 ms-4"), html.P("Mutually exclusive with ITC; higher value applies.", className="text-muted small ms-4"), ], className="mb-3"),
                             html.Div([ dbc.Checklist(id="bonus-credit-enabled", options=[{"label": " Bonus Credits (Energy Communities, Domestic Content)", "value": "enabled"}], value=["enabled"] if default_incentive_params["bonus_credit_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("Bonus Percentage (%):", html_for="bonus-credit-percentage", size="sm"), dcc.Input(id="bonus-credit-percentage", type="number", value=default_incentive_params["bonus_credit_percentage"], min=0, max=100, className="form-control form-control-sm"), ], className="mb-2 ms-4"), html.P("Stacks with ITC/CEIC.", className="text-muted small ms-4"), ], className="mb-3"),
                         ])
                     ]),
                     dbc.Col(md=6, children=[ # State & Custom
                         dbc.Card(className="p-3 mb-4", children=[ # State
                             html.H4("State Incentives (Examples)", className="mb-3"),
                             html.Div([ dbc.Checklist(id="sgip-enabled", options=[{"label": " CA Self-Generation Incentive Program (SGIP)", "value": "enabled"}], value=["enabled"] if default_incentive_params["sgip_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("SGIP Amount ($/kWh):", html_for="sgip-amount", size="sm"), dcc.Input(id="sgip-amount", type="number", value=default_incentive_params["sgip_amount"], min=0, className="form-control form-control-sm"), ], className="mb-2 ms-4"), ], className="mb-3"),
                             html.Div([ dbc.Checklist(id="ess-enabled", options=[{"label": " CT Energy Storage Solutions", "value": "enabled"}], value=["enabled"] if default_incentive_params["ess_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("ESS Amount ($/kWh):", html_for="ess-amount", size="sm"), dcc.Input(id="ess-amount", type="number", value=default_incentive_params["ess_amount"], min=0, className="form-control form-control-sm"), ], className="mb-2 ms-4"), ], className="mb-3"),
                             html.Div([ dbc.Checklist(id="mabi-enabled", options=[{"label": " NY Market Acceleration Bridge Incentive", "value": "enabled"}], value=["enabled"] if default_incentive_params["mabi_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("MABI Amount ($/kWh):", html_for="mabi-amount", size="sm"), dcc.Input(id="mabi-amount", type="number", value=default_incentive_params["mabi_amount"], min=0, className="form-control form-control-sm"), ], className="mb-2 ms-4"), ], className="mb-3"),
                             html.Div([ dbc.Checklist(id="cs-enabled", options=[{"label": " MA Connected Solutions", "value": "enabled"}], value=["enabled"] if default_incentive_params["cs_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("CS Amount ($/kWh):", html_for="cs-amount", size="sm"), dcc.Input(id="cs-amount", type="number", value=default_incentive_params["cs_amount"], min=0, className="form-control form-control-sm"), ], className="mb-2 ms-4"), ], className="mb-3"),
                         ]),
                         dbc.Card(className="p-3", children=[ # Custom
                             html.H4("Custom Incentive", className="mb-3"),
                             dbc.Checklist(id="custom-incentive-enabled", options=[{"label": " Enable Custom Incentive", "value": "enabled"}], value=["enabled"] if default_incentive_params["custom_incentive_enabled"] else [], className="form-check mb-2"),
                             html.Div([ dbc.Label("Incentive Type:", html_for="custom-incentive-type", size="sm"), dcc.RadioItems(id="custom-incentive-type", options=[{"label": " $/kWh", "value": "per_kwh"}, {"label": " % of Cost", "value": "percentage"}], value=default_incentive_params["custom_incentive_type"], inline=True, className="form-check"), ], className="mb-2 ms-4"),
                             html.Div([ dbc.Label("Incentive Amount:", html_for="custom-incentive-amount", size="sm"), dcc.Input(id="custom-incentive-amount", type="number", value=default_incentive_params["custom_incentive_amount"], min=0, className="form-control form-control-sm"), ], className="mb-2 ms-4"),
                             html.Div([ dbc.Label("Description:", html_for="custom-incentive-description", size="sm"), dcc.Input(id="custom-incentive-description", type="text", value=default_incentive_params["custom_incentive_description"], className="form-control form-control-sm"), ], className="mb-2 ms-4"),
                         ]),
                     ]),
                 ]), # End Incentive Row
                 html.Div([
                     dbc.Button("Calculate Results", id="calculate-results-button", n_clicks=0, color="primary", className="mt-4 mb-3 me-3"),
                     dbc.Button("Optimize Battery Size", id="optimize-battery-button", n_clicks=0, color="success", className="mt-4 mb-3"),
                 ], className="d-flex justify-content-center"),
            ])
        ]), # End Tab 3

        # Results Tab (keep as is)
        dbc.Tab(label="4. Results & Analysis", tab_id="tab-results", children=[
            dbc.Container(py=4, children=[
                dcc.Loading(id="loading-results", type="circle", children=[html.Div(id="results-output-container", className="mt-4")])
            ])
        ]), # End Tab 4

        # Optimization Tab (keep as is)
        dbc.Tab(label="5. Battery Sizing Tool", tab_id="tab-optimization", children=[
             dbc.Container(py=4, children=[
                dcc.Loading(id="loading-optimization", type="circle", children=[html.Div(id="optimization-output-container", className="mt-4")])
             ])
        ]), # End Tab 5
    ]), # End Tabs
]) # End Main Container

# --- Callbacks ---

# Tab Navigation (keep as is)
@app.callback(
    Output("main-tabs", "active_tab"),
    [Input("continue-to-params-button", "n_clicks"), Input("continue-to-incentives-button", "n_clicks")],
    prevent_initial_call=True,
)
def navigate_tabs(n_params, n_incentives):
    ctx = callback_context
    if not ctx.triggered_id: return dash.no_update
    if ctx.triggered_id == "continue-to-params-button": return "tab-params"
    elif ctx.triggered_id == "continue-to-incentives-button": return "tab-incentives"
    else: return dash.no_update

# EAF Store Update (keep as is)
@app.callback(
    Output("eaf-params-store", "data"),
    [Input("eaf-size", "value"), Input("eaf-count", "value"), Input("grid-cap", "value"), Input("cycles-per-day", "value"), Input("cycle-duration", "value"), Input("days-per-year", "value"), Input("mill-selection-dropdown", "value")],
    State("eaf-params-store", "data")
)
def update_eaf_params_store(size, count, grid_cap, cycles, duration, days, selected_mill, existing_data):
    ctx = callback_context; triggered_id = ctx.triggered_id if ctx.triggered_id else 'unknown'
    output_data = existing_data.copy() if existing_data and isinstance(existing_data, dict) else nucor_mills["Custom"].copy()
    if "cycle_duration_input" not in output_data: output_data["cycle_duration_input"] = output_data.get("cycle_duration", 0)
    if triggered_id == "mill-selection-dropdown":
        output_data = nucor_mills.get(selected_mill, nucor_mills["Custom"]).copy()
        output_data["cycle_duration_input"] = output_data.get("cycle_duration", 0)
    else:
        if size is not None: output_data["eaf_size"] = size
        if count is not None: output_data["eaf_count"] = count
        if grid_cap is not None: output_data["grid_cap"] = grid_cap
        if cycles is not None: output_data["cycles_per_day"] = cycles
        if duration is not None: output_data["cycle_duration"] = duration; output_data["cycle_duration_input"] = duration
        if days is not None: output_data["days_per_year"] = days
    base_duration = output_data.get("cycle_duration"); input_duration = output_data.get("cycle_duration_input")
    try: base_duration = float(base_duration) if base_duration is not None else 0.0
    except (ValueError, TypeError): base_duration = 0.0
    try: input_duration = float(input_duration) if input_duration is not None else 0.0
    except (ValueError, TypeError): input_duration = 0.0
    base_duration = max(0.0, base_duration); input_duration = max(0.0, input_duration)
    if input_duration <= 0 and base_duration > 0: output_data["cycle_duration_input"] = base_duration
    elif input_duration > 0: output_data["cycle_duration"] = input_duration
    else: output_data["cycle_duration"] = 0.0; output_data["cycle_duration_input"] = 0.0
    output_data["cycle_duration"] = base_duration; output_data["cycle_duration_input"] = input_duration
    return output_data

# Financial Store Update (keep as is)
@app.callback(
    Output("financial-params-store", "data"),
    [Input("wacc", "value"), Input("project-lifespan", "value"), Input("tax-rate", "value"), Input("inflation-rate", "value"), Input("salvage-value", "value")],
)
def update_financial_params_store(wacc, lifespan, tax, inflation, salvage):
    return {
        "wacc": wacc / 100.0 if wacc is not None else default_financial_params["wacc"],
        "project_lifespan": lifespan,
        "tax_rate": tax / 100.0 if tax is not None else default_financial_params["tax_rate"],
        "inflation_rate": inflation / 100.0 if inflation is not None else default_financial_params["inflation_rate"],
        "salvage_value": salvage / 100.0 if salvage is not None else default_financial_params["salvage_value"],
    }

# Incentive Store Update (keep as is)
@app.callback(
    Output("incentive-params-store", "data"),
    [Input("itc-enabled", "value"), Input("itc-percentage", "value"), Input("ceic-enabled", "value"), Input("ceic-percentage", "value"), Input("bonus-credit-enabled", "value"), Input("bonus-credit-percentage", "value"), Input("sgip-enabled", "value"), Input("sgip-amount", "value"), Input("ess-enabled", "value"), Input("ess-amount", "value"), Input("mabi-enabled", "value"), Input("mabi-amount", "value"), Input("cs-enabled", "value"), Input("cs-amount", "value"), Input("custom-incentive-enabled", "value"), Input("custom-incentive-type", "value"), Input("custom-incentive-amount", "value"), Input("custom-incentive-description", "value")],
)
def update_incentive_params_store(itc_en, itc_pct, ceic_en, ceic_pct, bonus_en, bonus_pct, sgip_en, sgip_amt, ess_en, ess_amt, mabi_en, mabi_amt, cs_en, cs_amt, custom_en, custom_type, custom_amt, custom_desc):
    return {
        "itc_enabled": "enabled" in itc_en, "itc_percentage": itc_pct, "ceic_enabled": "enabled" in ceic_en, "ceic_percentage": ceic_pct,
        "bonus_credit_enabled": "enabled" in bonus_en, "bonus_credit_percentage": bonus_pct, "sgip_enabled": "enabled" in sgip_en, "sgip_amount": sgip_amt,
        "ess_enabled": "enabled" in ess_en, "ess_amount": ess_amt, "mabi_enabled": "enabled" in mabi_en, "mabi_amount": mabi_amt,
        "cs_enabled": "enabled" in cs_en, "cs_amount": cs_amt, "custom_incentive_enabled": "enabled" in custom_en,
        "custom_incentive_type": custom_type, "custom_incentive_amount": custom_amt, "custom_incentive_description": custom_desc,
    }

# Utility Store Update (keep as is)
@app.callback(
    Output("utility-params-store", "data"),
    [Input("utility-provider-dropdown", "value"), Input("off-peak-rate", "value"), Input("mid-peak-rate", "value"), Input("peak-rate", "value"), Input("demand-charge", "value"), Input("seasonal-rates-toggle", "value"), Input("winter-multiplier", "value"), Input("summer-multiplier", "value"), Input("shoulder-multiplier", "value"), Input("winter-months", "value"), Input("summer-months", "value"), Input("shoulder-months", "value"), Input({"type": "tou-start", "index": ALL}, "value"), Input({"type": "tou-end", "index": ALL}, "value"), Input({"type": "tou-rate", "index": ALL}, "value")],
    State("utility-params-store", "data"),
)
def update_utility_params_store(utility_provider, off_peak_rate, mid_peak_rate, peak_rate, demand_charge, seasonal_toggle, winter_mult, summer_mult, shoulder_mult, winter_months_str, summer_months_str, shoulder_months_str, tou_starts, tou_ends, tou_rates, existing_data):
    ctx = callback_context; triggered_id = ctx.triggered_id
    if isinstance(triggered_id, str) and triggered_id == "utility-provider-dropdown":
        params = utility_rates.get(utility_provider, default_utility_params).copy()
        params["tou_periods_raw"] = params.get("tou_periods", default_utility_params["tou_periods_raw"])
    elif existing_data: params = existing_data.copy()
    else: params = default_utility_params.copy()
    params["energy_rates"] = {"off_peak": off_peak_rate, "mid_peak": mid_peak_rate, "peak": peak_rate}
    params["demand_charge"] = demand_charge
    params["seasonal_rates"] = True if seasonal_toggle and "enabled" in seasonal_toggle else False
    def parse_months(month_str, default_list):
        if not isinstance(month_str, str): return default_list
        try: parsed = [int(m.strip()) for m in month_str.split(",") if m.strip() and 1 <= int(m.strip()) <= 12]; return parsed if parsed else default_list
        except ValueError: return default_list
    if params["seasonal_rates"] or any(trig["prop_id"].startswith(p) for trig in ctx.triggered for p in ["winter-", "summer-", "shoulder-"]):
        params["winter_months"] = parse_months(winter_months_str, default_utility_params["winter_months"])
        params["summer_months"] = parse_months(summer_months_str, default_utility_params["summer_months"])
        params["shoulder_months"] = parse_months(shoulder_months_str, default_utility_params["shoulder_months"])
        params["winter_multiplier"] = winter_mult if winter_mult is not None else default_utility_params["winter_multiplier"]
        params["summer_multiplier"] = summer_mult if summer_mult is not None else default_utility_params["summer_multiplier"]
        params["shoulder_multiplier"] = shoulder_mult if shoulder_mult is not None else default_utility_params["shoulder_multiplier"]
    if isinstance(triggered_id, str) and triggered_id == "utility-provider-dropdown":
        raw_tou_periods = params.get("tou_periods", default_utility_params["tou_periods_raw"])
    else:
        raw_tou_periods = []
        for i in range(len(tou_starts)):
            start_val, end_val, rate_val = tou_starts[i], tou_ends[i], tou_rates[i]
            if start_val is not None and end_val is not None and rate_val is not None:
                try:
                    start_f, end_f = float(start_val), float(end_val)
                    if 0 <= start_f < end_f <= 24: raw_tou_periods.append((start_f, end_f, str(rate_val)))
                    else: print(f"Warning: Invalid TOU range {start_f}-{end_f} ignored.")
                except (ValueError, TypeError): print(f"Warning: Invalid TOU numeric values ({start_val}, {end_val}) ignored.")
            elif rate_val is not None: print(f"Warning: Incomplete TOU period at index {i} ignored.")
    params["tou_periods_raw"] = raw_tou_periods
    params["tou_periods_filled"] = fill_tou_gaps(raw_tou_periods)
    return params

# Mill Info Card Update (keep as is)
@app.callback(Output("mill-info-card", "children"), Input("mill-selection-dropdown", "value"))
def update_mill_info(selected_mill):
    if not selected_mill or selected_mill not in nucor_mills: mill_data = nucor_mills["Custom"]; selected_mill = "Custom"; card_header_class = "card-header bg-secondary text-white"
    else: mill_data = nucor_mills[selected_mill]; card_header_class = "card-header bg-primary text-white"
    info_card = dbc.Card([ dbc.CardHeader(f"Selected: Nucor Steel {selected_mill}", className=card_header_class), dbc.CardBody([ html.Div([html.Strong("Location: "), html.Span(mill_data.get("location", "N/A"))], className="mb-1"), html.Div([html.Strong("Mill Type: "), html.Span(mill_data.get("type", "N/A"))], className="mb-1"), html.Div([html.Strong("EAF Config: "), html.Span(f"{mill_data.get('eaf_count', 'N/A')} x {mill_data.get('eaf_size', 'N/A')} ton {mill_data.get('eaf_type', 'N/A')} ({mill_data.get('eaf_manufacturer', 'N/A')})")], className="mb-1"), html.Div([html.Strong("Production: "), html.Span(f"{mill_data.get('tons_per_year', 0):,} tons/year")], className="mb-1"), html.Div([html.Strong("Schedule: "), html.Span(f"{mill_data.get('cycles_per_day', 'N/A')} cycles/day, {mill_data.get('days_per_year', 'N/A')} days/year, {mill_data.get('cycle_duration', 'N/A')} min/cycle")], className="mb-1"), html.Div([html.Strong("Utility: "), html.Span(mill_data.get("utility", "N/A"))], className="mb-1"), html.Div([html.Strong("Grid Cap (Est): "), html.Span(f"{mill_data.get('grid_cap', 'N/A')} MW")], className="mb-1"), ]) ])
    return info_card

# Update Params from Mill Selection (keep as is)
@app.callback(
    [Output("utility-provider-dropdown", "value"), Output("off-peak-rate", "value"), Output("mid-peak-rate", "value"), Output("peak-rate", "value"), Output("demand-charge", "value"), Output("seasonal-rates-toggle", "value"), Output("eaf-size", "value"), Output("eaf-count", "value"), Output("grid-cap", "value"), Output("cycles-per-day", "value"), Output("cycle-duration", "value"), Output("days-per-year", "value"), Output("tou-periods-container", "children", allow_duplicate=True)],
    Input("mill-selection-dropdown", "value"),
    prevent_initial_call=True,
)
def update_params_from_mill(selected_mill):
    if not selected_mill or selected_mill not in nucor_mills: mill_data = nucor_mills["Custom"]; utility_provider = "Custom Utility"; utility_data = utility_rates.get(utility_provider, default_utility_params)
    else:
        mill_data = nucor_mills[selected_mill]; utility_provider = mill_data["utility"]
        if utility_provider not in utility_rates: utility_data = utility_rates["Custom Utility"]; utility_provider = "Custom Utility"
        else: utility_data = utility_rates[utility_provider]
    off_peak = utility_data.get("energy_rates", {}).get("off_peak", default_utility_params["energy_rates"]["off_peak"])
    mid_peak = utility_data.get("energy_rates", {}).get("mid_peak", default_utility_params["energy_rates"]["mid_peak"])
    peak = utility_data.get("energy_rates", {}).get("peak", default_utility_params["energy_rates"]["peak"])
    demand = utility_data.get("demand_charge", default_utility_params["demand_charge"])
    seasonal_enabled = ["enabled"] if utility_data.get("seasonal_rates", default_utility_params["seasonal_rates"]) else []
    eaf_size = mill_data.get("eaf_size", nucor_mills["Custom"]["eaf_size"]); eaf_count = mill_data.get("eaf_count", nucor_mills["Custom"]["eaf_count"])
    grid_cap = mill_data.get("grid_cap", nucor_mills["Custom"]["grid_cap"]); cycles = mill_data.get("cycles_per_day", nucor_mills["Custom"]["cycles_per_day"])
    duration = mill_data.get("cycle_duration", nucor_mills["Custom"]["cycle_duration"]); days = mill_data.get("days_per_year", nucor_mills["Custom"]["days_per_year"])
    tou_periods_for_ui = utility_data.get("tou_periods", default_utility_params["tou_periods_raw"])
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)
    return [utility_provider, off_peak, mid_peak, peak, demand, seasonal_enabled, eaf_size, eaf_count, grid_cap, cycles, duration, days, tou_elements_ui]

# Update Rates from Provider Dropdown (keep as is)
@app.callback(
    [Output("off-peak-rate", "value", allow_duplicate=True), Output("mid-peak-rate", "value", allow_duplicate=True), Output("peak-rate", "value", allow_duplicate=True), Output("demand-charge", "value", allow_duplicate=True), Output("seasonal-rates-toggle", "value", allow_duplicate=True), Output("tou-periods-container", "children", allow_duplicate=True)],
    Input("utility-provider-dropdown", "value"), State("mill-selection-dropdown", "value"),
    prevent_initial_call=True,
)
def update_rates_from_provider_manual(selected_utility, selected_mill):
    ctx = callback_context
    if not ctx.triggered_id or ctx.triggered_id != "utility-provider-dropdown": return dash.no_update
    utility_data = utility_rates.get(selected_utility, utility_rates["Custom Utility"])
    off_peak = utility_data.get("energy_rates", {}).get("off_peak", default_utility_params["energy_rates"]["off_peak"])
    mid_peak = utility_data.get("energy_rates", {}).get("mid_peak", default_utility_params["energy_rates"]["mid_peak"])
    peak = utility_data.get("energy_rates", {}).get("peak", default_utility_params["energy_rates"]["peak"])
    demand = utility_data.get("demand_charge", default_utility_params["demand_charge"])
    seasonal_enabled = ["enabled"] if utility_data.get("seasonal_rates", default_utility_params["seasonal_rates"]) else []
    tou_periods_for_ui = utility_data.get("tou_periods", default_utility_params["tou_periods_raw"])
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)
    return off_peak, mid_peak, peak, demand, seasonal_enabled, tou_elements_ui

# Seasonal Rates UI (keep as is)
@app.callback(
    [Output("seasonal-rates-container", "children"), Output("seasonal-rates-container", "style")],
    [Input("seasonal-rates-toggle", "value"), Input("utility-provider-dropdown", "value")], State("mill-selection-dropdown", "value"),
)
def update_seasonal_rates_ui(toggle_value, selected_utility, selected_mill):
    is_enabled = toggle_value and "enabled" in toggle_value
    utility_data_source = default_utility_params
    if selected_utility in utility_rates: utility_data_source = utility_rates[selected_utility]
    elif selected_mill and selected_mill in nucor_mills and nucor_mills[selected_mill]["utility"] in utility_rates: utility_data_source = utility_rates[nucor_mills[selected_mill]["utility"]]
    winter_mult = utility_data_source.get("winter_multiplier", default_utility_params["winter_multiplier"]); summer_mult = utility_data_source.get("summer_multiplier", default_utility_params["summer_multiplier"]); shoulder_mult = utility_data_source.get("shoulder_multiplier", default_utility_params["shoulder_multiplier"])
    winter_m = ",".join(map(str, utility_data_source.get("winter_months", default_utility_params["winter_months"]))); summer_m = ",".join(map(str, utility_data_source.get("summer_months", default_utility_params["summer_months"]))); shoulder_m = ",".join(map(str, utility_data_source.get("shoulder_months", default_utility_params["shoulder_months"])))
    if not is_enabled: return [], {"display": "none"}
    seasonal_ui = html.Div([ dbc.Row([ dbc.Col([dbc.Label("Winter Multiplier:", size="sm"), dcc.Input(id="winter-multiplier", type="number", value=winter_mult, min=0, step=0.01, className="form-control form-control-sm")], md=4, className="mb-2"), dbc.Col([dbc.Label("Summer Multiplier:", size="sm"), dcc.Input(id="summer-multiplier", type="number", value=summer_mult, min=0, step=0.01, className="form-control form-control-sm")], md=4, className="mb-2"), dbc.Col([dbc.Label("Shoulder Multiplier:", size="sm"), dcc.Input(id="shoulder-multiplier", type="number", value=shoulder_mult, min=0, step=0.01, className="form-control form-control-sm")], md=4, className="mb-2"), ], className="row mb-2"), dbc.Row([ dbc.Col([dbc.Label("Winter Months (1-12):", size="sm"), dcc.Input(id="winter-months", type="text", value=winter_m, placeholder="e.g., 11,12,1,2", className="form-control form-control-sm")], md=4, className="mb-2"), dbc.Col([dbc.Label("Summer Months (1-12):", size="sm"), dcc.Input(id="summer-months", type="text", value=summer_m, placeholder="e.g., 6,7,8,9", className="form-control form-control-sm")], md=4, className="mb-2"), dbc.Col([dbc.Label("Shoulder Months (1-12):", size="sm"), dcc.Input(id="shoulder-months", type="text", value=shoulder_m, placeholder="e.g., 3,4,5,10", className="form-control form-control-sm")], md=4, className="mb-2"), ], className="row"), html.P("Use comma-separated month numbers (1-12). Ensure all 12 months are assigned.", className="small text-muted mt-1"), ])
    return seasonal_ui, {"display": "block"}

# TOU UI Management (Helper and Callback - keep as is)
# ... (generate_tou_ui_elements and modify_tou_rows remain the same) ...
def generate_tou_ui_elements(tou_periods_list):
    tou_elements = []
    if not tou_periods_list: tou_periods_list = [(0.0, 24.0, "off_peak")]
    for i, period_data in enumerate(tou_periods_list):
        if isinstance(period_data, (list, tuple)) and len(period_data) == 3: start, end, rate_type = period_data
        else: print(f"Warning: Invalid format for TOU period data at index {i}: {period_data}. Using default."); start, end, rate_type = (0.0, 0.0, "off_peak")
        tou_row = html.Div([ html.Div([ html.Div(dcc.Input(id={"type": "tou-start", "index": i}, type="number", min=0, max=24, step=0.1, value=start, className="form-control form-control-sm", placeholder="Start Hr (0-24)"), className="col-3"), html.Div(dcc.Input(id={"type": "tou-end", "index": i}, type="number", min=0, max=24, step=0.1, value=end, className="form-control form-control-sm", placeholder="End Hr (0-24)"), className="col-3"), html.Div(dcc.Dropdown(id={"type": "tou-rate", "index": i}, options=[{"label": "Off-Peak", "value": "off_peak"}, {"label": "Mid-Peak", "value": "mid_peak"}, {"label": "Peak", "value": "peak"}], value=rate_type, clearable=False, className="form-select form-select-sm"), className="col-4"), html.Div(dbc.Button("×", id={"type": "remove-tou", "index": i}, color="danger", size="sm", title="Remove Period", style={"lineHeight": "1"}, disabled=len(tou_periods_list) <= 1), className="col-2 d-flex align-items-center justify-content-center"), ], className="row g-1 mb-1 align-items-center"), ], id=f"tou-row-{i}", className="tou-period-row")
        tou_elements.append(tou_row)
    return tou_elements

@app.callback(
    Output("tou-periods-container", "children", allow_duplicate=True),
    [Input("add-tou-period-button", "n_clicks"), Input({"type": "remove-tou", "index": ALL}, "n_clicks")],
    State("tou-periods-container", "children"), prevent_initial_call=True,
)
def modify_tou_rows(add_clicks, remove_clicks_list, current_rows):
    ctx = callback_context; triggered_input = ctx.triggered_id
    if not triggered_input: return dash.no_update
    new_rows = current_rows[:] if current_rows else []
    if triggered_input == "add-tou-period-button":
        new_index = len(new_rows); default_start = 0.0
        new_row_elements = generate_tou_ui_elements([(default_start, 0.0, "off_peak")])
        new_row_div = new_row_elements[0]; new_row_div.id = f"tou-row-{new_index}"
        for col in new_row_div.children[0].children:
            if hasattr(col.children, "id") and isinstance(col.children.id, dict): col.children.id["index"] = new_index
        new_rows.append(new_row_div)
    elif isinstance(triggered_input, dict) and triggered_input.get("type") == "remove-tou":
        if len(new_rows) > 1:
            clicked_index = triggered_input["index"]; row_to_remove_id = f"tou-row-{clicked_index}"
            new_rows = [row for row in new_rows if row.get("props", {}).get("id") != row_to_remove_id]
        else: print("Cannot remove the last TOU period row.")
    num_rows = len(new_rows)
    for i, row in enumerate(new_rows):
        try: button_col = row.children[0].children[-1]; button = button_col.children; button.disabled = num_rows <= 1
        except (AttributeError, IndexError): print(f"Warning: Could not find or update remove button state for row {i}")
    return new_rows


# Input Validation (keep as is, maybe add checks for new BESS fields)
@app.callback(
    [Output("validation-error-container", "children"), Output("validation-error-container", "is_open"), Output("calculation-error-container", "is_open", allow_duplicate=True)],
    [Input("calculate-results-button", "n_clicks"), Input("optimize-battery-button", "n_clicks"), Input("utility-params-store", "data"), Input("eaf-params-store", "data"), Input("bess-params-store", "data"), Input("financial-params-store", "data")],
    prevent_initial_call=True,
)
def validate_inputs(calc_clicks, opt_clicks, utility_params, eaf_params, bess_params, fin_params):
    ctx = dash.callback_context; triggered_id = ctx.triggered_id if ctx.triggered_id else 'initial_load_or_unknown'
    is_calc_attempt = triggered_id in ["calculate-results-button", "optimize-battery-button"]
    errors = []; warnings = []
    # ... (Keep existing validation checks for Utility, EAF, Financial) ...
    # --- Add/Modify BESS Validation ---
    if not bess_params: errors.append("BESS parameters are missing.")
    else:
        if bess_params.get('capacity', 0) <= 0: errors.append("BESS Capacity (MWh) must be positive.")
        if bess_params.get('power_max', 0) <= 0: errors.append("BESS Power (MW) must be positive.")
        # Add checks for new fields
        if bess_params.get('sb_bos_cost_per_kwh', -1) < 0: errors.append("BESS SB+BOS Cost cannot be negative.")
        if bess_params.get('pcs_cost_per_kw', -1) < 0: errors.append("BESS PCS Cost cannot be negative.")
        if bess_params.get('epc_cost_per_kwh', -1) < 0: errors.append("BESS EPC Cost cannot be negative.")
        if bess_params.get('sys_integration_cost_per_kwh', -1) < 0: errors.append("BESS System Integration Cost cannot be negative.")
        if bess_params.get('fixed_om_per_kw_yr', None) is not None and bess_params.get('fixed_om_per_kw_yr', -1) < 0: errors.append("BESS Fixed O&M Cost cannot be negative.")
        if bess_params.get('om_cost_per_kwh_yr', None) is not None and bess_params.get('om_cost_per_kwh_yr', -1) < 0: errors.append("BESS O&M Cost ($/kWh/yr) cannot be negative.")
        if not (0 < bess_params.get('rte_percent', 0) <= 100): errors.append("BESS RTE must be between 0% and 100%.")
        if bess_params.get('insurance_percent_yr', -1) < 0: errors.append("BESS Insurance Rate cannot be negative.")
        # Decomm costs can be negative (recycling value)
        if bess_params.get('cycle_life', 0) <= 0: errors.append("BESS Cycle Life must be positive.")
        if not (0 < bess_params.get('dod_percent', 0) <= 100): errors.append("BESS DoD must be between 0% and 100%.")
        if bess_params.get('calendar_life', 0) <= 0: errors.append("BESS Calendar Life must be positive.")

    output_elements = []; is_open = False; calc_error_open = False
    if errors:
        output_elements.append(html.H5("Validation Errors:", className="text-danger")); output_elements.append(html.Ul([html.Li(e) for e in errors]))
        is_open = True; calc_error_open = False # Hide calc error if validation fails
    elif warnings:
        output_elements.append(html.H5("Validation Warnings:", className="text-warning")); output_elements.append(html.Ul([html.Li(w) for w in warnings]))
        is_open = True

    return output_elements, is_open, calc_error_open


# --- NEW BESS CALLBACK: Update Inputs on Dropdown Change ---
@app.callback(
    [
        Output("bess-example-product", "children"),
        Output("bess-sb-bos-cost", "value"),
        Output("bess-pcs-cost", "value"),
        Output("bess-epc-cost", "value"),
        Output("bess-sys-int-cost", "value"),
        Output("bess-opex-inputs-container", "children"), # Dynamically create O&M input
        Output("bess-rte", "value"),
        Output("bess-insurance", "value"),
        Output("bess-disconnect-cost", "value"),
        Output("bess-recycling-cost", "value"),
        Output("bess-cycle-life", "value"),
        Output("bess-dod", "value"),
        Output("bess-calendar-life", "value"),
    ],
    Input("bess-technology-dropdown", "value"),
    prevent_initial_call=True
)
def update_bess_inputs_from_technology(selected_technology):
    if not selected_technology or selected_technology not in bess_technology_data:
        # Handle error or default case, maybe revert to LFP?
        selected_technology = "LFP"

    tech_data = bess_technology_data[selected_technology]

    # Create the correct O&M input based on available data
    if "om_cost_per_kwh_yr" in tech_data:
        opex_input = create_bess_input_group("O&M Cost:", "bess-om-cost-kwhyr", tech_data['om_cost_per_kwh_yr'], "$/kWh/yr")
    else:
        # Default to fixed $/kW/yr if the other isn't present
        opex_input = create_bess_input_group("Fixed O&M:", "bess-fixed-om", tech_data.get('fixed_om_per_kw_yr', 0), "$/kW/yr")


    return (
        tech_data.get("example_product", "N/A"),
        tech_data.get("sb_bos_cost_per_kwh", 0),
        tech_data.get("pcs_cost_per_kw", 0),
        tech_data.get("epc_cost_per_kwh", 0),
        tech_data.get("sys_integration_cost_per_kwh", 0),
        opex_input, # Put the dynamically created input here
        tech_data.get("rte_percent", 0),
        tech_data.get("insurance_percent_yr", 0),
        tech_data.get("disconnect_cost_per_kwh", 0),
        tech_data.get("recycling_cost_per_kwh", 0),
        tech_data.get("cycle_life", 0),
        tech_data.get("dod_percent", 0),
        tech_data.get("calendar_life", 0),
    )


# --- MODIFIED BESS CALLBACK: Update BESS Store from All Inputs ---
@app.callback(
    Output("bess-params-store", "data"),
    [
        # Overall Size
        Input("bess-capacity", "value"),
        Input("bess-power", "value"),
        # Technology Choice
        Input("bess-technology-dropdown", "value"),
        # Detailed Inputs
        Input("bess-sb-bos-cost", "value"),
        Input("bess-pcs-cost", "value"),
        Input("bess-epc-cost", "value"),
        Input("bess-sys-int-cost", "value"),
        Input("bess-fixed-om", "value"), # Note: ID depends on dynamic creation
        Input("bess-om-cost-kwhyr", "value"), # Note: ID depends on dynamic creation
        Input("bess-rte", "value"),
        Input("bess-insurance", "value"),
        Input("bess-disconnect-cost", "value"),
        Input("bess-recycling-cost", "value"),
        Input("bess-cycle-life", "value"),
        Input("bess-dod", "value"),
        Input("bess-calendar-life", "value"),
    ],
    # prevent_initial_call=True # Allow initial load based on defaults
)
def update_bess_params_store(
    capacity, power, technology,
    sb_bos_cost, pcs_cost, epc_cost, sys_int_cost,
    fixed_om, om_kwhyr, # One of these will likely be None depending on tech
    rte, insurance, disconnect_cost, recycling_cost,
    cycle_life, dod, calendar_life
    ):

    # Build the dictionary for the store
    bess_store_data = {
        "capacity": capacity,
        "power_max": power,
        "technology": technology,
        "sb_bos_cost_per_kwh": sb_bos_cost,
        "pcs_cost_per_kw": pcs_cost,
        "epc_cost_per_kwh": epc_cost,
        "sys_integration_cost_per_kwh": sys_int_cost,
        # Store the O&M value that is not None
        "fixed_om_per_kw_yr": fixed_om if fixed_om is not None else 0, # Default to 0 if None
        "om_cost_per_kwh_yr": om_kwhyr if om_kwhyr is not None else None, # Keep as None if not applicable
        "rte_percent": rte,
        "insurance_percent_yr": insurance,
        "disconnect_cost_per_kwh": disconnect_cost,
        "recycling_cost_per_kwh": recycling_cost,
        "cycle_life": cycle_life,
        "dod_percent": dod,
        "calendar_life": calendar_life,
    }
    # Add back the example product for reference if needed, though not strictly necessary for calcs
    bess_store_data["example_product"] = bess_technology_data.get(technology, {}).get("example_product", "N/A")

    return bess_store_data


# --- Main Calculation Callback (keep as is, uses updated store) ---
@app.callback(
    [Output("results-output-container", "children"), Output("calculation-results-store", "data"), Output("calculation-error-container", "children"), Output("calculation-error-container", "is_open")],
    Input("calculate-results-button", "n_clicks"),
    [State("eaf-params-store", "data"), State("bess-params-store", "data"), State("utility-params-store", "data"), State("financial-params-store", "data"), State("incentive-params-store", "data"), State("validation-error-container", "children")],
    prevent_initial_call=True,
)
def display_calculation_results(n_clicks, eaf_params, bess_params, utility_params, financial_params, incentive_params, validation_errors):
    results_output = html.Div("Click 'Calculate Results' to generate the analysis.", className="text-center text-muted")
    stored_data = {}; error_output = ""; error_open = False
    if n_clicks == 0: return results_output, stored_data, error_output, error_open
    if validation_errors:
        error_output = html.Div([html.H5("Cannot Calculate - Validation Errors Exist", className="text-danger"), html.P("Please fix the errors listed above before calculating.")])
        error_open = True
        return results_output, stored_data, error_output, error_open
    try:
        if not all([eaf_params, bess_params, utility_params, financial_params, incentive_params]): raise ValueError("One or more parameter sets are missing.")
        billing_results = calculate_annual_billings(eaf_params, bess_params, utility_params)
        incentive_results = calculate_incentives(bess_params, incentive_params) # Pass full bess_params
        financial_metrics = calculate_financial_metrics(bess_params, financial_params, eaf_params, billing_results["annual_savings"], incentive_results) # Pass full bess_params
        stored_data = {"billing": billing_results, "incentives": incentive_results, "financials": financial_metrics, "inputs": {"eaf": eaf_params, "bess": bess_params, "utility": utility_params, "financial": financial_params, "incentive": incentive_params}}

        # --- Plotting Data ---
        plot_data_calculated = False; plot_error_message = ""; time_plot, eaf_power_plot, grid_power_plot, bess_power_plot = [], [], [], []; max_y_plot = 60
        try:
            plot_cycle_duration_min = eaf_params.get("cycle_duration_input", 36); plot_cycle_duration_min = max(1, plot_cycle_duration_min) # Ensure positive
            time_plot = np.linspace(0, plot_cycle_duration_min, 200)
            eaf_power_plot = calculate_eaf_profile(time_plot, eaf_params.get("eaf_size", 100), plot_cycle_duration_min)
            grid_power_plot, bess_power_plot = calculate_grid_bess_power(eaf_power_plot, eaf_params.get("grid_cap", 35), bess_params.get("power_max", 20))
            plot_data_calculated = True
            max_y_plot = max(np.max(eaf_power_plot) if len(eaf_power_plot)>0 else 0, eaf_params.get("grid_cap", 35)) * 1.15; max_y_plot = max(10, max_y_plot) # Ensure min range
        except Exception as plot_err: plot_error_message = f"Error generating single cycle plot data: {plot_err}"; print(plot_error_message)

        # --- Formatting ---
        def fmt_c(v): return f"${v:,.0f}" if pd.notna(v) else "N/A"
        def fmt_p(v): return f"{v:.1%}" if pd.notna(v) and isinstance(v, (int, float)) and abs(v)<=5 else (f"{'+' if v > 0 else ''}>500%" if pd.notna(v) and abs(v)>5 else "N/A")
        def fmt_y(v): return "Never" if pd.isna(v) or v == float("inf") else ("< 0 (Immediate)" if v < 0 else f"{v:.1f} yrs")

        # --- Cards ---
        metrics_card = dbc.Card([ dbc.CardHeader("Financial Summary"), dbc.CardBody(html.Table([ html.Tr([html.Td("Net Present Value (NPV)"), html.Td(fmt_c(financial_metrics["npv"]))]), html.Tr([html.Td("Internal Rate of Return (IRR)"), html.Td(fmt_p(financial_metrics["irr"]))]), html.Tr([html.Td("Simple Payback Period"), html.Td(fmt_y(financial_metrics["payback_years"]))]), html.Tr([html.Td("Est. Battery Life (Replacement Interval)"), html.Td(fmt_y(financial_metrics["battery_life_years"]))]), html.Tr([html.Td("Net Initial Cost (After Incentives)"), html.Td(fmt_c(financial_metrics["net_initial_cost"]))]), html.Tr([html.Td("Gross Initial Cost (Before Incentives)"), html.Td(fmt_c(financial_metrics["total_initial_cost"]))]), ], className="table table-sm")) ])
        savings_card = dbc.Card([ dbc.CardHeader("Annual Billing"), dbc.CardBody(html.Table([ html.Tr([html.Td("Baseline Bill (No BESS)"), html.Td(fmt_c(billing_results["annual_bill_without_bess"]))]), html.Tr([html.Td("Projected Bill (With BESS)"), html.Td(fmt_c(billing_results["annual_bill_with_bess"]))]), html.Tr([html.Td(html.Strong("Annual Savings")), html.Td(html.Strong(fmt_c(billing_results["annual_savings"])))]) ], className="table table-sm")) ])
        inc_items = [html.Tr([html.Td(desc), html.Td(fmt_c(amount))]) for desc, amount in incentive_results["breakdown"].items()]
        inc_items.append(html.Tr([html.Td(html.Strong("Total Incentives")), html.Td(html.Strong(fmt_c(incentive_results["total_incentive"]))) ]))
        incentives_card = dbc.Card([ dbc.CardHeader("Incentives Applied"), dbc.CardBody(html.Table(inc_items, className="table table-sm")) ])

        # --- Monthly Table ---
        months = [calendar.month_abbr[i] for i in range(1, 13)]
        df_monthly = pd.DataFrame({ "Month": months, "Bill Without BESS": [b["total_bill"] for b in billing_results["monthly_bills_without_bess"]], "Bill With BESS": [b["total_bill"] for b in billing_results["monthly_bills_with_bess"]], "Savings": billing_results["monthly_savings"], "Peak Demand w/o BESS (kW)": [b["peak_demand_kw"] for b in billing_results["monthly_bills_without_bess"]], "Peak Demand w/ BESS (kW)": [b["peak_demand_kw"] for b in billing_results["monthly_bills_with_bess"]], })
        for col in ["Bill Without BESS", "Bill With BESS", "Savings"]: df_monthly[col] = df_monthly[col].apply(fmt_c)
        for col in ["Peak Demand w/o BESS (kW)", "Peak Demand w/ BESS (kW)"]: df_monthly[col] = df_monthly[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        monthly_table = dash_table.DataTable(data=df_monthly.to_dict("records"), columns=[{"name": i, "id": i} for i in df_monthly.columns], style_cell={"textAlign": "right", "padding": "5px"}, style_header={"fontWeight": "bold", "textAlign": "center"}, style_data={"border": "1px solid grey"}, style_table={"overflowX": "auto", "minWidth": "100%"}, style_cell_conditional=[{"if": {"column_id": "Month"}, "textAlign": "left"}])

        # --- Graphs ---
        years_cf = list(range(financial_params["project_lifespan"] + 1)); cash_flows_data = financial_metrics.get("cash_flows", [])
        if len(cash_flows_data) != len(years_cf): print(f"Warning: Cash flow data length ({len(cash_flows_data)}) doesn't match project lifespan + 1 ({len(years_cf)})."); cash_flows_data = cash_flows_data[: len(years_cf)] + [0] * (len(years_cf) - len(cash_flows_data))
        fig_cashflow = go.Figure(go.Bar(x=years_cf, y=cash_flows_data, name="After-Tax Cash Flow", marker_color=["red" if cf < 0 else "green" for cf in cash_flows_data]))
        fig_cashflow.update_layout(title="Project After-Tax Cash Flows", xaxis_title="Year", yaxis_title="Cash Flow ($)", yaxis_tickformat="$,.0f", plot_bgcolor="white", margin=dict(l=40, r=20, t=40, b=30))

        fig_single_cycle = go.Figure()
        if plot_data_calculated:
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=eaf_power_plot, mode='lines', name='EAF Power Demand', line=dict(color='blue', width=2)))
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=grid_power_plot, mode='lines', name='Grid Power Supply', line=dict(color='green', width=2)))
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=bess_power_plot, mode='lines', name='BESS Power Output', line=dict(color='red', width=2), fill='tozeroy'))
            grid_cap_val = eaf_params.get("grid_cap", 35)
            fig_single_cycle.add_shape(type="line", x0=0, y0=grid_cap_val, x1=plot_cycle_duration_min, y1=grid_cap_val, line=dict(color='black', width=2, dash='dash'), name='Grid Cap')
            fig_single_cycle.add_annotation(x=plot_cycle_duration_min * 0.9, y=grid_cap_val + max_y_plot * 0.03, text=f"Grid Cap ({grid_cap_val} MW)", showarrow=False, font=dict(color='black', size=10))
        else: fig_single_cycle.update_layout(xaxis = {'visible': False}, yaxis = {'visible': False}, annotations = [{'text': 'Error generating plot data', 'xref': 'paper', 'yref': 'paper', 'showarrow': False, 'font': {'size': 16}}])
        fig_single_cycle.update_layout(title=f'Simulated EAF Cycle Profile ({eaf_params.get("eaf_size", "N/A")}-ton)', xaxis_title=f"Time in Cycle (minutes, Duration: {plot_cycle_duration_min:.1f} min)", yaxis_title="Power (MW)", yaxis_range=[0, max_y_plot], showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), template="plotly_white", margin=dict(l=40, r=20, t=50, b=40))

        # --- Assemble ---
        results_output = html.Div([ html.H3("Calculation Results", className="mb-4"), dbc.Row([ dbc.Col(metrics_card, lg=4, md=6), dbc.Col(savings_card, lg=4, md=6), dbc.Col(incentives_card, lg=4, md=12), ], className="mb-4"), html.H4("Monthly Billing Breakdown", className="mb-3"), monthly_table, html.H4("Single Cycle Power Profile", className="mt-4 mb-3"), dcc.Graph(figure=fig_single_cycle), html.H4("Cash Flow Analysis", className="mt-4 mb-3"), dcc.Graph(figure=fig_cashflow), ])
        error_output = ""; error_open = False

    except Exception as e:
        tb_str = traceback.format_exc()
        error_output = html.Div([ html.H5("Calculation Error", className="text-danger"), html.P("An error occurred during calculation:"), html.Pre(f"{type(e).__name__}: {str(e)}"), html.Details([html.Summary("Click for technical details (Traceback)"), html.Pre(tb_str)]) ])
        error_open = True
        results_output = html.Div("Could not generate results due to an error.", className="text-center text-danger")
        stored_data = {}

    return results_output, stored_data, error_output, error_open


# --- Optimization Callback (keep as is, uses updated store) ---
@app.callback(
    [Output("optimization-output-container", "children"), Output("optimization-results-store", "data")],
    Input("optimize-battery-button", "n_clicks"),
    [State("eaf-params-store", "data"), State("bess-params-store", "data"), State("utility-params-store", "data"), State("financial-params-store", "data"), State("incentive-params-store", "data"), State("validation-error-container", "children")],
    prevent_initial_call=True,
)
def display_optimization_results(n_clicks, eaf_params, bess_base_params, utility_params, financial_params, incentive_params, validation_errors):
    opt_output = html.Div("Click 'Optimize Battery Size' to run the analysis.", className="text-center text-muted")
    opt_stored_data = {}
    if n_clicks == 0: return opt_output, opt_stored_data
    if validation_errors:
        opt_output = dbc.Alert([html.H4("Cannot Optimize - Validation Errors Exist", className="text-danger"), html.P("Please fix the errors listed in the Parameters/Incentives tabs before optimizing.")], color="danger")
        return opt_output, opt_stored_data
    try:
        if not all([eaf_params, bess_base_params, utility_params, financial_params, incentive_params]): raise ValueError("One or more parameter sets are missing for optimization.")
        print("Starting Optimization Callback...")
        # Pass the full bess_base_params which now includes tech-specific costs/perf
        opt_results = optimize_battery_size(eaf_params, utility_params, financial_params, incentive_params, bess_base_params)
        opt_stored_data = opt_results
        print("Optimization Function Finished.")

        if opt_results and opt_results.get("best_capacity") is not None:
            best_metrics = opt_results.get("best_metrics", {})
            def fmt_c(v): return f"${v:,.0f}" if pd.notna(v) else "N/A"
            def fmt_p(v): return f"{v:.1%}" if pd.notna(v) and isinstance(v, (int, float)) and abs(v)<=5 else (f"{'+' if v > 0 else ''}>500%" if pd.notna(v) and abs(v)>5 else "N/A")
            def fmt_y(v): return "Never" if pd.isna(v) or v == float("inf") else ("< 0 yrs" if v < 0 else f"{v:.1f} yrs")

            best_summary = dbc.Card([ dbc.CardHeader("Optimal Size Found (Max NPV)"), dbc.CardBody(html.Table([ html.Tr([html.Td("Capacity (MWh)"), html.Td(f"{opt_results['best_capacity']:.1f}")]), html.Tr([html.Td("Power (MW)"), html.Td(f"{opt_results['best_power']:.1f}")]), html.Tr([html.Td("Resulting NPV"), html.Td(fmt_c(opt_results["best_npv"]))]), html.Tr([html.Td("Resulting IRR"), html.Td(fmt_p(best_metrics.get("irr")))]), html.Tr([html.Td("Resulting Payback"), html.Td(fmt_y(best_metrics.get("payback_years")))]), html.Tr([html.Td("Annual Savings (Year 1)"), html.Td(fmt_c(best_metrics.get("annual_savings_year1")))]), html.Tr([html.Td("Net Initial Cost"), html.Td(fmt_c(best_metrics.get("net_initial_cost")))]), ], className="table table-sm")) ], className="mb-4")

            all_results_df = pd.DataFrame(opt_results.get("all_results", []))
            table_section = html.Div("No optimization results data to display in table.")
            if not all_results_df.empty:
                display_cols = {"capacity": "Capacity (MWh)", "power": "Power (MW)", "npv": "NPV ($)", "irr": "IRR (%)", "payback_years": "Payback (Yrs)", "annual_savings": "Savings ($/Yr)", "net_initial_cost": "Net Cost ($)"}
                all_results_df = all_results_df[[k for k in display_cols if k in all_results_df.columns]].copy() # Handle missing cols
                all_results_df.rename(columns=display_cols, inplace=True)
                for col in ["Capacity (MWh)", "Power (MW)"]: all_results_df[col] = all_results_df[col].map("{:.1f}".format)
                for col in ["NPV ($)", "Savings ($/Yr)", "Net Cost ($)"]: all_results_df[col] = all_results_df[col].apply(fmt_c)
                all_results_df["IRR (%)"] = all_results_df["IRR (%)"].apply(fmt_p)
                all_results_df["Payback (Yrs)"] = all_results_df["Payback (Yrs)"].apply(fmt_y)
                all_results_table = dash_table.DataTable(data=all_results_df.to_dict("records"), columns=[{"name": i, "id": i} for i in all_results_df.columns], page_size=10, sort_action="native", filter_action="native", style_cell={"textAlign": "right"}, style_header={"fontWeight": "bold"}, style_table={"overflowX": "auto", "minWidth": "100%"}, style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "left"} for c in ["Capacity (MWh)", "Power (MW)"]])
                table_section = html.Div([html.H4("All Tested Combinations", className="mt-4 mb-3"), all_results_table])

            opt_output = html.Div([html.H3("Battery Sizing Optimization Results", className="mb-4"), best_summary, table_section])
        else:
            opt_output = dbc.Alert([html.H4("Optimization Failed", className="text-warning"), html.P("Could not find an optimal battery size with the given parameters. Reasons might include:"), html.Ul([html.Li("No combinations resulted in a positive NPV or reasonable payback."), html.Li("Errors occurred during the simulation for all tested sizes."), html.Li("Parameter ranges for optimization might need adjustment.")])], color="warning")

    except Exception as e:
        tb_str = traceback.format_exc()
        opt_output = dbc.Alert([html.H5("Optimization Error", className="text-danger"), html.P("An error occurred during the optimization process:"), html.Pre(f"{type(e).__name__}: {str(e)}"), html.Details([html.Summary("Click for technical details (Traceback)"), html.Pre(tb_str)])], color="danger")
        opt_stored_data = {}

    return opt_output, opt_stored_data


# --- Run the App ---
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False) # Use debug=True for development

# --- END OF FILE ---
#```

#**Key Changes and Explanations:**

#1.  **Import `dash_bootstrap_components`:** Added `import dash_bootstrap_components as dbc` and used `dbc.themes.BOOTSTRAP` for better layout control with Cards, Rows, Cols.
#2.  **`bess_technology_data` Dictionary:** Created this dictionary to store default parameters for each technology. Values are populated based on the PNNL report (using figures/tables mentioned in the thought process) and user input for the supercapacitor. Placeholders are used where specific data was unavailable.
#3.  **`default_bess_params_store`:** The default state for the BESS store now includes the detailed parameters, initialized with LFP data.
#4.  **Layout Modifications:**
#    *   The BESS Parameters section in Tab 2 is significantly changed.
#    *   It now includes `dcc.Dropdown(id="bess-technology-dropdown")`.
#    *   An `html.P(id="bess-example-product")` displays the example product.
#    *   The individual inputs (`bess-capacity`, `bess-power`, etc.) are replaced by new inputs corresponding to the detailed parameters (`bess-sb-bos-cost`, `bess-pcs-cost`, etc.).
#    *   These new inputs are grouped into `dbc.Card` sections (Capex, Opex, Decommissioning, Performance) for clarity.
#    *   A helper function `create_bess_input_group` is used to reduce layout code repetition.
#    *   The O&M input is now dynamically created within a container (`bess-opex-inputs-container`) based on the selected technology (either `$/kW/yr` or `$/kWh/yr`).
#5.  **New Callback (`update_bess_inputs_from_technology`):**
#    *   Triggered by the `bess-technology-dropdown`.
#    *   Outputs update all the detailed BESS input fields and the example product text.
#    *   It dynamically creates the correct O&M input element (`$/kW/yr` or `$/kWh/yr`) based on the data available for the selected technology.
#6.  **Modified Callback (`update_bess_params_store`):**
#    *   Inputs now include all the *new* detailed BESS parameter inputs.
#    *   It reads these values and constructs the dictionary that gets stored in `bess-params-store`. It handles the two possible O&M input IDs.
#7.  **Modified Calculation Functions:**
#    *   `calculate_incentives`: Calculates `total_cost` based on the component costs (`sb_bos_cost_per_kwh`, `pcs_cost_per_kw`, etc.) and the system size (`capacity`, `power_max`) read from the `bess_params`.
#    *   `calculate_financial_metrics`:
#        *   Calculates `total_initial_cost` similarly.
#        *   Calculates `net_initial_cost` using incentives.
#        *   Calculates `total_initial_om_cost` using `fixed_om_per_kw_yr` (or `om_cost_per_kwh_yr` for supercap) and `insurance_percent_yr`.
#        *   Calculates `battery_replacement_interval` using both `calendar_life` and `cycle_life`.
#        *   Includes replacement costs based on `total_initial_cost`.
#        *   Includes decommissioning costs (`disconnect_cost_per_kwh`, `recycling_cost_per_kwh`) in the final year's cash flow. The old `salvage_value` input is still present in the layout but effectively ignored in the calculation in favor of the decommissioning costs.
#    *   `optimize_battery_size`: The `bess_base_params` passed to it now correctly contains the technology-specific cost/performance factors loaded from the store. It iterates capacity/power and passes the combined `test_bess_params` (base + size) to the incentive and financial calculation functions.
#8.  **Results Display:** The financial summary card in the results tab is updated to show the gross initial cost and clarifies that the net cost is after incentives. It also clarifies the battery life shown is the replacement interval.
#
#This implementation provides the requested technology selection and uses more detailed, technology-specific parameters for the financial calculations, making the tool significantly more robust. Remember to install `dash-bootstrap-components` (`pip install dash-bootstrap-components`) if you haven't already.
