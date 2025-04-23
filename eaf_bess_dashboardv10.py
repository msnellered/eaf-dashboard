# --- START OF FILE eaf_bess_dashboardv9_fixed_v2.py ---

import dash
import dash_bootstrap_components as dbc # Use dash_bootstrap_components
from dash import dcc, html, Input, Output, State, callback_context, ALL, dash_table
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import json
from datetime import datetime
import calendar
import traceback  # For detailed error logging
import pprint # For debug printing

# --- numpy_financial fallback ---
try:
    import numpy_financial as npf
except ImportError:
    print("WARNING: numpy_financial package is required for accurate financial calculations. Please install it with: pip install numpy-financial")
    class DummyNPF:
        def npv(self, rate, values):
            print("WARNING: Using simplified NPV calculation. Install numpy-financial for accurate results.")
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

# --- Constants ---
# Store IDs
STORE_EAF = "eaf-params-store"
STORE_UTILITY = "utility-params-store"
STORE_BESS = "bess-params-store"
STORE_FINANCIAL = "financial-params-store"
STORE_INCENTIVE = "incentive-params-store"
STORE_RESULTS = "calculation-results-store"
STORE_OPTIMIZATION = "optimization-results-store"

# Component IDs (Selected Examples)
ID_MILL_DROPDOWN = "mill-selection-dropdown"
ID_MILL_INFO_CARD = "mill-info-card"
ID_UTILITY_DROPDOWN = "utility-provider-dropdown"
ID_OFF_PEAK = "off-peak-rate"
ID_MID_PEAK = "mid-peak-rate"
ID_PEAK = "peak-rate"
ID_DEMAND_CHARGE = "demand-charge"
ID_SEASONAL_TOGGLE = "seasonal-rates-toggle"
ID_SEASONAL_CONTAINER = "seasonal-rates-container"
ID_TOU_CONTAINER = "tou-periods-container"
ID_ADD_TOU_BTN = "add-tou-period-button"
ID_EAF_SIZE = "eaf-size"
ID_EAF_COUNT = "eaf-count"
ID_GRID_CAP = "grid-cap"
ID_CYCLES_PER_DAY = "cycles-per-day"
ID_CYCLE_DURATION = "cycle-duration"
ID_DAYS_PER_YEAR = "days-per-year"
ID_BESS_CAPACITY = "bess-capacity"
ID_BESS_POWER = "bess-power"
ID_BESS_C_RATE_DISPLAY = "bess-c-rate-display"
ID_BESS_TECH_DROPDOWN = "bess-technology-dropdown"
ID_BESS_EXAMPLE_PRODUCT = "bess-example-product"
ID_BESS_SB_BOS_COST = "bess-sb-bos-cost"
ID_BESS_PCS_COST = "bess-pcs-cost"
ID_BESS_EPC_COST = "bess-epc-cost"
ID_BESS_SYS_INT_COST = "bess-sys-int-cost"
ID_BESS_OPEX_CONTAINER = "bess-opex-inputs-container"
ID_BESS_FIXED_OM = "bess-fixed-om" # Dynamic ID
ID_BESS_OM_KWHR_YR = "bess-om-cost-kwhyr" # Dynamic ID
ID_BESS_RTE = "bess-rte"
ID_BESS_INSURANCE = "bess-insurance"
ID_BESS_DISCONNECT_COST = "bess-disconnect-cost"
ID_BESS_RECYCLING_COST = "bess-recycling-cost"
ID_BESS_CYCLE_LIFE = "bess-cycle-life"
ID_BESS_DOD = "bess-dod"
ID_BESS_CALENDAR_LIFE = "bess-calendar-life"
ID_WACC = "wacc"
ID_LIFESPAN = "project-lifespan"
ID_TAX_RATE = "tax-rate"
ID_INFLATION_RATE = "inflation-rate"
ID_SALVAGE = "salvage-value"
ID_ITC_ENABLED = "itc-enabled"
ID_ITC_PERCENT = "itc-percentage"
# ... (add other incentive IDs if needed) ...
ID_CALC_BTN = "calculate-results-button"
ID_OPTIMIZE_BTN = "optimize-battery-button"
ID_RESULTS_OUTPUT = "results-output-container"
ID_OPTIMIZE_OUTPUT = "optimization-output-container"
ID_VALIDATION_ERR = "validation-error-container"
ID_CALCULATION_ERR = "calculation-error-container"
ID_MAIN_TABS = "main-tabs"
ID_CONTINUE_PARAMS_BTN = "continue-to-params-button"
ID_CONTINUE_INCENTIVES_BTN = "continue-to-incentives-button"

# Dictionary Keys (Selected Examples)
KEY_TECH = "technology"
KEY_CAPACITY = "capacity"
KEY_POWER_MAX = "power_max"
KEY_SB_BOS_COST = "sb_bos_cost_per_kwh"
KEY_PCS_COST = "pcs_cost_per_kw"
KEY_EPC_COST = "epc_cost_per_kwh"
KEY_SYS_INT_COST = "sys_integration_cost_per_kwh"
KEY_FIXED_OM = "fixed_om_per_kw_yr"
KEY_OM_KWHR_YR = "om_cost_per_kwh_yr"
KEY_RTE = "rte_percent"
KEY_INSURANCE = "insurance_percent_yr"
KEY_DISCONNECT_COST = "disconnect_cost_per_kwh"
KEY_RECYCLING_COST = "recycling_cost_per_kwh"
KEY_CYCLE_LIFE = "cycle_life"
KEY_DOD = "dod_percent"
KEY_CALENDAR_LIFE = "calendar_life"
KEY_EXAMPLE_PRODUCT = "example_product"
KEY_WACC = "wacc"
KEY_LIFESPAN = "project_lifespan"
KEY_TAX_RATE = "tax_rate"
KEY_INFLATION = "inflation_rate"
KEY_SALVAGE = "salvage_value"
KEY_EAF_SIZE = "eaf_size"
KEY_GRID_CAP = "grid_cap"
KEY_CYCLES_PER_DAY = "cycles_per_day"
KEY_DAYS_PER_YEAR = "days_per_year"
KEY_CYCLE_DURATION_INPUT = "cycle_duration_input" # User input value
KEY_CYCLE_DURATION = "cycle_duration" # Base value from mill data
KEY_ENERGY_RATES = "energy_rates"
KEY_DEMAND_CHARGE = "demand_charge"
KEY_TOU_RAW = "tou_periods_raw"
KEY_TOU_FILLED = "tou_periods_filled"
KEY_SEASONAL = "seasonal_rates"
KEY_WINTER_MONTHS = "winter_months"
KEY_SUMMER_MONTHS = "summer_months"
KEY_SHOULDER_MONTHS = "shoulder_months"
KEY_WINTER_MULT = "winter_multiplier"
KEY_SUMMER_MULT = "summer_multiplier"
KEY_SHOULDER_MULT = "shoulder_multiplier"
# ... (add other keys as needed) ...


# --- Initialize the Dash app with Bootstrap themes & Font Awesome ---
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME], # Added Font Awesome
    suppress_callback_exceptions=True,
)
server = app.server
app.title = "Battery Profitability Tool"

# --- Default Parameters (Utility, EAF, Financial) ---
default_utility_params = {
    KEY_ENERGY_RATES: {"off_peak": 50, "mid_peak": 100, "peak": 150},
    KEY_DEMAND_CHARGE: 10,
    KEY_TOU_RAW: [ (0.0, 8.0, "off_peak"), (8.0, 10.0, "peak"), (10.0, 16.0, "mid_peak"), (16.0, 20.0, "peak"), (20.0, 24.0, "off_peak")],
    KEY_TOU_FILLED: [ (0.0, 8.0, "off_peak"), (8.0, 10.0, "peak"), (10.0, 16.0, "mid_peak"), (16.0, 20.0, "peak"), (20.0, 24.0, "off_peak")],
    KEY_SEASONAL: False, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [4, 5, 10],
    KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.2, KEY_SHOULDER_MULT: 1.1,
}
default_financial_params = {
    KEY_WACC: 0.131, KEY_LIFESPAN: 30, KEY_TAX_RATE: 0.2009,
    KEY_INFLATION: 0.024, KEY_SALVAGE: 0.1,
}
default_incentive_params = {
    "itc_enabled": False, "itc_percentage": 30, "ceic_enabled": False, "ceic_percentage": 30,
    "bonus_credit_enabled": False, "bonus_credit_percentage": 10, "sgip_enabled": False, "sgip_amount": 400,
    "ess_enabled": False, "ess_amount": 280, "mabi_enabled": False, "mabi_amount": 250,
    "cs_enabled": False, "cs_amount": 225, "custom_incentive_enabled": False,
    "custom_incentive_type": "per_kwh", "custom_incentive_amount": 100, "custom_incentive_description": "Custom incentive",
}


# --- BESS Technology Data ---
bess_technology_data = {
    "LFP": {
        KEY_EXAMPLE_PRODUCT: "Tesla Megapack 2XL (Illustrative)",
        KEY_SB_BOS_COST: 210, KEY_PCS_COST: 75, KEY_EPC_COST: 56, KEY_SYS_INT_COST: 42,
        KEY_FIXED_OM: 5, KEY_RTE: 86, KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2, KEY_RECYCLING_COST: 1,
        KEY_CYCLE_LIFE: 4000, KEY_DOD: 95, KEY_CALENDAR_LIFE: 16,
    },
    "NMC": {
        KEY_EXAMPLE_PRODUCT: "Samsung SDI E3 (Illustrative)",
        KEY_SB_BOS_COST: 250, KEY_PCS_COST: 75, KEY_EPC_COST: 63, KEY_SYS_INT_COST: 48,
        KEY_FIXED_OM: 6, KEY_RTE: 86, KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2, KEY_RECYCLING_COST: -2,
        KEY_CYCLE_LIFE: 3500, KEY_DOD: 90, KEY_CALENDAR_LIFE: 13,
    },
    "Redox Flow (Vanadium)": {
        KEY_EXAMPLE_PRODUCT: "Invinity VS3 / Generic VRFB (Illustrative)",
        KEY_SB_BOS_COST: 250, KEY_PCS_COST: 138, KEY_EPC_COST: 70, KEY_SYS_INT_COST: 60,
        KEY_FIXED_OM: 7, KEY_RTE: 68, KEY_INSURANCE: 0.6,
        KEY_DISCONNECT_COST: 3, KEY_RECYCLING_COST: 5,
        KEY_CYCLE_LIFE: 15000, KEY_DOD: 100, KEY_CALENDAR_LIFE: 20,
    },
     "Sodium-Ion": {
        KEY_EXAMPLE_PRODUCT: "Natron Energy BlueTray 4000 (Illustrative - High Power Focus)",
        KEY_SB_BOS_COST: 300, KEY_PCS_COST: 100, KEY_EPC_COST: 60, KEY_SYS_INT_COST: 50,
        KEY_FIXED_OM: 5, KEY_RTE: 90, KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2, KEY_RECYCLING_COST: 3,
        KEY_CYCLE_LIFE: 10000, KEY_DOD: 100, KEY_CALENDAR_LIFE: 20,
    },
    "Iron-Air": {
        KEY_EXAMPLE_PRODUCT: "Form Energy (Illustrative - Long Duration Focus)",
        KEY_SB_BOS_COST: 30, KEY_PCS_COST: 300, KEY_EPC_COST: 20, KEY_SYS_INT_COST: 15,
        KEY_FIXED_OM: 8, KEY_RTE: 50, KEY_INSURANCE: 0.7,
        KEY_DISCONNECT_COST: 3, KEY_RECYCLING_COST: 1,
        KEY_CYCLE_LIFE: 10000, KEY_DOD: 100, KEY_CALENDAR_LIFE: 20,
    },
    "Hybrid Supercapacitor": {
        KEY_EXAMPLE_PRODUCT: "Hycap Hybrid Supercapacitor System",
        KEY_SB_BOS_COST: 900, KEY_PCS_COST: 100, KEY_EPC_COST: 50, KEY_SYS_INT_COST: 50,
        KEY_OM_KWHR_YR: 2, # Specific O&M format
        KEY_RTE: 98, KEY_INSURANCE: 0.1,
        KEY_DISCONNECT_COST: 0.5, KEY_RECYCLING_COST: 1.0,
        KEY_CYCLE_LIFE: 100000, KEY_DOD: 100, KEY_CALENDAR_LIFE: 30,
    },
}

# --- Default BESS Parameters Store Structure ---
default_bess_params_store = {
    KEY_TECH: "LFP",
    KEY_CAPACITY: 40,
    KEY_POWER_MAX: 20,
    **bess_technology_data["LFP"] # Populate with LFP details
}
# Note: Supercap default O&M structure is handled by the presence/absence of keys


# --- Nucor Mill Data ---
# Using KEY constants where applicable for consistency
nucor_mills = { "West Virginia": { "location": "Apple Grove, WV", "type": "Sheet", "eaf_count": 2, "eaf_type": "DC", "eaf_manufacturer": "SMS", KEY_EAF_SIZE: 190, KEY_CYCLES_PER_DAY: 26, "tons_per_year": 3000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Appalachian Power", KEY_GRID_CAP: 50, }, "Auburn": { "location": "Auburn, NY", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Unknown", KEY_EAF_SIZE: 60, KEY_CYCLES_PER_DAY: 28, "tons_per_year": 510000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "New York State Electric & Gas", KEY_GRID_CAP: 25, }, "Birmingham": { "location": "Birmingham, AL", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Unknown", KEY_EAF_SIZE: 52, KEY_CYCLES_PER_DAY: 20, "tons_per_year": 310000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Alabama Power", KEY_GRID_CAP: 20, }, "Arkansas": { "location": "Blytheville, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "Demag", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 28, "tons_per_year": 2500000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 38, "utility": "Entergy Arkansas", KEY_GRID_CAP: 45, }, "Kankakee": { "location": "Bourbonnais, IL", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 73, KEY_CYCLES_PER_DAY: 39, "tons_per_year": 850000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "ComEd", KEY_GRID_CAP: 30, }, "Brandenburg": { "location": "Brandenburg, KY", "type": "Sheet", "eaf_count": 1, "eaf_type": "DC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 27, "tons_per_year": 1200000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "LG&E KU", KEY_GRID_CAP: 45, }, "Hertford": { "location": "Cofield, NC", "type": "Plate", "eaf_count": 1, "eaf_type": "DC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 30, "tons_per_year": 1350000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Dominion Energy", KEY_GRID_CAP: 45, }, "Crawfordsville": { "location": "Crawfordsville, IN", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "Brown-Boveri", KEY_EAF_SIZE: 118, KEY_CYCLES_PER_DAY: 27, "tons_per_year": 1890000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Duke Energy", KEY_GRID_CAP: 40, }, "Darlington": { "location": "Darlington, SC", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 110, KEY_CYCLES_PER_DAY: 30, "tons_per_year": 980000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Duke Energy", KEY_GRID_CAP: 40, }, "Decatur": { "location": "Decatur, AL", "type": "Sheet", "eaf_count": 2, "eaf_type": "DC", "eaf_manufacturer": "NKK-SE", KEY_EAF_SIZE: 165, KEY_CYCLES_PER_DAY: 20, "tons_per_year": 2000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Alabama Power", KEY_GRID_CAP: 48, }, "Gallatin": { "location": "Ghent, KY", "type": "Sheet", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "NKK-SE, Danieli", KEY_EAF_SIZE: 175, KEY_CYCLES_PER_DAY: 27, "tons_per_year": 2800000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Kentucky Utilities", KEY_GRID_CAP: 53, }, "Hickman": { "location": "Hickman, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 22, "tons_per_year": 2000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Mississippi County Electric Cooperative", KEY_GRID_CAP: 45, }, "Berkeley": { "location": "Huger, SC", "type": "Sheet/Beam Mill", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 154, KEY_CYCLES_PER_DAY: 26, "tons_per_year": 2430000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Santee Cooper", KEY_GRID_CAP: 46, }, "Texas": { "location": "Jewett, TX", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "SMS Concast", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 33, "tons_per_year": 1000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Oncor Electric Delivery", KEY_GRID_CAP: 30, }, "Kingman": { "location": "Kingman, AZ", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 21, "tons_per_year": 630000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "UniSource Energy Services", KEY_GRID_CAP: 30, }, "Marion": { "location": "Marion, OH", "type": "Bar Mill/Sign Pos", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "?", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 40, "tons_per_year": 1200000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "AEP Ohio", KEY_GRID_CAP: 30, }, "Nebraska": { "location": "Norfolk, NE", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 95, KEY_CYCLES_PER_DAY: 35, "tons_per_year": 1000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Nebraska Public Power District", KEY_GRID_CAP: 29, }, "Utah": { "location": "Plymouth, UT", "type": "Bar", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "Fuchs", KEY_EAF_SIZE: 51, KEY_CYCLES_PER_DAY: 42, "tons_per_year": 1290000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Rocky Mountain Power", KEY_GRID_CAP: 15, }, "Seattle": { "location": "Seattle, WA", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "Fuchs", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 29, "tons_per_year": 855000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Seattle City Light", KEY_GRID_CAP: 30, }, "Sedalia": { "location": "Sedalia, MO", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 40, KEY_CYCLES_PER_DAY: 39, "tons_per_year": 470000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Evergy", KEY_GRID_CAP: 12, }, "Tuscaloosa": { "location": "Tuscaloosa, AL", "type": "Plate", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 122, KEY_CYCLES_PER_DAY: 17, "tons_per_year": 610000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Alabama Power", KEY_GRID_CAP: 37, }, "Florida": { "location": "Frostproof, FL", "type": "?", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 40, KEY_CYCLES_PER_DAY: 38, "tons_per_year": 450000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Duke Energy Florida", KEY_GRID_CAP: 12, }, "Jackson": { "location": "Flowood, MS", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "?", KEY_EAF_SIZE: 50, KEY_CYCLES_PER_DAY: 33, "tons_per_year": 490000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Entergy Mississippi (Assumed)", KEY_GRID_CAP: 15, }, "Nucor-Yamato": { "location": "Blytheville, AR", "type": "Structural (implied)", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "?", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 25, "tons_per_year": 2500000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Mississippi County Electric Cooperative", KEY_GRID_CAP: 45, }, "Custom": { "location": "Custom Location", "type": "Custom", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Custom", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 24, "tons_per_year": 1000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Custom Utility", KEY_GRID_CAP: 35, }, }

# --- Utility Rate Data ---
# Using KEY constants where applicable
utility_rates = { "Appalachian Power": { KEY_ENERGY_RATES: {"off_peak": 45, "mid_peak": 90, "peak": 135}, KEY_DEMAND_CHARGE: 12, "tou_periods": [ (0, 7, "off_peak"), (7, 11, "peak"), (11, 16, "mid_peak"), (16, 20, "peak"), (20, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.3, KEY_SHOULDER_MULT: 1.1, }, "New York State Electric & Gas": { KEY_ENERGY_RATES: {"off_peak": 60, "mid_peak": 110, "peak": 180}, KEY_DEMAND_CHARGE: 15, "tou_periods": [ (0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "mid_peak"), (17, 21, "peak"), (21, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8], KEY_SHOULDER_MONTHS: [4, 5, 9, 10], KEY_WINTER_MULT: 1.2, KEY_SUMMER_MULT: 1.5, KEY_SHOULDER_MULT: 1.3, }, "Alabama Power": { KEY_ENERGY_RATES: {"off_peak": 40, "mid_peak": 80, "peak": 120}, KEY_DEMAND_CHARGE: 10, "tou_periods": [ (0, 8, "off_peak"), (8, 11, "peak"), (11, 15, "mid_peak"), (15, 19, "peak"), (19, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10, 11], KEY_WINTER_MULT: 0.9, KEY_SUMMER_MULT: 1.4, KEY_SHOULDER_MULT: 1.0, }, "Entergy Arkansas": { KEY_ENERGY_RATES: {"off_peak": 42, "mid_peak": 85, "peak": 130}, KEY_DEMAND_CHARGE: 11, "tou_periods": [ (0, 7, "off_peak"), (7, 10, "peak"), (10, 16, "mid_peak"), (16, 19, "peak"), (19, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 0.9, KEY_SUMMER_MULT: 1.3, KEY_SHOULDER_MULT: 1.0, }, "ComEd": { KEY_ENERGY_RATES: {"off_peak": 48, "mid_peak": 95, "peak": 140}, KEY_DEMAND_CHARGE: 13, "tou_periods": [ (0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "mid_peak"), (17, 21, "peak"), (21, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8], KEY_SHOULDER_MONTHS: [4, 5, 9, 10], KEY_WINTER_MULT: 1.1, KEY_SUMMER_MULT: 1.6, KEY_SHOULDER_MULT: 1.2, }, "LG&E KU": { KEY_ENERGY_RATES: {"off_peak": 44, "mid_peak": 88, "peak": 125}, KEY_DEMAND_CHARGE: 12.5, "tou_periods": [ (0, 7, "off_peak"), (7, 11, "peak"), (11, 17, "mid_peak"), (17, 21, "peak"), (21, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.35, KEY_SHOULDER_MULT: 1.1, }, "Dominion Energy": { KEY_ENERGY_RATES: {"off_peak": 47, "mid_peak": 94, "peak": 138}, KEY_DEMAND_CHARGE: 13.5, "tou_periods": [ (0, 6, "off_peak"), (6, 11, "peak"), (11, 16, "mid_peak"), (16, 20, "peak"), (20, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [4, 5, 10, 11], KEY_WINTER_MULT: 1.05, KEY_SUMMER_MULT: 1.45, KEY_SHOULDER_MULT: 1.15, }, "Duke Energy": { KEY_ENERGY_RATES: {"off_peak": 46, "mid_peak": 92, "peak": 135}, KEY_DEMAND_CHARGE: 14, "tou_periods": [ (0, 7, "off_peak"), (7, 10, "peak"), (10, 16, "mid_peak"), (16, 20, "peak"), (20, 24, "off_peak"), ], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 0.95, KEY_SUMMER_MULT: 1.4, KEY_SHOULDER_MULT: 1.1, }, "Kentucky Utilities": {}, "Mississippi County Electric Cooperative": { KEY_ENERGY_RATES: {"off_peak": 32.72, "mid_peak": 32.72, "peak": 32.72}, KEY_DEMAND_CHARGE: 12.28, "tou_periods": [(0, 24, "off_peak")], KEY_SEASONAL: False, KEY_WINTER_MONTHS: default_utility_params[KEY_WINTER_MONTHS], KEY_SUMMER_MONTHS: default_utility_params[KEY_SUMMER_MONTHS], KEY_SHOULDER_MONTHS: default_utility_params[KEY_SHOULDER_MONTHS], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.0, KEY_SHOULDER_MULT: 1.0, }, "Santee Cooper": { KEY_ENERGY_RATES: {"off_peak": 37.50, "mid_peak": 37.50, "peak": 57.50}, KEY_DEMAND_CHARGE: 19.26, "tou_periods": [(0, 13, "off_peak"), (13, 22, "peak"), (22, 24, "off_peak")], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [1, 2, 3, 4, 5, 9, 10, 11, 12], KEY_SUMMER_MONTHS: [6, 7, 8], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.0, KEY_SHOULDER_MULT: 1.0, }, "Oncor Electric Delivery": {}, "UniSource Energy Services": { KEY_ENERGY_RATES: {"off_peak": 52.5, "mid_peak": 52.5, "peak": 77.5}, KEY_DEMAND_CHARGE: 16.5, "tou_periods": [(0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "off_peak"), (17, 21, "peak"), (21, 24, "off_peak")], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3, 4], KEY_SUMMER_MONTHS: [5, 6, 7, 8, 9, 10], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.85, KEY_SUMMER_MULT: 1.15, KEY_SHOULDER_MULT: 1.0, }, "AEP Ohio": {}, "Nebraska Public Power District": { KEY_ENERGY_RATES: {"off_peak": 19.3, "mid_peak": 19.3, "peak": 34.4}, KEY_DEMAND_CHARGE: 19.0, "tou_periods": default_utility_params[KEY_TOU_FILLED], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.9, KEY_SUMMER_MULT: 1.1, KEY_SHOULDER_MULT: 1.0, }, "Rocky Mountain Power": { KEY_ENERGY_RATES: {"off_peak": 24.7, "mid_peak": 24.7, "peak": 48.5}, KEY_DEMAND_CHARGE: 15.79, "tou_periods": [(0, 6, "off_peak"), (6, 9, "peak"), (9, 15, "off_peak"), (15, 22, "peak"), (22, 24, "off_peak")], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.95, KEY_SUMMER_MULT: 1.05, KEY_SHOULDER_MULT: 1.0, }, "Seattle City Light": { KEY_ENERGY_RATES: {"off_peak": 55.30, "mid_peak": 55.30, "peak": 110.70}, KEY_DEMAND_CHARGE: 5.13, "tou_periods": [(0, 6, "off_peak"), (6, 22, "peak"), (22, 24, "off_peak")], KEY_SEASONAL: False, KEY_WINTER_MONTHS: default_utility_params[KEY_WINTER_MONTHS], KEY_SUMMER_MONTHS: default_utility_params[KEY_SUMMER_MONTHS], KEY_SHOULDER_MONTHS: default_utility_params[KEY_SHOULDER_MONTHS], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.0, KEY_SHOULDER_MULT: 1.0, }, "Evergy": { KEY_ENERGY_RATES: {"off_peak": 32.59, "mid_peak": 37.19, "peak": 53.91}, KEY_DEMAND_CHARGE: 9.69, "tou_periods": [(0, 24, "off_peak")], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.69, KEY_SUMMER_MULT: 1.31, KEY_SHOULDER_MULT: 1.0, }, "Duke Energy Florida": {}, "Entergy Mississippi (Assumed)": { KEY_ENERGY_RATES: {"off_peak": 41.0, "mid_peak": 41.0, "peak": 67.0}, KEY_DEMAND_CHARGE: 16.75, "tou_periods": [(0, 6, "off_peak"), (6, 10, "peak"), (10, 12, "off_peak"), (12, 20, "peak"), (20, 24, "off_peak")], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.84, KEY_SUMMER_MULT: 1.16, KEY_SHOULDER_MULT: 1.0, }, "Custom Utility": default_utility_params, }
placeholder_utilities = [ "Kentucky Utilities", "Oncor Electric Delivery", "AEP Ohio", "Duke Energy Florida", ]
for util_key in placeholder_utilities:
    if util_key in utility_rates:
        utility_rates[util_key] = utility_rates["Custom Utility"].copy()


# --- Helper Functions ---
def fill_tou_gaps(periods):
    """Fills gaps in a list of TOU periods with 'off_peak'."""
    if not periods: return [(0.0, 24.0, "off_peak")]
    clean_periods = []
    # Validate and clean input periods
    for period in periods:
        try:
            if len(period) == 3:
                start, end, rate = float(period[0]), float(period[1]), str(period[2])
                if 0 <= start < end <= 24: clean_periods.append((start, end, rate))
                else: print(f"Warning: Skipping invalid TOU period data: {period}")
            else: print(f"Warning: Skipping malformed TOU period data: {period}")
        except (TypeError, ValueError, IndexError): print(f"Warning: Skipping invalid TOU period data: {period}"); continue
    clean_periods.sort(key=lambda x: x[0])
    # Check for overlaps (optional warning)
    for i in range(len(clean_periods) - 1):
        if clean_periods[i][1] > clean_periods[i + 1][0]: print(f"Warning: Overlapping TOU periods detected between {clean_periods[i]} and {clean_periods[i+1]}.")
    # Fill gaps
    filled_periods = []; current_time = 0.0
    for start, end, rate in clean_periods:
        if start > current_time: filled_periods.append((current_time, start, "off_peak")) # Fill gap before
        filled_periods.append((start, end, rate)); current_time = end
    if current_time < 24.0: filled_periods.append((current_time, 24.0, "off_peak")) # Fill gap after
    if not filled_periods: filled_periods.append((0.0, 24.0, "off_peak")) # Handle empty case
    return filled_periods

def get_month_season_multiplier(month, seasonal_data):
    """Gets the rate multiplier for a given month based on seasonal settings."""
    if not seasonal_data.get(KEY_SEASONAL, False): return 1.0
    if month in seasonal_data.get(KEY_WINTER_MONTHS, []): return seasonal_data.get(KEY_WINTER_MULT, 1.0)
    elif month in seasonal_data.get(KEY_SUMMER_MONTHS, []): return seasonal_data.get(KEY_SUMMER_MULT, 1.0)
    elif month in seasonal_data.get(KEY_SHOULDER_MONTHS, []): return seasonal_data.get(KEY_SHOULDER_MULT, 1.0)
    else: print(f"Warning: Month {month} not found in any defined season. Using multiplier 1.0."); return 1.0

def calculate_eaf_profile(time_minutes, eaf_size=100, cycle_duration=36):
    """Generates a representative EAF power profile for a single cycle."""
    if cycle_duration <= 0: return np.zeros_like(time_minutes)
    eaf_power = np.zeros_like(time_minutes); scale = (eaf_size / 100) ** 0.6 if eaf_size > 0 else 0
    # Reference profile timings (fractions of a 28-minute reference cycle)
    ref_duration = 28.0; bore_in_end_frac = 3 / ref_duration; main_melting_end_frac = 17 / ref_duration; melting_end_frac = 20 / ref_duration
    for i, t_actual in enumerate(time_minutes):
        # Normalize time within the *actual* cycle duration
        t_norm_actual_cycle = t_actual / cycle_duration if cycle_duration > 0 else 0
        # Scale frequency of sinusoidal variations based on actual vs reference duration
        freq_scale = ref_duration / cycle_duration if cycle_duration > 0 else 1
        # Apply power levels based on normalized time within the cycle
        if t_norm_actual_cycle <= bore_in_end_frac:
            phase_progress = t_norm_actual_cycle / bore_in_end_frac if bore_in_end_frac > 0 else 0
            eaf_power[i] = (15 + (25 - 15) * phase_progress) * scale # Ramp up during bore-in
        elif t_norm_actual_cycle <= main_melting_end_frac:
            eaf_power[i] = (55 + 5 * np.sin(t_actual * 0.5 * freq_scale)) * scale # Main melting with variation
        elif t_norm_actual_cycle <= melting_end_frac:
            phase_progress = ((t_norm_actual_cycle - main_melting_end_frac) / (melting_end_frac - main_melting_end_frac)) if (melting_end_frac > main_melting_end_frac) else 0
            eaf_power[i] = (50 - (50 - 40) * phase_progress) * scale # Ramp down slightly
        else: # Refining phase
            eaf_power[i] = (20 + 5 * np.sin(t_actual * 0.3 * freq_scale)) * scale # Lower power refining with variation
    return eaf_power

def calculate_grid_bess_power(eaf_power, grid_cap, bess_power_max):
    """Calculates grid and BESS power contributions based on EAF demand and limits."""
    grid_power = np.zeros_like(eaf_power); bess_power = np.zeros_like(eaf_power)

    # --- ADDED: Handle NoneType for inputs ---
    # Provide default numeric values if None is passed
    grid_cap_val = grid_cap if grid_cap is not None else 0
    bess_power_max_val = bess_power_max if bess_power_max is not None else 0
    # --- End Add ---

    # Ensure non-negative using the validated values
    grid_cap_val = max(0, grid_cap_val)
    bess_power_max_val = max(0, bess_power_max_val)

    for i, p_eaf in enumerate(eaf_power):
        p_eaf = max(0, p_eaf) # Ensure non-negative EAF power
        # Use the validated grid_cap_val here
        if p_eaf > grid_cap_val:
            # Peak shaving: BESS discharges to cover the excess demand
            discharge_needed = p_eaf - grid_cap_val
            # Use the validated bess_power_max_val here
            actual_discharge = min(discharge_needed, bess_power_max_val) # Limited by BESS power
            bess_power[i] = actual_discharge # Positive value indicates discharge
            grid_power[i] = p_eaf - actual_discharge # Grid supplies up to its cap + remaining EAF need
        else:
            # EAF demand is within grid capacity
            grid_power[i] = p_eaf
            bess_power[i] = 0 # BESS is idle (or could be charging - not modeled here)
    return grid_power, bess_power

# --- Billing Calculation Functions ---
def create_monthly_bill_with_bess(eaf_params, bess_params, utility_params, days_in_month, month_number):
    """Calculates estimated monthly utility bill WITH BESS peak shaving."""
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)
    energy_rates = {r: rate * seasonal_mult for r, rate in utility_params.get(KEY_ENERGY_RATES, {}).items()}
    demand_charge = utility_params.get(KEY_DEMAND_CHARGE, 0) * seasonal_mult
    filled_tou_periods = utility_params.get(KEY_TOU_FILLED, [(0.0, 24.0, "off_peak")])
    eaf_size = eaf_params.get(KEY_EAF_SIZE, 100)
    # Use the user-input cycle duration if available, otherwise the base
    cycle_duration_min = eaf_params.get(KEY_CYCLE_DURATION_INPUT, eaf_params.get(KEY_CYCLE_DURATION, 36))
    if cycle_duration_min <= 0: cycle_duration_min = 36 # Fallback
    time_step_min = cycle_duration_min / 200; time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min)
    grid_cap = eaf_params.get(KEY_GRID_CAP, 50); bess_power_max = bess_params.get(KEY_POWER_MAX, 20)
    grid_power_cycle, bess_power_cycle = calculate_grid_bess_power(eaf_power_cycle, grid_cap, bess_power_max)
    peak_demand_kw = np.max(grid_power_cycle) * 1000 if len(grid_power_cycle) > 0 else 0
    # Calculate energy consumed/discharged per cycle
    bess_energy_cycle_discharged = np.sum(bess_power_cycle) * (time_step_min / 60) # MWh
    grid_energy_cycle = np.sum(grid_power_cycle) * (time_step_min / 60) # MWh
    # Calculate monthly costs based on TOU rates
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}; total_energy_cost = 0; total_grid_energy_month = 0
    cycles_per_day = eaf_params.get(KEY_CYCLES_PER_DAY, 24)
    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start; period_fraction = period_hours / 24.0
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month
            period_cost = energy_in_period_month * energy_rates[period] # MWh * $/MWh
            tou_energy_costs[period] += period_cost; total_energy_cost += period_cost; total_grid_energy_month += energy_in_period_month
        else: print(f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict.")
    demand_cost = peak_demand_kw * demand_charge # kW * $/kW
    total_bill = total_energy_cost + demand_cost
    return {"energy_cost": total_energy_cost, "demand_cost": demand_cost, "total_bill": total_bill, "peak_demand_kw": peak_demand_kw, "energy_consumed_mwh": total_grid_energy_month, "tou_breakdown": tou_energy_costs, "bess_discharged_per_cycle_mwh": bess_energy_cycle_discharged}

def create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month_number):
    """Calculates estimated monthly utility bill WITHOUT BESS."""
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)
    energy_rates = {r: rate * seasonal_mult for r, rate in utility_params.get(KEY_ENERGY_RATES, {}).items()}
    demand_charge = utility_params.get(KEY_DEMAND_CHARGE, 0) * seasonal_mult
    filled_tou_periods = utility_params.get(KEY_TOU_FILLED, [(0.0, 24.0, "off_peak")])
    eaf_size = eaf_params.get(KEY_EAF_SIZE, 100)
    cycle_duration_min = eaf_params.get(KEY_CYCLE_DURATION_INPUT, eaf_params.get(KEY_CYCLE_DURATION, 36))
    if cycle_duration_min <= 0: cycle_duration_min = 36
    time_step_min = cycle_duration_min / 200; time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min)
    grid_power_cycle = eaf_power_cycle # No BESS, grid takes full load
    peak_demand_kw = np.max(grid_power_cycle) * 1000 if len(grid_power_cycle) > 0 else 0
    grid_energy_cycle = np.sum(grid_power_cycle) * (time_step_min / 60) # MWh
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}; total_energy_cost = 0; total_grid_energy_month = 0
    cycles_per_day = eaf_params.get(KEY_CYCLES_PER_DAY, 24)
    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start; period_fraction = period_hours / 24.0
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month
            period_cost = energy_in_period_month * energy_rates[period]
            tou_energy_costs[period] += period_cost; total_energy_cost += period_cost; total_grid_energy_month += energy_in_period_month
        else: print(f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict.")
    demand_cost = peak_demand_kw * demand_charge
    total_bill = total_energy_cost + demand_cost
    return {"energy_cost": total_energy_cost, "demand_cost": demand_cost, "total_bill": total_bill, "peak_demand_kw": peak_demand_kw, "energy_consumed_mwh": total_grid_energy_month, "tou_breakdown": tou_energy_costs}

def calculate_annual_billings(eaf_params, bess_params, utility_params):
    """Calculates annual bills and savings by summing monthly results."""
    # --- START DEBUG PRINT ---
    import pprint
    print("\n--- DEBUG: calculate_annual_billings ---")
    print("Received bess_params:")
    pprint.pprint(bess_params)
    print("--------------------------------------\n")
    # --- END DEBUG PRINT ---
    monthly_bills_with_bess = []; monthly_bills_without_bess = []; monthly_savings = []
    # ... (rest of the function remains the same)
    year = 2025 # Assume a non-leap year for simplicity
    # Ensure TOU periods are filled if missing
    if KEY_TOU_FILLED not in utility_params or not utility_params[KEY_TOU_FILLED]:
        raw_periods = utility_params.get(KEY_TOU_RAW, default_utility_params[KEY_TOU_RAW])
        utility_params[KEY_TOU_FILLED] = fill_tou_gaps(raw_periods)
        print("Warning: Filled TOU periods were missing, generated them.")
    # Calculate for each month
    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]
        bill_with_bess = create_monthly_bill_with_bess(eaf_params, bess_params, utility_params, days_in_month, month)
        bill_without_bess = create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month)
        savings = bill_without_bess["total_bill"] - bill_with_bess["total_bill"]
        monthly_bills_with_bess.append(bill_with_bess); monthly_bills_without_bess.append(bill_without_bess); monthly_savings.append(savings)
    # Sum monthly results for annual totals
    annual_bill_with_bess = sum(bill["total_bill"] for bill in monthly_bills_with_bess)
    annual_bill_without_bess = sum(bill["total_bill"] for bill in monthly_bills_without_bess)
    annual_savings = sum(monthly_savings)
    return {"monthly_bills_with_bess": monthly_bills_with_bess, "monthly_bills_without_bess": monthly_bills_without_bess, "monthly_savings": monthly_savings, "annual_bill_with_bess": annual_bill_with_bess, "annual_bill_without_bess": annual_bill_without_bess, "annual_savings": annual_savings}

# --- Refactored Cost Calculation Helper ---
def calculate_initial_bess_cost(bess_params):
    """Calculates the initial gross capital cost of the BESS."""
    # --- ADDED: Handle NoneType for capacity/power ---
    capacity_mwh = bess_params.get(KEY_CAPACITY, 0)
    power_mw = bess_params.get(KEY_POWER_MAX, 0)
    capacity_mwh = capacity_mwh if capacity_mwh is not None else 0
    power_mw = power_mw if power_mw is not None else 0
    # --- End Add ---

    capacity_kwh = capacity_mwh * 1000
    power_kw = power_mw * 1000

    sb_bos_cost = bess_params.get(KEY_SB_BOS_COST, 0) * capacity_kwh
    pcs_cost = bess_params.get(KEY_PCS_COST, 0) * power_kw
    epc_cost = bess_params.get(KEY_EPC_COST, 0) * capacity_kwh
    sys_int_cost = bess_params.get(KEY_SYS_INT_COST, 0) * capacity_kwh

    total_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost
    return total_cost

# --- Incentive Calculation Function ---
def calculate_incentives(bess_params, incentive_params):
    """Calculate total incentives based on selected programs and BESS cost."""
    # --- START DEBUG PRINT ---
    import pprint
    print("\n--- DEBUG: calculate_incentives ---")
    print("Received bess_params:")
    pprint.pprint(bess_params)
    print("---------------------------------\n")
    # --- END DEBUG PRINT ---
    # REMOVED call to ensure_correct_technology_parameters
    # ... (rest of the function remains the same)

    total_incentive = 0
    incentive_breakdown = {}

    # --- Calculate Initial BESS Cost using helper function ---
    total_cost = calculate_initial_bess_cost(bess_params)
    capacity_mwh = bess_params.get(KEY_CAPACITY, 0)
    capacity_kwh = capacity_mwh * 1000
    # --- End Cost Calculation ---

    def get_incentive_param(key, default): return incentive_params.get(key, default)

    # Calculate individual incentives
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

    # Apply rules (e.g., ITC/CEIC exclusivity)
    applied_federal_base = 0; federal_base_desc = ""
    if itc_enabled and ceic_enabled:
        if itc_amount >= ceic_amount: applied_federal_base = itc_amount; federal_base_desc = "Investment Tax Credit (ITC)"
        else: applied_federal_base = ceic_amount; federal_base_desc = "Clean Electricity Investment Credit (CEIC)"
    elif itc_enabled: applied_federal_base = itc_amount; federal_base_desc = "Investment Tax Credit (ITC)"
    elif ceic_enabled: applied_federal_base = ceic_amount; federal_base_desc = "Clean Electricity Investment Credit (CEIC)"

    # Sum up applied incentives
    if applied_federal_base > 0: total_incentive += applied_federal_base; incentive_breakdown[federal_base_desc] = applied_federal_base
    if bonus_amount > 0: total_incentive += bonus_amount; incentive_breakdown["Bonus Credits"] = bonus_amount
    if sgip_amount > 0: total_incentive += sgip_amount; incentive_breakdown["CA Self-Generation Incentive Program"] = sgip_amount
    if ess_amount > 0: total_incentive += ess_amount; incentive_breakdown["CT Energy Storage Solutions"] = ess_amount
    if mabi_amount > 0: total_incentive += mabi_amount; incentive_breakdown["NY Market Acceleration Bridge Incentive"] = mabi_amount
    if cs_amount > 0: total_incentive += cs_amount; incentive_breakdown["MA Connected Solutions"] = cs_amount
    if custom_amount > 0: total_incentive += custom_amount; incentive_breakdown[custom_desc] = custom_amount

    return {"total_incentive": total_incentive, "breakdown": incentive_breakdown, "calculated_initial_cost": total_cost}


# --- Financial Metrics Calculation Function ---
def calculate_financial_metrics(bess_params, financial_params, eaf_params, annual_savings, incentives_results):
    """Calculate NPV, IRR, payback period, etc. using detailed BESS parameters."""
    # --- START DEBUG PRINT ---
    import pprint
    print("\n--- DEBUG: calculate_financial_metrics ---")
    print("Received bess_params:")
    pprint.pprint(bess_params)
    print("----------------------------------------\n")
    # --- END DEBUG PRINT ---

    # --- Get Parameters ---
    technology = bess_params.get(KEY_TECH, "LFP")
    print(f"DEBUG FINANCE: Using technology: {technology}")
    print(f"DEBUG: BESS parameters used: cycle_life={bess_params.get(KEY_CYCLE_LIFE)}, rte={bess_params.get(KEY_RTE)}")

    # --- ADDED: Handle NoneType for capacity/power ---
    capacity_mwh = bess_params.get(KEY_CAPACITY, 0)
    power_mw = bess_params.get(KEY_POWER_MAX, 0)
    capacity_mwh = capacity_mwh if capacity_mwh is not None else 0
    power_mw = power_mw if power_mw is not None else 0
    # --- End Add ---

    capacity_kwh = capacity_mwh * 1000
    power_kw = power_mw * 1000

    # Opex params (ensure defaults if None)
    fixed_om_per_kw_yr = bess_params.get(KEY_FIXED_OM, 0)
    om_cost_per_kwh_yr = bess_params.get(KEY_OM_KWHR_YR, None) # Keep None possibility here
    insurance_percent_yr = bess_params.get(KEY_INSURANCE, 0)
    fixed_om_per_kw_yr = fixed_om_per_kw_yr if fixed_om_per_kw_yr is not None else 0
    insurance_percent_yr = insurance_percent_yr if insurance_percent_yr is not None else 0


    # Decommissioning params (ensure defaults if None)
    disconnect_cost_per_kwh = bess_params.get(KEY_DISCONNECT_COST, 0)
    recycling_cost_per_kwh = bess_params.get(KEY_RECYCLING_COST, 0) # Can be negative
    disconnect_cost_per_kwh = disconnect_cost_per_kwh if disconnect_cost_per_kwh is not None else 0
    recycling_cost_per_kwh = recycling_cost_per_kwh if recycling_cost_per_kwh is not None else 0


    # Performance params (ensure defaults if None)
    cycle_life = bess_params.get(KEY_CYCLE_LIFE, 5000)
    calendar_life = bess_params.get(KEY_CALENDAR_LIFE, 15) # Years
    cycle_life = cycle_life if cycle_life is not None else 5000
    calendar_life = calendar_life if calendar_life is not None else 15


    # Financial Parameters (ensure defaults if None)
    years = int(financial_params.get(KEY_LIFESPAN, 30))
    wacc = financial_params.get(KEY_WACC, 0.131)
    inflation_rate = financial_params.get(KEY_INFLATION, 0.024)
    tax_rate = financial_params.get(KEY_TAX_RATE, 0.2009)
    years = years if years is not None else 30
    wacc = wacc if wacc is not None else 0.131
    inflation_rate = inflation_rate if inflation_rate is not None else 0.024
    tax_rate = tax_rate if tax_rate is not None else 0.2009


    # EAF Parameters for battery life calculation (ensure defaults if None)
    days_per_year = eaf_params.get(KEY_DAYS_PER_YEAR, 300)
    cycles_per_day = eaf_params.get(KEY_CYCLES_PER_DAY, 24)
    days_per_year = days_per_year if days_per_year is not None else 300
    cycles_per_day = cycles_per_day if cycles_per_day is not None else 24


    # --- Initial Calculations ---
    # Calculate Initial Capital Cost using helper (already handles None inside)
    total_initial_cost = calculate_initial_bess_cost(bess_params)

    # Net Initial Cost (Year 0)
    total_incentive = incentives_results.get("total_incentive", 0)
    net_initial_cost = total_initial_cost - total_incentive
    if net_initial_cost < 0: print("Warning: Total incentives exceed calculated initial BESS cost.")

    # Calculate Annual O&M Cost (Year 1)
    # Handle different O&M structures
    om_base_cost = 0 # Initialize
    if om_cost_per_kwh_yr is not None:
         # Use $/kWh/yr if available (e.g., for Supercapacitor)
         om_base_cost = om_cost_per_kwh_yr * capacity_kwh
    elif fixed_om_per_kw_yr is not None: # Check fixed_om_per_kw_yr which now has a default
         # Otherwise use fixed $/kW/yr
         om_base_cost = fixed_om_per_kw_yr * power_kw
    else:
         # This case should be less likely now with defaults
         print(f"Warning: No O&M cost defined or retrieved for technology {technology}")

    insurance_cost = (insurance_percent_yr / 100.0) * total_initial_cost # Insurance based on gross cost
    total_initial_om_cost = om_base_cost + insurance_cost

    # --- Battery Life & Replacement Calculation ---
    # Calculate equivalent full cycles per year
    if days_per_year <= 0 or cycles_per_day <= 0:
        cycles_per_year_equiv = 0
    else:
        cycles_per_year_equiv = cycles_per_day * days_per_year

    # Calculate life limited by cycles
    if cycle_life <= 0 or cycles_per_year_equiv <= 0:
        battery_life_years_cycles = float('inf')
    else:
        battery_life_years_cycles = cycle_life / cycles_per_year_equiv

    # Effective battery life is minimum of calendar and cycle life
    battery_replacement_interval = min(calendar_life, battery_life_years_cycles)
    if battery_replacement_interval <= 0 or pd.isna(battery_replacement_interval):
        battery_replacement_interval = float('inf')
        print("Warning: Calculated battery replacement interval is zero or invalid. No replacements will be scheduled.")

    # --- Cash Flow Calculation Loop ---
    cash_flows = [-net_initial_cost]

    for year in range(1, years + 1):
        # Inflated Savings and O&M Costs for year t
        savings_t = annual_savings * ((1 + inflation_rate) ** (year - 1))
        o_m_cost_t = total_initial_om_cost * ((1 + inflation_rate) ** (year - 1))

        # Recurring Replacement Cost Logic
        replacement_cost_year = 0
        if battery_replacement_interval != float('inf'):
            if year > 0 and abs(year % battery_replacement_interval) < 0.01 or \
               abs(year % battery_replacement_interval - battery_replacement_interval) < 0.01:
                 inflated_replacement_cost = total_initial_cost * ((1 + inflation_rate) ** (year - 1))
                 replacement_cost_year = inflated_replacement_cost
                 print(f"DEBUG: Battery replacement cost ${replacement_cost_year:,.0f} applied in year {year} (Interval: {battery_replacement_interval:.1f} yrs)")
            elif battery_replacement_interval < 1 and year >= 1:
                 replacements_per_year = int(1 / battery_replacement_interval) # Approx
                 inflated_replacement_cost = total_initial_cost * ((1 + inflation_rate) ** (year - 1))
                 replacement_cost_year = inflated_replacement_cost * replacements_per_year
                 print(f"DEBUG: Multiple ({replacements_per_year}) battery replacements costing ${replacement_cost_year:,.0f} applied in year {year}")

        # EBT (Earnings Before Tax)
        ebt = savings_t - o_m_cost_t - replacement_cost_year
        taxes = ebt * tax_rate if ebt > 0 else 0
        net_cash_flow = savings_t - o_m_cost_t - replacement_cost_year - taxes

        # Decommissioning Costs (Applied ONLY in the final year)
        if year == years:
            decomm_cost_base = (disconnect_cost_per_kwh + recycling_cost_per_kwh) * capacity_kwh
            inflated_decomm_cost = decomm_cost_base * ((1 + inflation_rate) ** (year - 1))
            decomm_cost_after_tax = inflated_decomm_cost * (1 - tax_rate)
            net_cash_flow -= decomm_cost_after_tax

        cash_flows.append(net_cash_flow)

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

    # --- Payback Period Calculation (Simple) ---
    cumulative_cash_flow = 0.0; payback_years = float('inf')
    if cash_flows[0] >= 0:
        payback_years = 0.0
    else:
        cumulative_cash_flow = cash_flows[0]
        for year_pbk in range(1, len(cash_flows)):
            current_year_cf = cash_flows[year_pbk]
            if current_year_cf is None: current_year_cf = 0 # Handle potential None in cash flows
            if cumulative_cash_flow + current_year_cf >= 0:
                fraction_needed = abs(cumulative_cash_flow) / current_year_cf if current_year_cf is not None and current_year_cf > 0 else 0
                payback_years = (year_pbk - 1) + fraction_needed
                break
            cumulative_cash_flow += current_year_cf
        # If loop finishes without payback, payback_years remains 'inf'

    return {
        "npv": npv_val,
        "irr": irr_val,
        "payback_years": payback_years,
        "cash_flows": cash_flows,
        "net_initial_cost": net_initial_cost,
        "total_initial_cost": total_initial_cost,
        "battery_life_years": battery_replacement_interval,
        "annual_savings_year1": annual_savings,
        "initial_om_cost_year1": total_initial_om_cost,
    }


# --- Optimization Function ---
def optimize_battery_size(eaf_params, utility_params, financial_params, incentive_params, bess_base_params):
    """Find optimal battery size (Capacity MWh, Power MW) for best ROI using NPV as metric."""
    # REMOVED call to ensure_correct_technology_parameters

    technology = bess_base_params.get(KEY_TECH, "LFP")
    print(f"DEBUG OPTIMIZE: Using base technology: {technology}")

    # Define search space (adjust ranges and step count as needed)
    capacity_options = np.linspace(5, 100, 10) # 10 steps from 5 to 100 MWh
    power_options = np.linspace(2, 50, 10)    # 10 steps from 2 to 50 MW

    best_npv = -float("inf"); best_capacity = None; best_power = None; best_metrics = None
    optimization_results = []
    print(f"Starting optimization: {len(capacity_options)} capacities, {len(power_options)} powers...")
    count = 0; total_combinations = len(capacity_options) * len(power_options)

    for capacity in capacity_options:
        for power in power_options:
            count += 1
            print(f"  Testing {count}/{total_combinations}: Cap={capacity:.1f} MWh, Pow={power:.1f} MW")
            # Check C-Rate constraint (example: 0.2C to 2.5C)
            c_rate = power / capacity if capacity > 0 else float("inf")
            if not (0.2 <= c_rate <= 2.5):
                print(f"    Skipping C-rate {c_rate:.2f} (out of range 0.2-2.5)")
                continue

            # Create test BESS parameters: Start with base tech params, override size
            test_bess_params = bess_base_params.copy()
            test_bess_params[KEY_CAPACITY] = capacity
            test_bess_params[KEY_POWER_MAX] = power

            try:
                # Run calculations for this specific size
                billing_results = calculate_annual_billings(eaf_params, test_bess_params, utility_params)
                annual_savings = billing_results["annual_savings"]
                incentive_results = calculate_incentives(test_bess_params, incentive_params)
                metrics = calculate_financial_metrics(test_bess_params, financial_params, eaf_params, annual_savings, incentive_results)

                current_result = {
                    "capacity": capacity, "power": power, "npv": metrics["npv"], "irr": metrics["irr"],
                    "payback_years": metrics["payback_years"], "annual_savings": annual_savings,
                    "net_initial_cost": metrics["net_initial_cost"],
                }
                optimization_results.append(current_result)

                # Check if this is the best result so far
                if pd.notna(metrics["npv"]) and metrics["npv"] > best_npv:
                    best_npv = metrics["npv"]; best_capacity = capacity; best_power = power
                    best_metrics = metrics # Store full metrics for the best combo
                    print(f"    *** New best NPV found: ${best_npv:,.0f} ***")

            except Exception as e:
                print(f"    Error during optimization step (Cap={capacity:.1f}, Pow={power:.1f}): {e}")
                # Log error for this combination
                optimization_results.append({"capacity": capacity, "power": power, "npv": float("nan"), "error": str(e)})

    print("Optimization finished.")
    return {"best_capacity": best_capacity, "best_power": best_power, "best_npv": best_npv, "best_metrics": best_metrics, "all_results": optimization_results}


# --- Application Layout ---
def create_technology_comparison_table(current_tech, capacity_mwh, power_mw):
    """Create a comparison table of different battery technologies based on current size."""
    def fmt_c(v): return f"${v:,.0f}" if pd.notna(v) else "N/A"

    techs_to_compare = list(bess_technology_data.keys())
    if current_tech not in techs_to_compare and current_tech:
        techs_to_compare.append(current_tech) # Ensure current is listed if custom

    comp_data = []
    capacity_kwh = capacity_mwh * 1000
    power_kw = power_mw * 1000

    for tech in techs_to_compare:
        if tech not in bess_technology_data: continue
        tech_data = bess_technology_data[tech]

        # Calculate costs for the *current* size using this tech's unit costs
        sb_bos_cost = tech_data.get(KEY_SB_BOS_COST, 0) * capacity_kwh
        pcs_cost = tech_data.get(KEY_PCS_COST, 0) * power_kw
        epc_cost = tech_data.get(KEY_EPC_COST, 0) * capacity_kwh
        sys_int_cost = tech_data.get(KEY_SYS_INT_COST, 0) * capacity_kwh
        total_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost

        # Calculate annual O&M cost for the *current* size
        if KEY_OM_KWHR_YR in tech_data:
            annual_om = tech_data[KEY_OM_KWHR_YR] * capacity_kwh
        else:
            annual_om = tech_data.get(KEY_FIXED_OM, 0) * power_kw

        cycle_life = tech_data.get(KEY_CYCLE_LIFE, 0)
        calendar_life = tech_data.get(KEY_CALENDAR_LIFE, 0)
        rte = tech_data.get(KEY_RTE, 0)

        # Calculate combined energy cost ($/kWh) and power cost ($/kW) from defaults
        energy_cost_per_kwh = tech_data.get(KEY_SB_BOS_COST, 0) + tech_data.get(KEY_EPC_COST, 0) + tech_data.get(KEY_SYS_INT_COST, 0)
        power_cost_per_kw = tech_data.get(KEY_PCS_COST, 0)

        row = {
            'Technology': tech + (' (Current)' if tech == current_tech else ''),
            'Cycle Life': f"{cycle_life:,}",
            'Calendar Life (yrs)': f"{calendar_life:.1f}",
            'RTE (%)': f"{rte:.1f}",
            'Capital Cost': fmt_c(total_cost),
            'Annual O&M': fmt_c(annual_om),
            'Unit Energy Cost ($/kWh)': f"${energy_cost_per_kwh:.0f}",
            'Unit Power Cost ($/kW)': f"${power_cost_per_kw:.0f}"
        }
        comp_data.append(row)

    if not comp_data: return html.Div("No technology data available for comparison.")

    comparison_table = dash_table.DataTable(
        data=comp_data,
        columns=[{"name": i, "id": i} for i in comp_data[0].keys()],
        style_cell={'textAlign': 'center', 'padding': '5px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f0f0f0'},
        style_cell_conditional=[
            {'if': {'column_id': 'Technology'}, 'textAlign': 'left', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{Technology} contains "Current"'}, 'backgroundColor': '#e6f7ff'}
        ],
        style_table={'overflowX': 'auto'}
    )
    return comparison_table

# Helper function to create input groups for BESS parameters with Tooltips
def create_bess_input_group(label, input_id, value, unit, tooltip_text=None, type="number", step=None, min_val=0, style=None): # Added style argument
    """Creates a standard row for a BESS parameter input with label, input, unit, optional tooltip, and optional style."""
    label_content = [label]
    if tooltip_text:
        tooltip_id = f"{input_id}-tooltip"
        label_content.extend([
            " ", # Add space
            html.I(className="fas fa-info-circle", id=tooltip_id, style={'cursor': 'pointer', 'color': '#6c757d'}), # Font Awesome icon
            dbc.Tooltip(tooltip_text, target=tooltip_id, placement="right")
        ])

    # Apply the style to the outer Row component
    row_style = style if style is not None else {}

    return dbc.Row(
        [
            dbc.Label(label_content, html_for=input_id, width=6),
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
        style=row_style # Apply the style here
    )

# --- Main Layout Definition ---
app.layout = dbc.Container(fluid=True, className="bg-light min-vh-100 py-4", children=[
    # Stores
    dcc.Store(id=STORE_EAF, data=nucor_mills["Custom"]),
    dcc.Store(id=STORE_UTILITY, data=utility_rates["Custom Utility"]),
    dcc.Store(id=STORE_BESS, data=default_bess_params_store),
    dcc.Store(id=STORE_FINANCIAL, data=default_financial_params),
    dcc.Store(id=STORE_INCENTIVE, data=default_incentive_params),
    dcc.Store(id=STORE_RESULTS, data={}),
    dcc.Store(id=STORE_OPTIMIZATION, data={}),

    html.H1("Battery Profitability Tool", className="mb-4 text-center"),
    # Error Containers
    dbc.Alert(id=ID_VALIDATION_ERR, color="danger", is_open=False, style={"max-width": "800px", "margin": "10px auto"}),
    dbc.Alert(id=ID_CALCULATION_ERR, color="warning", is_open=False, style={"max-width": "800px", "margin": "10px auto"}),

    # Tabs
    dbc.Tabs(id=ID_MAIN_TABS, active_tab="tab-mill", children=[
        # Mill Selection Tab
        dbc.Tab(label="1. Mill Selection", tab_id="tab-mill", children=[
             dbc.Container(children=[
                html.H3("Select Nucor Mill", className="mb-3"),
                html.P("Choose a mill to pre-fill parameters, or select 'Custom' to enter values manually.", className="text-muted mb-4"),
                html.Div([
                    html.Label("Mill Selection:", className="form-label"),
                    dcc.Dropdown(id=ID_MILL_DROPDOWN, options=[{"label": f"Nucor Steel {mill}", "value": mill} for mill in nucor_mills.keys()], value="Custom", clearable=False, className="form-select mb-3"),
                ], className="mb-4"),
                dbc.Card(id=ID_MILL_INFO_CARD, className="mb-4"),
                html.Div(dbc.Button("Continue to Parameters", id=ID_CONTINUE_PARAMS_BTN, n_clicks=0, color="primary", className="mt-3"), className="d-flex justify-content-center"),
             ])
        ]), # End Tab 1

        # Parameters Tab
        dbc.Tab(label="2. System Parameters", tab_id="tab-params", children=[
            dbc.Container(children=[
                dbc.Row([
                    # Left Column: Utility & EAF
                    dbc.Col(md=6, children=[
                        dbc.Card(className="p-3 mb-4", children=[ # Utility Card
                            html.H4("Utility Rates", className="mb-3"),
                            html.Div([ html.Label("Utility Provider:", className="form-label"), dcc.Dropdown(id=ID_UTILITY_DROPDOWN, options=[{"label": utility, "value": utility} for utility in utility_rates.keys()], value="Custom Utility", clearable=False, className="form-select mb-3"), ], className="mb-3"),
                            html.Div([ html.Label("Off-Peak Rate ($/MWh):", className="form-label"), dcc.Input(id=ID_OFF_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["off_peak"], min=0, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Mid-Peak Rate ($/MWh):", className="form-label"), dcc.Input(id=ID_MID_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["mid_peak"], min=0, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Peak Rate ($/MWh):", className="form-label"), dcc.Input(id=ID_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["peak"], min=0, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Demand Charge ($/kW/month):", className="form-label"), dcc.Input(id=ID_DEMAND_CHARGE, type="number", value=default_utility_params[KEY_DEMAND_CHARGE], min=0, className="form-control"), ], className="mb-2"),
                            dbc.Checklist(id=ID_SEASONAL_TOGGLE, options=[{"label": "Enable Seasonal Rate Variations", "value": "enabled"}], value=["enabled"] if default_utility_params[KEY_SEASONAL] else [], switch=True, className="mb-3"),
                            html.Div(id=ID_SEASONAL_CONTAINER, className="mb-3 border p-2 rounded", style={"display": "none"}),
                            html.H5("Time-of-Use Periods", className="mb-2"),
                            html.P("Define periods covering 24 hours. Gaps will be filled with Off-Peak.", className="small text-muted"),
                            html.Div(id=ID_TOU_CONTAINER), # Populated by callback
                            dbc.Button("Add TOU Period", id=ID_ADD_TOU_BTN, n_clicks=0, size="sm", outline=True, color="success", className="mt-2"),
                        ]),
                        dbc.Card(className="p-3", children=[ # EAF Card
                            html.H4("EAF Parameters", className="mb-3"),
                            html.Div([ html.Label("EAF Size (tons):", className="form-label"), dcc.Input(id=ID_EAF_SIZE, type="number", value=nucor_mills["Custom"][KEY_EAF_SIZE], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Number of EAFs:", className="form-label"), dcc.Input(id=ID_EAF_COUNT, type="number", value=nucor_mills["Custom"]["eaf_count"], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Grid Power Limit (MW):", className="form-label"), dcc.Input(id=ID_GRID_CAP, type="number", value=nucor_mills["Custom"][KEY_GRID_CAP], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("EAF Cycles per Day:", className="form-label"), dcc.Input(id=ID_CYCLES_PER_DAY, type="number", value=nucor_mills["Custom"][KEY_CYCLES_PER_DAY], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Avg. Cycle Duration (minutes):", className="form-label"), dcc.Input(id=ID_CYCLE_DURATION, type="number", value=nucor_mills["Custom"][KEY_CYCLE_DURATION], min=1, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Operating Days per Year:", className="form-label"), dcc.Input(id=ID_DAYS_PER_YEAR, type="number", value=nucor_mills["Custom"][KEY_DAYS_PER_YEAR], min=1, max=366, className="form-control"), ], className="mb-2"),
                        ]),
                    ]), # End Left Column

                    # Right Column: BESS & Financial
                    dbc.Col(md=6, children=[
                        dbc.Card(className="p-3 mb-4", children=[ # BESS Card
                            html.H4("BESS Parameters", className="mb-3"),
                            # --- Overall Size Inputs ---
                            create_bess_input_group("Total Energy Capacity:", ID_BESS_CAPACITY, default_bess_params_store[KEY_CAPACITY], "MWh", min_val=0.1, tooltip_text="Total energy the BESS can store."),
                            create_bess_input_group("Total Power Rating:", ID_BESS_POWER, default_bess_params_store[KEY_POWER_MAX], "MW", min_val=0.1, tooltip_text="Maximum rate of charge/discharge."),
                            html.Div(id=ID_BESS_C_RATE_DISPLAY, className="mt-2 mb-2 text-muted small"), # C-Rate Display
                            html.Hr(),
                            # --- Technology Selection ---
                            html.Div([
                                dbc.Label("Select BESS Technology:", html_for=ID_BESS_TECH_DROPDOWN),
                                dcc.Dropdown(
                                    id=ID_BESS_TECH_DROPDOWN,
                                    options=[{'label': tech, 'value': tech} for tech in bess_technology_data.keys()],
                                    value=default_bess_params_store[KEY_TECH],
                                    clearable=False,
                                    className="mb-2"
                                ),
                                html.P(id=ID_BESS_EXAMPLE_PRODUCT, className="small text-muted fst-italic")
                            ], className="mb-3"),
                            html.Hr(),

                            # --- Detailed Parameters ---
                            dbc.Card([ # Capex Card
                                dbc.CardHeader("Capex (Unit Costs)"),
                                dbc.CardBody([
                                    create_bess_input_group("SB + BOS Cost:", ID_BESS_SB_BOS_COST, default_bess_params_store[KEY_SB_BOS_COST], "$/kWh", tooltip_text="Storage Block (Cells, Modules, Racks) + Balance of System (HVAC, Fire Suppression, etc.) cost per kWh."),
                                    create_bess_input_group("PCS Cost:", ID_BESS_PCS_COST, default_bess_params_store[KEY_PCS_COST], "$/kW", tooltip_text="Power Conversion System (Inverters, Transformers) cost per kW."),
                                    create_bess_input_group("System Integration:", ID_BESS_SYS_INT_COST, default_bess_params_store[KEY_SYS_INT_COST], "$/kWh", tooltip_text="Engineering, Software, Commissioning cost per kWh."),
                                    create_bess_input_group("EPC Cost:", ID_BESS_EPC_COST, default_bess_params_store[KEY_EPC_COST], "$/kWh", tooltip_text="Engineering, Procurement, Construction (Installation Labor, Site Prep) cost per kWh."),
                                ])
                            ], className="mb-3"),

                            dbc.Card([ # Opex Card
                                dbc.CardHeader("Opex"),
                                dbc.CardBody([
                                    # Conditional O&M Input (Populated by callback)
                                    html.Div(id=ID_BESS_OPEX_CONTAINER),
                                    create_bess_input_group("Round Trip Efficiency:", ID_BESS_RTE, default_bess_params_store[KEY_RTE], "%", min_val=1, tooltip_text="AC-to-AC efficiency for a full charge/discharge cycle."),
                                    create_bess_input_group("Insurance Rate:", ID_BESS_INSURANCE, default_bess_params_store[KEY_INSURANCE], "%/yr", step=0.01, tooltip_text="Annual insurance cost as a percentage of initial capital cost."),
                                ])
                            ], className="mb-3"),

                            dbc.Card([ # Decommissioning Card
                                dbc.CardHeader("Decommissioning"),
                                dbc.CardBody([
                                    create_bess_input_group("Disconnect/Removal:", ID_BESS_DISCONNECT_COST, default_bess_params_store[KEY_DISCONNECT_COST], "$/kWh", min_val=None, tooltip_text="Cost to disconnect and remove the system at end-of-life."), # Allow negative later?
                                    create_bess_input_group("Recycling/Disposal:", ID_BESS_RECYCLING_COST, default_bess_params_store[KEY_RECYCLING_COST], "$/kWh", min_val=None, tooltip_text="Net cost of recycling or disposing of components (can be negative if valuable materials)."), # Allow negative
                                ])
                            ], className="mb-3"),

                            dbc.Card([ # Performance Card
                                dbc.CardHeader("Performance"),
                                dbc.CardBody([
                                    create_bess_input_group("Cycle Life:", ID_BESS_CYCLE_LIFE, default_bess_params_store[KEY_CYCLE_LIFE], "cycles", min_val=100, tooltip_text="Number of full charge/discharge cycles until end-of-life (e.g., 80% capacity retention)."),
                                    create_bess_input_group("Depth of Discharge:", ID_BESS_DOD, default_bess_params_store[KEY_DOD], "%", min_val=1, tooltip_text="Recommended maximum percentage of capacity to discharge per cycle."),
                                    create_bess_input_group("Calendar Life:", ID_BESS_CALENDAR_LIFE, default_bess_params_store[KEY_CALENDAR_LIFE], "years", min_val=1, tooltip_text="Expected lifespan based on time, regardless of cycles."),
                                ])
                            ]),
                        ]), # End BESS Card

                        dbc.Card(className="p-3", children=[ # Financial Card
                            html.H4("Financial Parameters", className="mb-3"),
                            html.Div([ html.Label("WACC (%):", className="form-label"), dcc.Input(id=ID_WACC, type="number", value=round(default_financial_params[KEY_WACC] * 100, 1), min=0, max=100, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Project Lifespan (years):", className="form-label"), dcc.Input(id=ID_LIFESPAN, type="number", value=default_financial_params[KEY_LIFESPAN], min=1, max=50, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Tax Rate (%):", className="form-label"), dcc.Input(id=ID_TAX_RATE, type="number", value=default_financial_params[KEY_TAX_RATE] * 100, min=0, max=100, className="form-control"), ], className="mb-2"),
                            html.Div([ html.Label("Inflation Rate (%):", className="form-label"), dcc.Input(id=ID_INFLATION_RATE, type="number", value=default_financial_params[KEY_INFLATION] * 100, min=-5, max=100, className="form-control"), ], className="mb-2"),
                            # Salvage value input kept for now, but calculation uses decommissioning costs primarily
                            html.Div([ html.Label("Salvage Value (% of initial BESS cost):", className="form-label"), dcc.Input(id=ID_SALVAGE, type="number", value=default_financial_params[KEY_SALVAGE] * 100, min=0, max=100, className="form-control"), html.P("Note: End-of-life value primarily driven by Decommissioning costs.", className="small text-muted")], className="mb-2"),
                        ]), # End Financial Card
                    ]), # End Right Column
                ]), # End Param Row
                html.Div(dbc.Button("Continue to Incentives", id=ID_CONTINUE_INCENTIVES_BTN, n_clicks=0, color="primary", className="mt-4 mb-3"), className="d-flex justify-content-center"),
            ])
        ]), # End Tab 2

        # Incentives Tab
        dbc.Tab(label="3. Battery Incentives", tab_id="tab-incentives", children=[
            dbc.Container(children=[
                 html.H3("Battery Incentive Programs", className="mb-4 text-center"),
                 html.P("Select applicable incentives. Ensure values are correct for your location/project.", className="text-muted mb-4 text-center"),
                 # Incentive layout structure remains the same, just using constants for IDs if defined
                 dbc.Row([
                     dbc.Col(md=6, children=[ # Federal
                         dbc.Card(className="p-3 mb-4", children=[
                             html.H4("Federal Incentives", className="mb-3"),
                             html.Div([ dbc.Checklist(id=ID_ITC_ENABLED, options=[{"label": " Investment Tax Credit (ITC)", "value": "enabled"}], value=["enabled"] if default_incentive_params["itc_enabled"] else [], className="form-check mb-1"), html.Div([ dbc.Label("ITC Percentage (%):", html_for=ID_ITC_PERCENT, size="sm"), dcc.Input(id=ID_ITC_PERCENT, type="number", value=default_incentive_params["itc_percentage"], min=0, max=100, className="form-control form-control-sm"), ], className="mb-2 ms-4"), html.P("Tax credit on capital expenditure.", className="text-muted small ms-4"), ], className="mb-3"),
                             # ... (rest of incentive inputs, using constants where defined) ...
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
                     dbc.Button("Calculate Results", id=ID_CALC_BTN, n_clicks=0, color="primary", className="mt-4 mb-3 me-3"),
                     dbc.Button("Optimize Battery Size", id=ID_OPTIMIZE_BTN, n_clicks=0, color="success", className="mt-4 mb-3"),
                 ], className="d-flex justify-content-center"),
            ])
        ]), # End Tab 3

        # Results Tab
        dbc.Tab(label="4. Results & Analysis", tab_id="tab-results", children=[
            dbc.Container(children=[
                dcc.Loading(id="loading-results", type="circle", children=[html.Div(id=ID_RESULTS_OUTPUT, className="mt-4")])
            ])
        ]), # End Tab 4

        # Optimization Tab
        dbc.Tab(label="5. Battery Sizing Tool", tab_id="tab-optimization", children=[
             dbc.Container(children=[
                dcc.Loading(id="loading-optimization", type="circle", children=[html.Div(id=ID_OPTIMIZE_OUTPUT, className="mt-4")])
             ])
        ]), # End Tab 5
    ]), # End Tabs
]) # End Main Container

# --- Callbacks ---

# Tab Navigation
@app.callback(
    Output(ID_MAIN_TABS, "active_tab"),
    [Input(ID_CONTINUE_PARAMS_BTN, "n_clicks"), Input(ID_CONTINUE_INCENTIVES_BTN, "n_clicks")],
    prevent_initial_call=True,
)
def navigate_tabs(n_params, n_incentives):
    ctx = callback_context
    if not ctx.triggered_id: return dash.no_update
    if ctx.triggered_id == ID_CONTINUE_PARAMS_BTN: return "tab-params"
    elif ctx.triggered_id == ID_CONTINUE_INCENTIVES_BTN: return "tab-incentives"
    else: return dash.no_update

# EAF Store Update
@app.callback(
    Output(STORE_EAF, "data"),
    [Input(ID_EAF_SIZE, "value"), Input(ID_EAF_COUNT, "value"), Input(ID_GRID_CAP, "value"), Input(ID_CYCLES_PER_DAY, "value"), Input(ID_CYCLE_DURATION, "value"), Input(ID_DAYS_PER_YEAR, "value"), Input(ID_MILL_DROPDOWN, "value")],
    State(STORE_EAF, "data")
)
def update_eaf_params_store(size, count, grid_cap, cycles, duration, days, selected_mill, existing_data):
    ctx = callback_context; triggered_id = ctx.triggered_id if ctx.triggered_id else 'unknown'
    output_data = existing_data.copy() if existing_data and isinstance(existing_data, dict) else nucor_mills["Custom"].copy()
    # Ensure cycle_duration_input exists for tracking user edits vs. mill defaults
    if KEY_CYCLE_DURATION_INPUT not in output_data:
        output_data[KEY_CYCLE_DURATION_INPUT] = output_data.get(KEY_CYCLE_DURATION, 0)

    if triggered_id == ID_MILL_DROPDOWN:
        # Load data from selected mill
        output_data = nucor_mills.get(selected_mill, nucor_mills["Custom"]).copy()
        # Set input tracker to match the loaded default
        output_data[KEY_CYCLE_DURATION_INPUT] = output_data.get(KEY_CYCLE_DURATION, 0)
    else:
        # Update individual fields based on user input
        if size is not None: output_data[KEY_EAF_SIZE] = size
        if count is not None: output_data["eaf_count"] = count # Assuming key is "eaf_count"
        if grid_cap is not None: output_data[KEY_GRID_CAP] = grid_cap
        if cycles is not None: output_data[KEY_CYCLES_PER_DAY] = cycles
        if duration is not None:
            # Update both the base duration (used in calcs if input is invalid) and the input tracker
            output_data[KEY_CYCLE_DURATION] = duration
            output_data[KEY_CYCLE_DURATION_INPUT] = duration
        if days is not None: output_data[KEY_DAYS_PER_YEAR] = days

    # Ensure cycle duration used in calculations is valid
    base_duration = output_data.get(KEY_CYCLE_DURATION, 0)
    input_duration = output_data.get(KEY_CYCLE_DURATION_INPUT, 0)
    try: base_duration = float(base_duration) if base_duration is not None else 0.0
    except (ValueError, TypeError): base_duration = 0.0
    try: input_duration = float(input_duration) if input_duration is not None else 0.0
    except (ValueError, TypeError): input_duration = 0.0

    base_duration = max(0.0, base_duration)
    input_duration = max(0.0, input_duration)

    # Logic to decide which duration to use: prioritize valid user input
    if input_duration > 0:
        output_data[KEY_CYCLE_DURATION] = input_duration # Use user input for calcs
    elif base_duration > 0:
         output_data[KEY_CYCLE_DURATION] = base_duration # Use mill default if input invalid
         output_data[KEY_CYCLE_DURATION_INPUT] = base_duration # Reset input display
    else:
         output_data[KEY_CYCLE_DURATION] = 36 # Fallback if both are invalid
         output_data[KEY_CYCLE_DURATION_INPUT] = 36

    return output_data

# Financial Store Update
@app.callback(
    Output(STORE_FINANCIAL, "data"),
    [Input(ID_WACC, "value"), Input(ID_LIFESPAN, "value"), Input(ID_TAX_RATE, "value"), Input(ID_INFLATION_RATE, "value"), Input(ID_SALVAGE, "value")],
)
def update_financial_params_store(wacc, lifespan, tax, inflation, salvage):
    # Convert percentages from UI to decimals for calculations
    return {
        KEY_WACC: wacc / 100.0 if wacc is not None else default_financial_params[KEY_WACC],
        KEY_LIFESPAN: lifespan,
        KEY_TAX_RATE: tax / 100.0 if tax is not None else default_financial_params[KEY_TAX_RATE],
        KEY_INFLATION: inflation / 100.0 if inflation is not None else default_financial_params[KEY_INFLATION],
        KEY_SALVAGE: salvage / 100.0 if salvage is not None else default_financial_params[KEY_SALVAGE],
    }

# Incentive Store Update
@app.callback(
    Output(STORE_INCENTIVE, "data"),
    [Input(ID_ITC_ENABLED, "value"), Input(ID_ITC_PERCENT, "value"), Input("ceic-enabled", "value"), Input("ceic-percentage", "value"), Input("bonus-credit-enabled", "value"), Input("bonus-credit-percentage", "value"), Input("sgip-enabled", "value"), Input("sgip-amount", "value"), Input("ess-enabled", "value"), Input("ess-amount", "value"), Input("mabi-enabled", "value"), Input("mabi-amount", "value"), Input("cs-enabled", "value"), Input("cs-amount", "value"), Input("custom-incentive-enabled", "value"), Input("custom-incentive-type", "value"), Input("custom-incentive-amount", "value"), Input("custom-incentive-description", "value")],
)
def update_incentive_params_store(itc_en, itc_pct, ceic_en, ceic_pct, bonus_en, bonus_pct, sgip_en, sgip_amt, ess_en, ess_amt, mabi_en, mabi_amt, cs_en, cs_amt, custom_en, custom_type, custom_amt, custom_desc):
    # Read checklist values and corresponding amounts/percentages
    return {
        "itc_enabled": "enabled" in itc_en, "itc_percentage": itc_pct,
        "ceic_enabled": "enabled" in ceic_en, "ceic_percentage": ceic_pct,
        "bonus_credit_enabled": "enabled" in bonus_en, "bonus_credit_percentage": bonus_pct,
        "sgip_enabled": "enabled" in sgip_en, "sgip_amount": sgip_amt,
        "ess_enabled": "enabled" in ess_en, "ess_amount": ess_amt,
        "mabi_enabled": "enabled" in mabi_en, "mabi_amount": mabi_amt,
        "cs_enabled": "enabled" in cs_en, "cs_amount": cs_amt,
        "custom_incentive_enabled": "enabled" in custom_en,
        "custom_incentive_type": custom_type, "custom_incentive_amount": custom_amt, "custom_incentive_description": custom_desc,
    }

# Utility Store Update (REVISED TO HANDLE TOGGLE STATE)
@app.callback(
    Output(STORE_UTILITY, "data"),
    [Input(ID_UTILITY_DROPDOWN, "value"),
     Input(ID_OFF_PEAK, "value"),
     Input(ID_MID_PEAK, "value"),
     Input(ID_PEAK, "value"),
     Input(ID_DEMAND_CHARGE, "value"),
     Input(ID_SEASONAL_TOGGLE, "value"), # Input for toggle status
     Input("winter-multiplier", "value"), # Keep as Input
     Input("summer-multiplier", "value"), # Keep as Input
     Input("shoulder-multiplier", "value"),# Keep as Input
     Input("winter-months", "value"),     # Keep as Input
     Input("summer-months", "value"),     # Keep as Input
     Input("shoulder-months", "value"),   # Keep as Input
     Input({"type": "tou-start", "index": ALL}, "value"),
     Input({"type": "tou-end", "index": ALL}, "value"),
     Input({"type": "tou-rate", "index": ALL}, "value")],
    State(STORE_UTILITY, "data"),
)
def update_utility_params_store(
    utility_provider, off_peak_rate, mid_peak_rate, peak_rate, demand_charge,
    seasonal_toggle_value, # Get the toggle value from its Input
    winter_mult, summer_mult, shoulder_mult, # Values from inputs
    winter_months_str, summer_months_str, shoulder_months_str, # Values from inputs
    tou_starts, tou_ends, tou_rates,
    existing_data
):
    """
    Updates the utility parameter store.
    Checks the seasonal toggle state before applying seasonal input values.
    """
    ctx = callback_context; triggered_id = ctx.triggered_id
    params = {}
    # Use pprint for cleaner dictionary printing in logs
    import pprint

    # Determine base parameters (from dropdown selection or existing state)
    if isinstance(triggered_id, str) and triggered_id == ID_UTILITY_DROPDOWN:
        print(f"DEBUG Utility Store: Triggered by Dropdown ({utility_provider})")
        params = utility_rates.get(utility_provider, default_utility_params).copy()
        # Ensure raw TOU periods are copied from the source 'tou_periods' key if it exists
        params[KEY_TOU_RAW] = params.get("tou_periods", default_utility_params[KEY_TOU_RAW])
    elif existing_data:
        # print(f"DEBUG Utility Store: Triggered by other input ({triggered_id}). Using existing data.")
        params = existing_data.copy()
    else:
        print("DEBUG Utility Store: No existing data. Using default params.")
        params = default_utility_params.copy()

    # Update basic rates and charges (always happens)
    params[KEY_ENERGY_RATES] = {"off_peak": off_peak_rate, "mid_peak": mid_peak_rate, "peak": peak_rate}
    params[KEY_DEMAND_CHARGE] = demand_charge

    # --- Revised Seasonal Logic ---
    # Determine if seasonal is conceptually enabled based on toggle INPUT value
    is_seasonal_enabled = seasonal_toggle_value and "enabled" in seasonal_toggle_value
    params[KEY_SEASONAL] = is_seasonal_enabled # Store the boolean flag

    def parse_months(month_str, default_list):
        if not isinstance(month_str, str): return default_list
        try:
            parsed = [int(m.strip()) for m in month_str.split(",") if m.strip() and 1 <= int(m.strip()) <= 12]
            return parsed if parsed else default_list
        except ValueError:
            print(f"Warning: Could not parse month string '{month_str}'. Using default.")
            return default_list

    # Update seasonal details ONLY IF the toggle is enabled
    if is_seasonal_enabled:
        print("DEBUG Utility Store: Seasonal Toggle is ON. Updating seasonal params from inputs.")
        params[KEY_WINTER_MONTHS] = parse_months(winter_months_str, default_utility_params[KEY_WINTER_MONTHS])
        params[KEY_SUMMER_MONTHS] = parse_months(summer_months_str, default_utility_params[KEY_SUMMER_MONTHS])
        params[KEY_SHOULDER_MONTHS] = parse_months(shoulder_months_str, default_utility_params[KEY_SHOULDER_MONTHS])
        params[KEY_WINTER_MULT] = winter_mult if winter_mult is not None else default_utility_params[KEY_WINTER_MULT]
        params[KEY_SUMMER_MULT] = summer_mult if summer_mult is not None else default_utility_params[KEY_SUMMER_MULT]
        params[KEY_SHOULDER_MULT] = shoulder_mult if shoulder_mult is not None else default_utility_params[KEY_SHOULDER_MULT]
        # TODO: Add validation here to ensure all 12 months are covered and unique
    else:
        print("DEBUG Utility Store: Seasonal Toggle is OFF. Using default/existing seasonal params (resetting to defaults).")
        # Reset to defaults when toggle is off to avoid confusion
        params[KEY_WINTER_MONTHS] = default_utility_params[KEY_WINTER_MONTHS]
        params[KEY_SUMMER_MONTHS] = default_utility_params[KEY_SUMMER_MONTHS]
        params[KEY_SHOULDER_MONTHS] = default_utility_params[KEY_SHOULDER_MONTHS]
        params[KEY_WINTER_MULT] = default_utility_params[KEY_WINTER_MULT]
        params[KEY_SUMMER_MULT] = default_utility_params[KEY_SUMMER_MULT]
        params[KEY_SHOULDER_MULT] = default_utility_params[KEY_SHOULDER_MULT]

    # --- TOU Logic (remains the same) ---
    # Update TOU periods based on UI inputs unless triggered by provider dropdown
    if isinstance(triggered_id, str) and triggered_id == ID_UTILITY_DROPDOWN:
        # Use the raw periods already set from the selected utility data
        raw_tou_periods = params.get(KEY_TOU_RAW, default_utility_params[KEY_TOU_RAW])
    else:
        # Reconstruct raw periods from the dynamic UI inputs
        raw_tou_periods = []
        for i in range(len(tou_starts)):
            start_val, end_val, rate_val = tou_starts[i], tou_ends[i], tou_rates[i]
            # Basic validation for completeness and numeric types
            if start_val is not None and end_val is not None and rate_val is not None:
                try:
                    start_f, end_f = float(start_val), float(end_val)
                    # Basic range check
                    if 0 <= start_f < end_f <= 24:
                        raw_tou_periods.append((start_f, end_f, str(rate_val)))
                    else: print(f"Warning: Invalid TOU range {start_f}-{end_f} ignored.")
                except (ValueError, TypeError): print(f"Warning: Invalid TOU numeric values ({start_val}, {end_val}) ignored.")
            elif rate_val is not None: print(f"Warning: Incomplete TOU period at index {i} ignored.")
        params[KEY_TOU_RAW] = raw_tou_periods
        # TODO: Add validation here to ensure 24h coverage without overlaps

    # Always fill gaps for calculation purposes
    params[KEY_TOU_FILLED] = fill_tou_gaps(params.get(KEY_TOU_RAW, []))

    print("DEBUG: Updated Utility Store:")
    pprint.pprint(params)
    return params

# Mill Info Card Update
@app.callback(Output(ID_MILL_INFO_CARD, "children"), Input(ID_MILL_DROPDOWN, "value"))
def update_mill_info(selected_mill):
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]; selected_mill = "Custom"; card_header_class = "card-header bg-secondary text-white"
    else:
        mill_data = nucor_mills[selected_mill]; card_header_class = "card-header bg-primary text-white"
    # Display key mill information
    info_card = dbc.Card([
        dbc.CardHeader(f"Selected: Nucor Steel {selected_mill}", className=card_header_class),
        dbc.CardBody([
            html.Div([html.Strong("Location: "), html.Span(mill_data.get("location", "N/A"))], className="mb-1"),
            html.Div([html.Strong("Mill Type: "), html.Span(mill_data.get("type", "N/A"))], className="mb-1"),
            html.Div([html.Strong("EAF Config: "), html.Span(f"{mill_data.get('eaf_count', 'N/A')} x {mill_data.get(KEY_EAF_SIZE, 'N/A')} ton {mill_data.get('eaf_type', 'N/A')} ({mill_data.get('eaf_manufacturer', 'N/A')})")], className="mb-1"),
            html.Div([html.Strong("Production: "), html.Span(f"{mill_data.get('tons_per_year', 0):,} tons/year")], className="mb-1"),
            html.Div([html.Strong("Schedule: "), html.Span(f"{mill_data.get(KEY_CYCLES_PER_DAY, 'N/A')} cycles/day, {mill_data.get(KEY_DAYS_PER_YEAR, 'N/A')} days/year, {mill_data.get(KEY_CYCLE_DURATION, 'N/A')} min/cycle")], className="mb-1"),
            html.Div([html.Strong("Utility: "), html.Span(mill_data.get("utility", "N/A"))], className="mb-1"),
            html.Div([html.Strong("Grid Cap (Est): "), html.Span(f"{mill_data.get(KEY_GRID_CAP, 'N/A')} MW")], className="mb-1"),
        ])
    ])
    return info_card

# Update Params from Mill Selection
@app.callback(
    [Output(ID_UTILITY_DROPDOWN, "value"), Output(ID_OFF_PEAK, "value"), Output(ID_MID_PEAK, "value"), Output(ID_PEAK, "value"), Output(ID_DEMAND_CHARGE, "value"), Output(ID_SEASONAL_TOGGLE, "value"), Output(ID_EAF_SIZE, "value"), Output(ID_EAF_COUNT, "value"), Output(ID_GRID_CAP, "value"), Output(ID_CYCLES_PER_DAY, "value"), Output(ID_CYCLE_DURATION, "value"), Output(ID_DAYS_PER_YEAR, "value"), Output(ID_TOU_CONTAINER, "children", allow_duplicate=True)],
    Input(ID_MILL_DROPDOWN, "value"),
    prevent_initial_call=True,
)
def update_params_from_mill(selected_mill):
    # Load mill data and corresponding utility data
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]; utility_provider = "Custom Utility"
        utility_data = utility_rates.get(utility_provider, default_utility_params)
    else:
        mill_data = nucor_mills[selected_mill]; utility_provider = mill_data.get("utility", "Custom Utility")
        if utility_provider not in utility_rates:
            utility_data = utility_rates["Custom Utility"]; utility_provider = "Custom Utility"
        else: utility_data = utility_rates[utility_provider]

    # Extract values, using defaults as fallbacks
    off_peak = utility_data.get(KEY_ENERGY_RATES, {}).get("off_peak", default_utility_params[KEY_ENERGY_RATES]["off_peak"])
    mid_peak = utility_data.get(KEY_ENERGY_RATES, {}).get("mid_peak", default_utility_params[KEY_ENERGY_RATES]["mid_peak"])
    peak = utility_data.get(KEY_ENERGY_RATES, {}).get("peak", default_utility_params[KEY_ENERGY_RATES]["peak"])
    demand = utility_data.get(KEY_DEMAND_CHARGE, default_utility_params[KEY_DEMAND_CHARGE])
    seasonal_enabled = ["enabled"] if utility_data.get(KEY_SEASONAL, default_utility_params[KEY_SEASONAL]) else []
    eaf_size = mill_data.get(KEY_EAF_SIZE, nucor_mills["Custom"][KEY_EAF_SIZE])
    eaf_count = mill_data.get("eaf_count", nucor_mills["Custom"]["eaf_count"])
    grid_cap = mill_data.get(KEY_GRID_CAP, nucor_mills["Custom"][KEY_GRID_CAP])
    cycles = mill_data.get(KEY_CYCLES_PER_DAY, nucor_mills["Custom"][KEY_CYCLES_PER_DAY])
    duration = mill_data.get(KEY_CYCLE_DURATION, nucor_mills["Custom"][KEY_CYCLE_DURATION])
    days = mill_data.get(KEY_DAYS_PER_YEAR, nucor_mills["Custom"][KEY_DAYS_PER_YEAR])

    # Generate TOU UI elements based on the selected utility's raw periods
    tou_periods_for_ui = utility_data.get("tou_periods", default_utility_params[KEY_TOU_RAW])
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)

    return [utility_provider, off_peak, mid_peak, peak, demand, seasonal_enabled, eaf_size, eaf_count, grid_cap, cycles, duration, days, tou_elements_ui]

# Update Rates from Provider Dropdown (Manual Override)
@app.callback(
    [Output(ID_OFF_PEAK, "value", allow_duplicate=True), Output(ID_MID_PEAK, "value", allow_duplicate=True), Output(ID_PEAK, "value", allow_duplicate=True), Output(ID_DEMAND_CHARGE, "value", allow_duplicate=True), Output(ID_SEASONAL_TOGGLE, "value", allow_duplicate=True), Output(ID_TOU_CONTAINER, "children", allow_duplicate=True)],
    Input(ID_UTILITY_DROPDOWN, "value"),
    # State(ID_MILL_DROPDOWN, "value"), # Mill selection state not strictly needed here
    prevent_initial_call=True,
)
def update_rates_from_provider_manual(selected_utility): # Removed selected_mill state
    ctx = callback_context
    # Ensure this callback only runs when the utility dropdown triggers it
    if not ctx.triggered_id or ctx.triggered_id != ID_UTILITY_DROPDOWN:
        return dash.no_update

    utility_data = utility_rates.get(selected_utility, utility_rates["Custom Utility"])
    off_peak = utility_data.get(KEY_ENERGY_RATES, {}).get("off_peak", default_utility_params[KEY_ENERGY_RATES]["off_peak"])
    mid_peak = utility_data.get(KEY_ENERGY_RATES, {}).get("mid_peak", default_utility_params[KEY_ENERGY_RATES]["mid_peak"])
    peak = utility_data.get(KEY_ENERGY_RATES, {}).get("peak", default_utility_params[KEY_ENERGY_RATES]["peak"])
    demand = utility_data.get(KEY_DEMAND_CHARGE, default_utility_params[KEY_DEMAND_CHARGE])
    seasonal_enabled = ["enabled"] if utility_data.get(KEY_SEASONAL, default_utility_params[KEY_SEASONAL]) else []
    # Use 'tou_periods' key which holds the raw definition for the UI
    tou_periods_for_ui = utility_data.get("tou_periods", default_utility_params[KEY_TOU_RAW])
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)

    return off_peak, mid_peak, peak, demand, seasonal_enabled, tou_elements_ui

# Seasonal Rates UI Toggle (REVISED TO ALWAYS RENDER INPUTS)
@app.callback(
    [Output(ID_SEASONAL_CONTAINER, "children"), Output(ID_SEASONAL_CONTAINER, "style")],
    [Input(ID_SEASONAL_TOGGLE, "value"), Input(ID_UTILITY_DROPDOWN, "value")],
    # No State needed here for this fix, defaults loaded from dropdown trigger
)
def update_seasonal_rates_ui(toggle_value, selected_utility):
    """
    Updates the seasonal rates UI.
    ALWAYS renders the input elements within the children.
    Controls the visibility of the container div (ID_SEASONAL_CONTAINER) via style.
    """
    is_enabled = toggle_value and "enabled" in toggle_value
    # Set the display style for the CONTAINER based on the toggle
    display_style = {"display": "block", "border": "1px solid #ccc", "padding": "10px", "border-radius": "5px", "background-color": "#f9f9f9"} if is_enabled else {"display": "none"}

    # Get defaults from the selected utility provider to populate values
    utility_data_source = utility_rates.get(selected_utility, default_utility_params)

    winter_mult = utility_data_source.get(KEY_WINTER_MULT, default_utility_params[KEY_WINTER_MULT])
    summer_mult = utility_data_source.get(KEY_SUMMER_MULT, default_utility_params[KEY_SUMMER_MULT])
    shoulder_mult = utility_data_source.get(KEY_SHOULDER_MULT, default_utility_params[KEY_SHOULDER_MULT])
    winter_m = ",".join(map(str, utility_data_source.get(KEY_WINTER_MONTHS, default_utility_params[KEY_WINTER_MONTHS])))
    summer_m = ",".join(map(str, utility_data_source.get(KEY_SUMMER_MONTHS, default_utility_params[KEY_SUMMER_MONTHS])))
    shoulder_m = ",".join(map(str, utility_data_source.get(KEY_SHOULDER_MONTHS, default_utility_params[KEY_SHOULDER_MONTHS])))

    # Define the UI elements for seasonal inputs - ALWAYS create them
    seasonal_ui = html.Div([
        # Make sure IDs match exactly what update_utility_params_store expects
        dbc.Row([
            dbc.Col([dbc.Label("Winter Multiplier:", size="sm"), dcc.Input(id="winter-multiplier", type="number", value=winter_mult, min=0, step=0.01, className="form-control form-control-sm")], md=4, className="mb-2"),
            dbc.Col([dbc.Label("Summer Multiplier:", size="sm"), dcc.Input(id="summer-multiplier", type="number", value=summer_mult, min=0, step=0.01, className="form-control form-control-sm")], md=4, className="mb-2"),
            dbc.Col([dbc.Label("Shoulder Multiplier:", size="sm"), dcc.Input(id="shoulder-multiplier", type="number", value=shoulder_mult, min=0, step=0.01, className="form-control form-control-sm")], md=4, className="mb-2"),
        ], className="row mb-2"),
        dbc.Row([
            dbc.Col([dbc.Label("Winter Months (1-12):", size="sm"), dcc.Input(id="winter-months", type="text", value=winter_m, placeholder="e.g., 11,12,1,2", className="form-control form-control-sm")], md=4, className="mb-2"),
            dbc.Col([dbc.Label("Summer Months (1-12):", size="sm"), dcc.Input(id="summer-months", type="text", value=summer_m, placeholder="e.g., 6,7,8,9", className="form-control form-control-sm")], md=4, className="mb-2"),
            dbc.Col([dbc.Label("Shoulder Months (1-12):", size="sm"), dcc.Input(id="shoulder-months", type="text", value=shoulder_m, placeholder="e.g., 3,4,5,10", className="form-control form-control-sm")], md=4, className="mb-2"),
        ], className="row"),
        html.P("Use comma-separated month numbers (1-12). Ensure all 12 months are assigned.", className="small text-muted mt-1"),
    ])

    # Return the UI elements AND the style to show/hide the container
    # The inputs now always exist in the layout's children structure.
    return seasonal_ui, display_style

# TOU UI Management Helper
def generate_tou_ui_elements(tou_periods_list):
    """Generates UI rows for TOU period inputs."""
    tou_elements = []
    if not tou_periods_list: # Provide a default row if list is empty
        tou_periods_list = [(0.0, 24.0, "off_peak")]

    for i, period_data in enumerate(tou_periods_list):
        # Safely unpack period data
        if isinstance(period_data, (list, tuple)) and len(period_data) == 3:
            start, end, rate_type = period_data
        else:
            print(f"Warning: Invalid format for TOU period data at index {i}: {period_data}. Using default.")
            start, end, rate_type = (0.0, 0.0, "off_peak") # Fallback

        # Create the row structure
        tou_row = html.Div([
            html.Div([
                html.Div(dcc.Input(id={"type": "tou-start", "index": i}, type="number", min=0, max=24, step=0.1, value=start, className="form-control form-control-sm", placeholder="Start Hr (0-24)"), className="col-3"),
                html.Div(dcc.Input(id={"type": "tou-end", "index": i}, type="number", min=0, max=24, step=0.1, value=end, className="form-control form-control-sm", placeholder="End Hr (0-24)"), className="col-3"),
                html.Div(dcc.Dropdown(id={"type": "tou-rate", "index": i}, options=[{"label": "Off-Peak", "value": "off_peak"}, {"label": "Mid-Peak", "value": "mid_peak"}, {"label": "Peak", "value": "peak"}], value=rate_type, clearable=False, className="form-select form-select-sm"), className="col-4"),
                html.Div(dbc.Button("×", id={"type": "remove-tou", "index": i}, color="danger", size="sm", title="Remove Period", style={"lineHeight": "1"}, disabled=len(tou_periods_list) <= 1), className="col-2 d-flex align-items-center justify-content-center"), # Disable remove for last row
            ], className="row g-1 mb-1 align-items-center"),
        ], id=f"tou-row-{i}", className="tou-period-row")
        tou_elements.append(tou_row)
    return tou_elements

# TOU UI Add/Remove Callback
@app.callback(
    Output(ID_TOU_CONTAINER, "children", allow_duplicate=True),
    [Input(ID_ADD_TOU_BTN, "n_clicks"), Input({"type": "remove-tou", "index": ALL}, "n_clicks")],
    State(ID_TOU_CONTAINER, "children"),
    prevent_initial_call=True,
)
def modify_tou_rows(add_clicks, remove_clicks_list, current_rows):
    ctx = callback_context; triggered_input = ctx.triggered_id
    if not triggered_input: return dash.no_update

    new_rows = current_rows[:] if current_rows else []

    if triggered_input == ID_ADD_TOU_BTN:
        # Add a new default row
        new_index = len(new_rows)
        # Determine start time for new row (end time of previous row, or 0)
        default_start = 0.0
        if new_rows:
            try:
                last_row_end_input = current_rows[-1]['props']['children'][0]['props']['children'][1]['props']['children'] # Navigate to end input
                default_start = last_row_end_input['props'].get('value', 0.0)
            except (KeyError, IndexError, TypeError):
                pass # Keep default_start as 0.0 if structure is unexpected

        new_row_elements = generate_tou_ui_elements([(default_start, default_start, "off_peak")]) # Start=End initially
        new_row_div = new_row_elements[0]; new_row_div.id = f"tou-row-{new_index}"
        # Update the index in the pattern-matching IDs
        for col in new_row_div.children[0].children:
            if hasattr(col.children, "id") and isinstance(col.children.id, dict):
                col.children.id["index"] = new_index
        new_rows.append(new_row_div)

    elif isinstance(triggered_input, dict) and triggered_input.get("type") == "remove-tou":
        # Remove the clicked row, but only if more than one row exists
        if len(new_rows) > 1:
            clicked_index = triggered_input["index"]; row_to_remove_id = f"tou-row-{clicked_index}"
            new_rows = [row for row in new_rows if row.get("props", {}).get("id") != row_to_remove_id]
        else:
            print("Cannot remove the last TOU period row.")

    # Update the disabled state of all remove buttons
    num_rows = len(new_rows)
    for i, row in enumerate(new_rows):
        try:
            # Find the button within the row structure
            button_col = row['props']['children'][0]['props']['children'][-1]
            button = button_col['props']['children']
            button['props']['disabled'] = (num_rows <= 1) # Disable if only one row left
        except (AttributeError, IndexError, KeyError, TypeError):
            print(f"Warning: Could not find or update remove button state for row {i}")

    return new_rows


# Input Validation
@app.callback(
    [Output(ID_VALIDATION_ERR, "children"), Output(ID_VALIDATION_ERR, "is_open"), Output(ID_CALCULATION_ERR, "is_open", allow_duplicate=True)],
    [Input(ID_CALC_BTN, "n_clicks"), Input(ID_OPTIMIZE_BTN, "n_clicks"), Input(STORE_UTILITY, "data"), Input(STORE_EAF, "data"), Input(STORE_BESS, "data"), Input(STORE_FINANCIAL, "data")],
    prevent_initial_call=True,
)
def validate_inputs(calc_clicks, opt_clicks, utility_params, eaf_params, bess_params, fin_params):
    ctx = dash.callback_context; triggered_id = ctx.triggered_id if ctx.triggered_id else 'initial_load_or_unknown'
    # Only perform validation if a calculation or optimization was attempted
    is_calc_attempt = triggered_id in [ID_CALC_BTN, ID_OPTIMIZE_BTN]
    if not is_calc_attempt:
        return "", False, False # No errors to show if not calculating

    errors = []; warnings = []

    # Utility Validation
    if not utility_params: errors.append("Utility parameters are missing.")
    else:
        rates = utility_params.get(KEY_ENERGY_RATES, {})
        if rates.get("off_peak", -1) < 0: errors.append("Off-Peak Rate cannot be negative.")
        if rates.get("mid_peak", -1) < 0: errors.append("Mid-Peak Rate cannot be negative.")
        if rates.get("peak", -1) < 0: errors.append("Peak Rate cannot be negative.")
        if utility_params.get(KEY_DEMAND_CHARGE, -1) < 0: errors.append("Demand Charge cannot be negative.")
        # TODO: Add more detailed TOU/Seasonal validation if desired

    # EAF Validation
    if not eaf_params: errors.append("EAF parameters are missing.")
    else:
        if eaf_params.get(KEY_EAF_SIZE, 0) <= 0: errors.append("EAF Size must be positive.")
        if eaf_params.get("eaf_count", 0) <= 0: errors.append("Number of EAFs must be positive.")
        if eaf_params.get(KEY_GRID_CAP, 0) <= 0: errors.append("Grid Power Limit must be positive.")
        if eaf_params.get(KEY_CYCLES_PER_DAY, 0) <= 0: errors.append("EAF Cycles per Day must be positive.")
        if eaf_params.get(KEY_CYCLE_DURATION_INPUT, 0) <= 0: errors.append("Avg. Cycle Duration must be positive.")
        if not (0 < eaf_params.get(KEY_DAYS_PER_YEAR, 0) <= 366): errors.append("Operating Days per Year must be between 1 and 366.")

    # BESS Validation
    if not bess_params: errors.append("BESS parameters are missing.")
    else:
        if bess_params.get(KEY_CAPACITY, 0) <= 0: errors.append("BESS Capacity (MWh) must be positive.")
        if bess_params.get(KEY_POWER_MAX, 0) <= 0: errors.append("BESS Power (MW) must be positive.")
        if bess_params.get(KEY_SB_BOS_COST, -1) < 0: errors.append("BESS SB+BOS Cost cannot be negative.")
        if bess_params.get(KEY_PCS_COST, -1) < 0: errors.append("BESS PCS Cost cannot be negative.")
        if bess_params.get(KEY_EPC_COST, -1) < 0: errors.append("BESS EPC Cost cannot be negative.")
        if bess_params.get(KEY_SYS_INT_COST, -1) < 0: errors.append("BESS System Integration Cost cannot be negative.")
        if bess_params.get(KEY_FIXED_OM, None) is not None and bess_params.get(KEY_FIXED_OM, -1) < 0: errors.append("BESS Fixed O&M Cost cannot be negative.")
        if bess_params.get(KEY_OM_KWHR_YR, None) is not None and bess_params.get(KEY_OM_KWHR_YR, -1) < 0: errors.append("BESS O&M Cost ($/kWh/yr) cannot be negative.")
        if not (0 < bess_params.get(KEY_RTE, 0) <= 100): errors.append("BESS RTE must be between 0% and 100%.")
        if bess_params.get(KEY_INSURANCE, -1) < 0: errors.append("BESS Insurance Rate cannot be negative.")
        # Decomm costs can be negative
        if bess_params.get(KEY_CYCLE_LIFE, 0) <= 0: errors.append("BESS Cycle Life must be positive.")
        if not (0 < bess_params.get(KEY_DOD, 0) <= 100): errors.append("BESS DoD must be between 0% and 100%.")
        if bess_params.get(KEY_CALENDAR_LIFE, 0) <= 0: errors.append("BESS Calendar Life must be positive.")

    # Financial Validation
    if not fin_params: errors.append("Financial parameters are missing.")
    else:
        if not (0 <= fin_params.get(KEY_WACC, -1) <= 1): errors.append("WACC must be between 0% and 100%.")
        if fin_params.get(KEY_LIFESPAN, 0) <= 0: errors.append("Project Lifespan must be positive.")
        if not (0 <= fin_params.get(KEY_TAX_RATE, -1) <= 1): errors.append("Tax Rate must be between 0% and 100%.")
        # Allow deflation, but maybe warn if too extreme?
        if fin_params.get(KEY_INFLATION, None) is None: errors.append("Inflation Rate is missing.")
        if not (0 <= fin_params.get(KEY_SALVAGE, -1) <= 1): errors.append("Salvage Value must be between 0% and 100%.")


    output_elements = []; is_open = False; calc_error_open = False
    if errors:
        output_elements.append(html.H5("Validation Errors:", className="text-danger"))
        output_elements.append(html.Ul([html.Li(e) for e in errors]))
        is_open = True
        calc_error_open = False # Hide calculation error if validation fails
    elif warnings: # Currently no warnings implemented here
        output_elements.append(html.H5("Validation Warnings:", className="text-warning"))
        output_elements.append(html.Ul([html.Li(w) for w in warnings]))
        is_open = True

    # Return validation messages and hide calculation error container if validation fails
    return output_elements, is_open, calc_error_open


# BESS C-Rate Display Update
@app.callback(
    Output(ID_BESS_C_RATE_DISPLAY, "children"),
    [Input(ID_BESS_CAPACITY, "value"), Input(ID_BESS_POWER, "value")]
)
def update_c_rate_display(capacity, power):
    """Calculates and displays the C-Rate based on capacity and power inputs."""
    if capacity is not None and power is not None and capacity > 0:
        try:
            c_rate = float(power) / float(capacity)
            return f"Calculated C-Rate: {c_rate:.2f} h⁻¹" # Using h⁻¹ as unit for C-rate
        except (ValueError, TypeError, ZeroDivisionError):
            return "Invalid capacity or power for C-Rate calculation."
    elif capacity == 0 and power is not None and power > 0:
         return "C-Rate: Infinite (Capacity is zero)"
    else:
        return "" # Return empty if inputs are missing or invalid


# BESS Inputs Update on Technology Dropdown Change (REVISED TO ALWAYS RENDER O&M INPUTS)
@app.callback(
    [
        Output(ID_BESS_EXAMPLE_PRODUCT, "children"),
        Output(ID_BESS_SB_BOS_COST, "value"),
        Output(ID_BESS_PCS_COST, "value"),
        Output(ID_BESS_EPC_COST, "value"),
        Output(ID_BESS_SYS_INT_COST, "value"),
        Output(ID_BESS_OPEX_CONTAINER, "children"), # Output remains the same container
        Output(ID_BESS_RTE, "value"),
        Output(ID_BESS_INSURANCE, "value"),
        Output(ID_BESS_DISCONNECT_COST, "value"),
        Output(ID_BESS_RECYCLING_COST, "value"),
        Output(ID_BESS_CYCLE_LIFE, "value"),
        Output(ID_BESS_DOD, "value"),
        Output(ID_BESS_CALENDAR_LIFE, "value"),
    ],
    Input(ID_BESS_TECH_DROPDOWN, "value"),
    prevent_initial_call=True
)
def update_bess_inputs_from_technology(selected_technology):
    """
    Updates the detailed BESS parameter inputs when the technology dropdown changes.
    ALWAYS renders both O&M input groups within the container, hiding the irrelevant one via style.
    """
    if not selected_technology or selected_technology not in bess_technology_data:
        print(f"DEBUG: Invalid or no technology selected ('{selected_technology}'), defaulting to LFP")
        selected_technology = "LFP" # Default to LFP if selection is invalid

    print(f"DEBUG: Loading UI defaults for technology: {selected_technology}")
    tech_data = bess_technology_data[selected_technology]

    # Determine which O&M input to show
    show_om_kwhyr = KEY_OM_KWHR_YR in tech_data
    style_fixed_om = {'display': 'none'} if show_om_kwhyr else {'display': 'flex'} # Use flex for Row display
    style_om_kwhyr = {'display': 'flex'} if show_om_kwhyr else {'display': 'none'} # Use flex for Row display

    # Create BOTH O&M input groups using the helper, applying the style
    fixed_om_input_group = create_bess_input_group(
        "Fixed O&M:", ID_BESS_FIXED_OM, tech_data.get(KEY_FIXED_OM, 0), "$/kW/yr",
        tooltip_text="Annual Fixed Operation & Maintenance cost per kW of power capacity (common for Li-ion, Flow).",
        style=style_fixed_om # Apply style to hide/show
    )
    om_kwhyr_input_group = create_bess_input_group(
        "O&M Cost:", ID_BESS_OM_KWHR_YR, tech_data.get(KEY_OM_KWHR_YR, 0), "$/kWh/yr",
        tooltip_text="Annual Operation & Maintenance cost per kWh of energy capacity (e.g., for Supercapacitors).",
        style=style_om_kwhyr # Apply style to hide/show
    )

    # The children of the container will be a list containing both input groups
    opex_container_children = [fixed_om_input_group, om_kwhyr_input_group]

    # Return the default values for the selected technology, including the container children
    return (
        tech_data.get(KEY_EXAMPLE_PRODUCT, "N/A"),
        tech_data.get(KEY_SB_BOS_COST, 0),
        tech_data.get(KEY_PCS_COST, 0),
        tech_data.get(KEY_EPC_COST, 0),
        tech_data.get(KEY_SYS_INT_COST, 0),
        opex_container_children, # Pass the list containing both styled groups
        tech_data.get(KEY_RTE, 0),
        tech_data.get(KEY_INSURANCE, 0),
        tech_data.get(KEY_DISCONNECT_COST, 0),
        tech_data.get(KEY_RECYCLING_COST, 0),
        tech_data.get(KEY_CYCLE_LIFE, 0),
        tech_data.get(KEY_DOD, 0),
        tech_data.get(KEY_CALENDAR_LIFE, 0),
    )

# BESS Store Update (REVISED LOGIC V5 - Trigger on All Inputs, Careful Handling)
@app.callback(
    Output(STORE_BESS, "data"),
    [
        # --- INPUTS ---
        # ALL relevant BESS inputs are now triggers
        Input(ID_BESS_CAPACITY, "value"),
        Input(ID_BESS_POWER, "value"),
        Input(ID_BESS_TECH_DROPDOWN, "value"),
        Input(ID_BESS_SB_BOS_COST, "value"),
        Input(ID_BESS_PCS_COST, "value"),
        Input(ID_BESS_EPC_COST, "value"),
        Input(ID_BESS_SYS_INT_COST, "value"),
        # Add BOTH potential O&M inputs as triggers
        Input(ID_BESS_FIXED_OM, "value"),
        Input(ID_BESS_OM_KWHR_YR, "value"),
        Input(ID_BESS_RTE, "value"),
        Input(ID_BESS_INSURANCE, "value"),
        Input(ID_BESS_DISCONNECT_COST, "value"),
        Input(ID_BESS_RECYCLING_COST, "value"),
        Input(ID_BESS_CYCLE_LIFE, "value"),
        Input(ID_BESS_DOD, "value"),
        Input(ID_BESS_CALENDAR_LIFE, "value"),
    ],
    [
        # --- STATE ---
        # Get previous store data to use as a base for non-dropdown changes
        State(STORE_BESS, "data")
    ],
    prevent_initial_call=True
)
def update_bess_params_store(
    # Input values (order must match Input list above)
    capacity, power, technology,
    sb_bos_cost, pcs_cost, epc_cost, sys_int_cost,
    fixed_om, om_kwhyr, # Read both O&M inputs
    rte, insurance, disconnect_cost, recycling_cost,
    cycle_life, dod, calendar_life,
    # State value
    previous_bess_data
):
    """
    Updates the BESS parameter store based on ANY BESS input change.
    V5: Handles dropdown trigger by reloading defaults.
        Handles other triggers by updating the specific field in the previous state.
    """
    ctx = dash.callback_context
    if not ctx.triggered_id or not ctx.triggered:
        print("DEBUG update_bess_params_store (V5): No trigger ID, returning no_update")
        return dash.no_update

    # Use pprint for cleaner dictionary printing in logs
    import pprint

    # Determine the ID and value that triggered the callback
    # Handle pattern-matching IDs if they were used (though not for these specific IDs)
    triggered_prop_id = ctx.triggered[0]['prop_id']
    triggered_value = ctx.triggered[0]['value']
    # Extract the base component ID (e.g., "bess-capacity" from "bess-capacity.value")
    triggered_id_base = triggered_prop_id.split('.')[0]

    print(f"\n--- DEBUG update_bess_params_store (V5) ---")
    print(f"Triggered by: {triggered_id_base} (Prop: {triggered_prop_id})")
    print(f"Triggered Value: {triggered_value}")
    # print(f"Current Dropdown Value: {technology}") # Value from Input arg
    # print(f"Previous Store Data:") # Optional: Can be verbose
    # pprint.pprint(previous_bess_data)

    # Initialize new_store_data
    # Use previous data if valid, otherwise start with LFP defaults
    if previous_bess_data and isinstance(previous_bess_data, dict):
        # IMPORTANT: Create a copy to modify, don't change the original state object
        new_store_data = previous_bess_data.copy()
        print("  Base: Using previous store data.")
    else:
        print("  Base: No valid previous data, using LFP defaults.")
        new_store_data = default_bess_params_store.copy() # Start with LFP

    # --- Case 1: Technology Dropdown Changed ---
    if triggered_id_base == ID_BESS_TECH_DROPDOWN:
        print(f"-> Dropdown Trigger: Reloading defaults for '{technology}'")
        selected_technology = technology # Value from the input argument
        if selected_technology not in bess_technology_data:
            print(f"  WARNING: Invalid technology '{selected_technology}'. Defaulting to LFP.")
            selected_technology = "LFP" # Fallback

        # Start fresh with the defaults for the selected technology
        tech_defaults = bess_technology_data[selected_technology].copy() # Deep copy
        new_store_data = tech_defaults
        new_store_data[KEY_TECH] = selected_technology
        new_store_data[KEY_EXAMPLE_PRODUCT] = tech_defaults.get(KEY_EXAMPLE_PRODUCT, "N/A")

        # Apply the current Capacity and Power inputs (read from args)
        new_store_data[KEY_CAPACITY] = capacity
        new_store_data[KEY_POWER_MAX] = power
        print(f"  Defaults loaded for {selected_technology}. Capacity={capacity}, Power={power}.")

    # --- Case 2: Other BESS Input Changed ---
    else:
        print(f"-> Input Trigger ({triggered_id_base}): Updating specific field.")
        # Update the specific field that triggered the callback using its value
        # The 'new_store_data' is based on the previous state here.

        # Update based on triggered ID
        if triggered_id_base == ID_BESS_CAPACITY: new_store_data[KEY_CAPACITY] = triggered_value
        elif triggered_id_base == ID_BESS_POWER: new_store_data[KEY_POWER_MAX] = triggered_value
        elif triggered_id_base == ID_BESS_SB_BOS_COST: new_store_data[KEY_SB_BOS_COST] = triggered_value
        elif triggered_id_base == ID_BESS_PCS_COST: new_store_data[KEY_PCS_COST] = triggered_value
        elif triggered_id_base == ID_BESS_EPC_COST: new_store_data[KEY_EPC_COST] = triggered_value
        elif triggered_id_base == ID_BESS_SYS_INT_COST: new_store_data[KEY_SYS_INT_COST] = triggered_value
        elif triggered_id_base == ID_BESS_RTE: new_store_data[KEY_RTE] = triggered_value
        elif triggered_id_base == ID_BESS_INSURANCE: new_store_data[KEY_INSURANCE] = triggered_value
        elif triggered_id_base == ID_BESS_DISCONNECT_COST: new_store_data[KEY_DISCONNECT_COST] = triggered_value
        elif triggered_id_base == ID_BESS_RECYCLING_COST: new_store_data[KEY_RECYCLING_COST] = triggered_value
        elif triggered_id_base == ID_BESS_CYCLE_LIFE: new_store_data[KEY_CYCLE_LIFE] = triggered_value
        elif triggered_id_base == ID_BESS_DOD: new_store_data[KEY_DOD] = triggered_value
        elif triggered_id_base == ID_BESS_CALENDAR_LIFE: new_store_data[KEY_CALENDAR_LIFE] = triggered_value
        # Handle O&M inputs: update the triggered one and clear the other
        elif triggered_id_base == ID_BESS_FIXED_OM:
            new_store_data[KEY_FIXED_OM] = triggered_value
            if KEY_OM_KWHR_YR in new_store_data: del new_store_data[KEY_OM_KWHR_YR]
            print("  Updated Fixed O&M, cleared OM/kWh/yr key.")
        elif triggered_id_base == ID_BESS_OM_KWHR_YR:
            new_store_data[KEY_OM_KWHR_YR] = triggered_value
            if KEY_FIXED_OM in new_store_data: del new_store_data[KEY_FIXED_OM]
            print("  Updated OM/kWh/yr, cleared Fixed O&M key.")

        # Ensure the technology key still matches the dropdown value
        # This prevents the store from having data for one tech while the dropdown shows another
        current_dropdown_tech = technology # Read from input arg
        if new_store_data.get(KEY_TECH) != current_dropdown_tech:
            print(f"  WARNING: Store tech ({new_store_data.get(KEY_TECH)}) differs from dropdown ({current_dropdown_tech}). Forcing store tech to match dropdown.")
            # If the tech differs, it implies the dropdown changed *without* triggering
            # the store update itself (less likely but possible). We should probably
            # reload defaults for the dropdown tech in this edge case.
            # Let's reload defaults for safety here.
            if current_dropdown_tech not in bess_technology_data: current_dropdown_tech = "LFP"
            tech_defaults = bess_technology_data[current_dropdown_tech].copy()
            # Keep the just-updated value
            updated_key = None
            if triggered_id_base == ID_BESS_CAPACITY: updated_key = KEY_CAPACITY
            elif triggered_id_base == ID_BESS_POWER: updated_key = KEY_POWER_MAX
            # ... add all other elifs corresponding to the keys ...
            elif triggered_id_base == ID_BESS_SB_BOS_COST: updated_key = KEY_SB_BOS_COST
            elif triggered_id_base == ID_BESS_PCS_COST: updated_key = KEY_PCS_COST
            elif triggered_id_base == ID_BESS_EPC_COST: updated_key = KEY_EPC_COST
            elif triggered_id_base == ID_BESS_SYS_INT_COST: updated_key = KEY_SYS_INT_COST
            elif triggered_id_base == ID_BESS_RTE: updated_key = KEY_RTE
            elif triggered_id_base == ID_BESS_INSURANCE: updated_key = KEY_INSURANCE
            elif triggered_id_base == ID_BESS_DISCONNECT_COST: updated_key = KEY_DISCONNECT_COST
            elif triggered_id_base == ID_BESS_RECYCLING_COST: updated_key = KEY_RECYCLING_COST
            elif triggered_id_base == ID_BESS_CYCLE_LIFE: updated_key = KEY_CYCLE_LIFE
            elif triggered_id_base == ID_BESS_DOD: updated_key = KEY_DOD
            elif triggered_id_base == ID_BESS_CALENDAR_LIFE: updated_key = KEY_CALENDAR_LIFE
            elif triggered_id_base == ID_BESS_FIXED_OM: updated_key = KEY_FIXED_OM
            elif triggered_id_base == ID_BESS_OM_KWHR_YR: updated_key = KEY_OM_KWHR_YR

            # Reload defaults but preserve the value that just changed
            new_store_data = tech_defaults
            new_store_data[KEY_TECH] = current_dropdown_tech
            new_store_data[KEY_EXAMPLE_PRODUCT] = tech_defaults.get(KEY_EXAMPLE_PRODUCT, "N/A")
            new_store_data[KEY_CAPACITY] = capacity # Keep current capacity/power
            new_store_data[KEY_POWER_MAX] = power
            if updated_key:
                 new_store_data[updated_key] = triggered_value # Re-apply the specific change
                 print(f"  Reloaded defaults for {current_dropdown_tech} due to mismatch, but preserved change to {updated_key}.")
            else:
                 print(f"  Reloaded defaults for {current_dropdown_tech} due to mismatch.")


    # --- Final Log and Return ---
    print(f"FINAL Stored BESS Params (Tech: {new_store_data.get(KEY_TECH)}):")
    pprint.pprint(new_store_data)
    print(f"--- END DEBUG update_bess_params_store (V5) ---\n")
    return new_store_data


# --- Main Calculation Callback ---
@app.callback(
    [Output(ID_RESULTS_OUTPUT, "children"), Output(STORE_RESULTS, "data"), Output(ID_CALCULATION_ERR, "children"), Output(ID_CALCULATION_ERR, "is_open")],
    Input(ID_CALC_BTN, "n_clicks"),
    [State(STORE_EAF, "data"), State(STORE_BESS, "data"), State(STORE_UTILITY, "data"), State(STORE_FINANCIAL, "data"), State(STORE_INCENTIVE, "data"), State(ID_VALIDATION_ERR, "children")],
    prevent_initial_call=True,
)
def display_calculation_results(n_clicks, eaf_params, bess_params, utility_params, financial_params, incentive_params, validation_errors):
    """Triggers calculations and displays results when the Calculate button is clicked."""
    # --- START DEBUG PRINT ---
    print("-" * 30)
    print(f"DEBUG: display_calculation_results triggered (n_clicks={n_clicks})")
    print(f"DEBUG: Reading bess_params from State:")
    pprint.pprint(bess_params) # Print the parameters being used for calculation
    print("-" * 30)
    # --- END DEBUG PRINT ---

    results_output = html.Div("Click 'Calculate Results' to generate the analysis.", className="text-center text-muted")
    stored_data = {}; error_output = ""; error_open = False

    if n_clicks == 0: return results_output, stored_data, error_output, error_open
    # Prevent calculation if validation errors exist
    if validation_errors:
        error_output = html.Div([html.H5("Cannot Calculate - Validation Errors Exist", className="text-danger"), html.P("Please fix the errors listed above before calculating.")])
        error_open = True
        return results_output, stored_data, error_output, error_open

    # Check for missing parameters before proceeding
    if not all([eaf_params, bess_params, utility_params, financial_params, incentive_params]):
         print("ERROR: One or more parameter sets are missing in display_calculation_results")
         error_output = html.Div([ html.H5("Internal Error", className="text-danger"), html.P("Could not retrieve all required parameters. Please try reloading or check console.")])
         error_open = True
         return results_output, stored_data, error_output, error_open

    try:
        # Ensure the technology key exists (should always be set by update_bess_params_store)
        if KEY_TECH not in bess_params:
             raise ValueError("BESS parameters dictionary is missing the 'technology' key.")
        current_technology = bess_params.get(KEY_TECH, "LFP") # Get current tech for display

        print(f"DEBUG: Proceeding with calculations using technology: {current_technology}")

        # --- Perform Calculations ---
        billing_results = calculate_annual_billings(eaf_params, bess_params, utility_params)
        incentive_results = calculate_incentives(bess_params, incentive_params)
        financial_metrics = calculate_financial_metrics(bess_params, financial_params, eaf_params, billing_results["annual_savings"], incentive_results)

        # Store results and inputs for potential later use
        stored_data = {"billing": billing_results, "incentives": incentive_results, "financials": financial_metrics, "inputs": {"eaf": eaf_params, "bess": bess_params, "utility": utility_params, "financial": financial_params, "incentive": incentive_params}}

        # --- Generate Plotting Data ---
        plot_data_calculated = False; plot_error_message = ""; time_plot, eaf_power_plot, grid_power_plot, bess_power_plot = [], [], [], []; max_y_plot = 60
        try:
            plot_cycle_duration_min = eaf_params.get(KEY_CYCLE_DURATION_INPUT, 36); plot_cycle_duration_min = max(1, plot_cycle_duration_min) # Ensure positive
            time_plot = np.linspace(0, plot_cycle_duration_min, 200)
            eaf_power_plot = calculate_eaf_profile(time_plot, eaf_params.get(KEY_EAF_SIZE, 100), plot_cycle_duration_min)
            grid_power_plot, bess_power_plot = calculate_grid_bess_power(eaf_power_plot, eaf_params.get(KEY_GRID_CAP, 35), bess_params.get(KEY_POWER_MAX, 20))
            plot_data_calculated = True
            max_y_plot = max(np.max(eaf_power_plot) if len(eaf_power_plot)>0 else 0, eaf_params.get(KEY_GRID_CAP, 35)) * 1.15; max_y_plot = max(10, max_y_plot) # Ensure min range
        except Exception as plot_err: plot_error_message = f"Error generating single cycle plot data: {plot_err}"; print(plot_error_message)

        # --- Formatting Helpers ---
        def fmt_c(v): return f"${v:,.0f}" if pd.notna(v) else "N/A"
        def fmt_p(v): return f"{v:.1%}" if pd.notna(v) and isinstance(v, (int, float)) and abs(v)<=5 else (f"{'+' if v > 0 else ''}>500%" if pd.notna(v) and abs(v)>5 else "N/A")
        def fmt_y(v): return "Never" if pd.isna(v) or v == float("inf") else ("< 0 (Immediate)" if v < 0 else f"{v:.1f} yrs")

        # --- Create Results Cards ---
        metrics_card = dbc.Card([
            dbc.CardHeader("Financial Summary"),
            dbc.CardBody(html.Table([
                html.Tr([html.Td("Net Present Value (NPV)"), html.Td(fmt_c(financial_metrics.get("npv")))]),
                html.Tr([html.Td("Internal Rate of Return (IRR)"), html.Td(fmt_p(financial_metrics.get("irr")))]),
                html.Tr([html.Td("Simple Payback Period"), html.Td(fmt_y(financial_metrics.get("payback_years")))]),
                html.Tr([html.Td("Est. Battery Life (Replacement Interval)"), html.Td(fmt_y(financial_metrics.get("battery_life_years")))]),
                html.Tr([html.Td("Net Initial Cost (After Incentives)"), html.Td(fmt_c(financial_metrics.get("net_initial_cost")))]),
                html.Tr([html.Td("Gross Initial Cost (Before Incentives)"), html.Td(fmt_c(financial_metrics.get("total_initial_cost")))]),
            ], className="table table-sm"))
        ])

        # Calculate approximate annual replacement cost for display (only if life < 1 year)
        annual_replacement_cost_display = 0
        batt_life = financial_metrics.get("battery_life_years", float('inf'))
        if 0 < batt_life < 1:
            replacements_per_year = int(1 / batt_life)
            annual_replacement_cost_display = financial_metrics.get("total_initial_cost", 0) * replacements_per_year

        savings_card = dbc.Card([
            dbc.CardHeader("Annual Costs & Savings (Year 1 Estimates)"),
            dbc.CardBody(html.Table([
                html.Tr([html.Td("Baseline Bill (No BESS)"), html.Td(fmt_c(billing_results.get("annual_bill_without_bess")))]),
                html.Tr([html.Td("Projected Bill (With BESS)"), html.Td(fmt_c(billing_results.get("annual_bill_with_bess")))]),
                html.Tr([html.Td("Gross Annual Utility Savings"), html.Td(html.Strong(fmt_c(billing_results.get("annual_savings"))))]),
                html.Tr([html.Td("Annual O&M Cost"), html.Td(html.Strong(fmt_c(financial_metrics.get("initial_om_cost_year1")), className="text-danger"))]),
                html.Tr([html.Td("Annualized Replacement Cost (if life < 1yr)"), html.Td(html.Strong(fmt_c(annual_replacement_cost_display), className="text-danger"))]),
                html.Tr([html.Td("Net Annual Benefit (Savings - O&M - Repl.)"), html.Td(html.Strong(fmt_c(billing_results.get("annual_savings", 0) - financial_metrics.get("initial_om_cost_year1", 0) - annual_replacement_cost_display)))]),
            ], className="table table-sm"))
        ])

        inc_items = [html.Tr([html.Td(desc), html.Td(fmt_c(amount))]) for desc, amount in incentive_results.get("breakdown", {}).items()]
        inc_items.append(html.Tr([html.Td(html.Strong("Total Incentives")), html.Td(html.Strong(fmt_c(incentive_results.get("total_incentive")))) ]))
        incentives_card = dbc.Card([ dbc.CardHeader("Incentives Applied"), dbc.CardBody(html.Table(inc_items, className="table table-sm")) ])

        # --- Monthly Billing Table ---
        months = [calendar.month_abbr[i] for i in range(1, 13)]
        df_monthly = pd.DataFrame({
            "Month": months,
            "Bill Without BESS": [b.get("total_bill", 0) for b in billing_results.get("monthly_bills_without_bess", [])],
            "Bill With BESS": [b.get("total_bill", 0) for b in billing_results.get("monthly_bills_with_bess", [])],
            "Savings": billing_results.get("monthly_savings", []),
            "Peak Demand w/o BESS (kW)": [b.get("peak_demand_kw", 0) for b in billing_results.get("monthly_bills_without_bess", [])],
            "Peak Demand w/ BESS (kW)": [b.get("peak_demand_kw", 0) for b in billing_results.get("monthly_bills_with_bess", [])],
        })
        # Format table values
        for col in ["Bill Without BESS", "Bill With BESS", "Savings"]: df_monthly[col] = df_monthly[col].apply(fmt_c)
        for col in ["Peak Demand w/o BESS (kW)", "Peak Demand w/ BESS (kW)"]: df_monthly[col] = df_monthly[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        monthly_table = dash_table.DataTable(data=df_monthly.to_dict("records"), columns=[{"name": i, "id": i} for i in df_monthly.columns], style_cell={"textAlign": "right", "padding": "5px"}, style_header={"fontWeight": "bold", "textAlign": "center"}, style_data={"border": "1px solid grey"}, style_table={"overflowX": "auto", "minWidth": "100%"}, style_cell_conditional=[{"if": {"column_id": "Month"}, "textAlign": "left"}])

        # --- Graphs ---
        # Cash Flow Bar Chart
        years_cf = list(range(int(financial_params.get(KEY_LIFESPAN, 30)) + 1)); cash_flows_data = financial_metrics.get("cash_flows", [])
        if len(cash_flows_data) != len(years_cf): print(f"Warning: Cash flow data length ({len(cash_flows_data)}) doesn't match project lifespan + 1 ({len(years_cf)})."); cash_flows_data = cash_flows_data[: len(years_cf)] + [0] * (len(years_cf) - len(cash_flows_data))
        fig_cashflow = go.Figure(go.Bar(x=years_cf, y=cash_flows_data, name="After-Tax Cash Flow", marker_color=["red" if cf < 0 else "green" for cf in cash_flows_data]))
        fig_cashflow.update_layout(title="Project After-Tax Cash Flows", xaxis_title="Year", yaxis_title="Cash Flow ($)", yaxis_tickformat="$,.0f", plot_bgcolor="white", margin=dict(l=40, r=20, t=40, b=30))

        # Cumulative Cash Flow Line Chart
        cumulative_cash_flows = np.cumsum(cash_flows_data)
        fig_cumulative_cashflow = go.Figure(go.Scatter(x=years_cf, y=cumulative_cash_flows, mode='lines+markers', name='Cumulative Cash Flow', line=dict(color='purple')))
        fig_cumulative_cashflow.add_hline(y=0, line_width=1, line_dash="dash", line_color="black")
        fig_cumulative_cashflow.update_layout(title="Cumulative After-Tax Cash Flow", xaxis_title="Year", yaxis_title="Cumulative Cash Flow ($)", yaxis_tickformat="$,.0f", plot_bgcolor="white", margin=dict(l=40, r=20, t=40, b=30))


        # Single Cycle Power Profile
        fig_single_cycle = go.Figure()
        if plot_data_calculated:
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=eaf_power_plot, mode='lines', name='EAF Power Demand', line=dict(color='blue', width=2)))
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=grid_power_plot, mode='lines', name='Grid Power Supply', line=dict(color='green', width=2)))
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=bess_power_plot, mode='lines', name='BESS Power Output', line=dict(color='red', width=2), fill='tozeroy'))
            grid_cap_val = eaf_params.get(KEY_GRID_CAP, 35)
            fig_single_cycle.add_shape(type="line", x0=0, y0=grid_cap_val, x1=plot_cycle_duration_min, y1=grid_cap_val, line=dict(color='black', width=2, dash='dash'), name='Grid Cap')
            fig_single_cycle.add_annotation(x=plot_cycle_duration_min * 0.9, y=grid_cap_val + max_y_plot * 0.03, text=f"Grid Cap ({grid_cap_val} MW)", showarrow=False, font=dict(color='black', size=10))
        else: fig_single_cycle.update_layout(xaxis = {'visible': False}, yaxis = {'visible': False}, annotations = [{'text': 'Error generating plot data', 'xref': 'paper', 'yref': 'paper', 'showarrow': False, 'font': {'size': 16}}])
        fig_single_cycle.update_layout(title=f'Simulated EAF Cycle Profile ({eaf_params.get(KEY_EAF_SIZE, "N/A")}-ton)', xaxis_title=f"Time in Cycle (minutes, Duration: {plot_cycle_duration_min:.1f} min)", yaxis_title="Power (MW)", yaxis_range=[0, max_y_plot], showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), template="plotly_white", margin=dict(l=40, r=20, t=50, b=40))

        # Technology comparison table
        print(f"DEBUG: Creating comparison table for technology: {current_technology}")
        tech_comparison = create_technology_comparison_table(
            current_technology,
            bess_params.get(KEY_CAPACITY, 0),
            bess_params.get(KEY_POWER_MAX, 0)
        )

        # --- Assemble Results Output ---
        results_output = html.Div([
            html.H3("Calculation Results", className="mb-4"),
            dbc.Row([
                dbc.Col(metrics_card, lg=4, md=6, className="mb-4"),
                dbc.Col(savings_card, lg=4, md=6, className="mb-4"),
                dbc.Col(incentives_card, lg=4, md=12, className="mb-4"),
            ]),
            html.H4("Technology Comparison (at current size)", className="mt-4 mb-3"),
            tech_comparison,
            html.H4("Monthly Billing Breakdown", className="mt-4 mb-3"),
            monthly_table,
            html.H4("Single Cycle Power Profile", className="mt-4 mb-3"),
            dcc.Graph(figure=fig_single_cycle),
            html.H4("Cash Flow Analysis", className="mt-4 mb-3"),
            dbc.Row([
                 dbc.Col(dcc.Graph(figure=fig_cashflow), md=6),
                 dbc.Col(dcc.Graph(figure=fig_cumulative_cashflow), md=6), # Add cumulative plot
            ]),
        ])
        error_output = ""; error_open = False # Clear any previous calculation errors

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"ERROR during calculation: {e}\n{tb_str}") # Log full traceback to console
        # Display error message to user
        error_output = html.Div([
            html.H5("Calculation Error", className="text-danger"),
            html.P("An error occurred during calculation:"),
            html.Pre(f"{type(e).__name__}: {str(e)}"),
            html.Details([
                html.Summary("Click for technical details (Traceback)"),
                html.Pre(tb_str)
            ]),
            html.Details([ # Show parameters used during error
                html.Summary("BESS Parameters at time of error:"),
                html.Pre(pprint.pformat(bess_params))
            ])
        ])
        error_open = True
        results_output = html.Div("Could not generate results due to an error.", className="text-center text-danger")
        stored_data = {} # Clear stored results on error

    return results_output, stored_data, error_output, error_open


# --- Optimization Callback ---
@app.callback(
    [Output(ID_OPTIMIZE_OUTPUT, "children"), Output(STORE_OPTIMIZATION, "data")],
    Input(ID_OPTIMIZE_BTN, "n_clicks"),
    [State(STORE_EAF, "data"), State(STORE_BESS, "data"), State(STORE_UTILITY, "data"), State(STORE_FINANCIAL, "data"), State(STORE_INCENTIVE, "data"), State(ID_VALIDATION_ERR, "children")],
    prevent_initial_call=True,
)
def display_optimization_results(n_clicks, eaf_params, bess_base_params, utility_params, financial_params, incentive_params, validation_errors):
    """Triggers optimization calculation and displays results."""
    opt_output = html.Div("Click 'Optimize Battery Size' to run the analysis.", className="text-center text-muted")
    opt_stored_data = {}
    if n_clicks == 0: return opt_output, opt_stored_data

    # Prevent optimization if validation errors exist
    if validation_errors:
        opt_output = dbc.Alert([html.H4("Cannot Optimize - Validation Errors Exist", className="text-danger"), html.P("Please fix the errors listed in the Parameters/Incentives tabs before optimizing.")], color="danger")
        return opt_output, opt_stored_data

    # Check for missing parameters
    if not all([eaf_params, bess_base_params, utility_params, financial_params, incentive_params]):
        opt_output = dbc.Alert("Cannot Optimize - Missing one or more parameter sets.", color="danger")
        return opt_output, opt_stored_data

    try:
        print("Starting Optimization Callback...")
        # Pass the full bess_base_params which includes tech-specific costs/perf
        opt_results = optimize_battery_size(eaf_params, utility_params, financial_params, incentive_params, bess_base_params)
        opt_stored_data = opt_results
        print("Optimization Function Finished.")

        # Display results if optimization was successful
        if opt_results and opt_results.get("best_capacity") is not None:
            best_metrics = opt_results.get("best_metrics", {})
            # Formatting helpers
            def fmt_c(v): return f"${v:,.0f}" if pd.notna(v) else "N/A"
            def fmt_p(v): return f"{v:.1%}" if pd.notna(v) and isinstance(v, (int, float)) and abs(v)<=5 else (f"{'+' if v > 0 else ''}>500%" if pd.notna(v) and abs(v)>5 else "N/A")
            def fmt_y(v): return "Never" if pd.isna(v) or v == float("inf") else ("< 0 yrs" if v < 0 else f"{v:.1f} yrs")

            # Summary card for the best result
            best_summary = dbc.Card([
                dbc.CardHeader(f"Optimal Size Found (Max NPV) - Tech: {bess_base_params.get(KEY_TECH, 'N/A')}"),
                dbc.CardBody(html.Table([
                    html.Tr([html.Td("Capacity (MWh)"), html.Td(f"{opt_results['best_capacity']:.1f}")]),
                    html.Tr([html.Td("Power (MW)"), html.Td(f"{opt_results['best_power']:.1f}")]),
                    html.Tr([html.Td("Resulting NPV"), html.Td(fmt_c(opt_results["best_npv"]))]),
                    html.Tr([html.Td("Resulting IRR"), html.Td(fmt_p(best_metrics.get("irr")))]),
                    html.Tr([html.Td("Resulting Payback"), html.Td(fmt_y(best_metrics.get("payback_years")))]),
                    html.Tr([html.Td("Annual Savings (Year 1)"), html.Td(fmt_c(best_metrics.get("annual_savings_year1")))]),
                    html.Tr([html.Td("Net Initial Cost"), html.Td(fmt_c(best_metrics.get("net_initial_cost")))]),
                ], className="table table-sm"))
            ], className="mb-4")

            # Table of all tested combinations
            all_results_df = pd.DataFrame(opt_results.get("all_results", []))
            table_section = html.Div("No optimization results data to display in table.")
            if not all_results_df.empty:
                # Select and rename columns for display
                display_cols = {"capacity": "Capacity (MWh)", "power": "Power (MW)", "npv": "NPV ($)", "irr": "IRR (%)", "payback_years": "Payback (Yrs)", "annual_savings": "Savings ($/Yr)", "net_initial_cost": "Net Cost ($)"}
                all_results_df = all_results_df[[k for k in display_cols if k in all_results_df.columns]].copy() # Handle missing cols
                all_results_df.rename(columns=display_cols, inplace=True)
                # Format columns
                for col in ["Capacity (MWh)", "Power (MW)"]: all_results_df[col] = all_results_df[col].map("{:.1f}".format)
                for col in ["NPV ($)", "Savings ($/Yr)", "Net Cost ($)"]: all_results_df[col] = all_results_df[col].apply(fmt_c)
                all_results_df["IRR (%)"] = all_results_df["IRR (%)"].apply(fmt_p)
                all_results_df["Payback (Yrs)"] = all_results_df["Payback (Yrs)"].apply(fmt_y)
                # Create DataTable
                all_results_table = dash_table.DataTable(
                    data=all_results_df.to_dict("records"),
                    columns=[{"name": i, "id": i} for i in all_results_df.columns],
                    page_size=10, sort_action="native", filter_action="native",
                    style_cell={"textAlign": "right"}, style_header={"fontWeight": "bold"},
                    style_table={"overflowX": "auto", "minWidth": "100%"},
                    style_cell_conditional=[{"if": {"column_id": c}, "textAlign": "left"} for c in ["Capacity (MWh)", "Power (MW)"]]
                )
                table_section = html.Div([html.H4("All Tested Combinations", className="mt-4 mb-3"), all_results_table])

            opt_output = html.Div([html.H3("Battery Sizing Optimization Results", className="mb-4"), best_summary, table_section])
        else:
            # Handle case where optimization didn't find a suitable result
            opt_output = dbc.Alert([
                html.H4("Optimization Failed or No Viable Solution", className="text-warning"),
                html.P("Could not find an optimal battery size with the given parameters. Reasons might include:"),
                html.Ul([
                    html.Li("No combinations resulted in a positive NPV or reasonable payback."),
                    html.Li("Errors occurred during the simulation for all tested sizes (check console logs)."),
                    html.Li("Parameter ranges for optimization might need adjustment."),
                    html.Li("The selected technology might not be profitable under current conditions.")
                ])
            ], color="warning")

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"ERROR during optimization: {e}\n{tb_str}") # Log full traceback
        opt_output = dbc.Alert([
            html.H5("Optimization Error", className="text-danger"),
            html.P("An error occurred during the optimization process:"),
            html.Pre(f"{type(e).__name__}: {str(e)}"),
            html.Details([html.Summary("Click for technical details (Traceback)"), html.Pre(tb_str)])
        ], color="danger")
        opt_stored_data = {} # Clear stored results on error

    return opt_output, opt_stored_data


# --- Run the App ---
if __name__ == "__main__":
    # Set debug=True for development (enables hot-reloading and error pages)
    # Set debug=False for production deployment
    app.run_server(host="0.0.0.0", port=8050, debug=True)

# --- END OF FILE ---