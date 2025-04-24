import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback_context, ALL, dash_table, ctx
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import json
from datetime import datetime
import calendar
import traceback
import pprint
import io
import base64
import math  # For ceil

# --- numpy_financial fallback ---
try:
    import numpy_financial as npf
except ImportError:
    print("WARNING: numpy_financial package is required. pip install numpy-financial")

    class DummyNPF:
        def npv(self, rate, values):
            if rate <= -1:
                return float("nan")
            try:
                return sum(values[i] / ((1 + rate) ** i) for i in range(len(values)))
            except:
                return float("nan")

        def irr(self, values):
            if not values or values[0] >= 0:
                return float("nan")
            try:
                low_rate, high_rate = -0.99, 1.0
                tolerance = 1e-6
                max_iter = 100
                for _ in range(max_iter):
                    mid_rate = (low_rate + high_rate) / 2
                    npv_mid = self.npv(mid_rate, values)
                    if abs(npv_mid) < tolerance:
                        return mid_rate
                    if npv_mid > 0:
                        low_rate = mid_rate
                    else:
                        high_rate = mid_rate
                    if high_rate - low_rate < tolerance:
                        break
                # Return mid_rate only if NPV is reasonably close to zero
                return (
                    mid_rate
                    if abs(self.npv(mid_rate, values)) < tolerance * 10
                    else float("nan")
                )
            except:
                return float("nan")

    npf = DummyNPF()

# --- Constants ---

# Store IDs
STORE_EAF = "eaf-store"
STORE_UTILITY = "utility-store"
STORE_BESS = "bess-store"
STORE_FINANCIAL = "financial-store"
STORE_INCENTIVE = "incentive-store"
STORE_RESULTS = "results-store"
STORE_OPTIMIZATION = "optimization-store"
STORE_LOADED_STATE = "loaded-state-store"  # To trigger updates after load

# Component IDs
ID_PARAM_ACCORDION = "parameter-accordion"
ID_DEBT_PARAMS_CARD = "debt-params-card"
ID_DEPREC_PARAMS_CARD = "deprec-params-card"
ID_DEGRAD_PARAMS_CARD = "degrad-params-card"
ID_ANCILLARY_REVENUE_INPUT = "ancillary-revenue-input"
ID_LOAN_AMOUNT_PERCENT = "loan-amount-percent"
ID_LOAN_INTEREST_RATE = "loan-interest-rate"
ID_LOAN_TERM_YEARS = "loan-term-years"
ID_MACRS_SCHEDULE = "macrs-schedule-dropdown"
ID_DEGRAD_RATE_CAP_YR = "degrad-rate-cap-yr"
ID_DEGRAD_RATE_RTE_YR = "degrad-rate-rte-yr"
ID_REPLACEMENT_THRESHOLD = "replacement-threshold-percent"
ID_SAVE_PROJECT_BTN = "save-project-button"
ID_LOAD_PROJECT_UPLOAD = "load-project-upload"
ID_DOWNLOAD_PROJECT_JSON = "download-project-json"
ID_RESULTS_TABLES_COLLAPSE = "results-tables-collapse"
ID_RESULTS_TABLES_TOGGLE_BTN = "results-tables-toggle-button"
ID_MILL_DROPDOWN = "mill-dropdown"
ID_MILL_INFO_CARD = "mill-info-card"
ID_VALIDATION_ERR = "validation-error"
ID_CALCULATION_ERR = "calculation-error"
ID_CONTINUE_PARAMS_BTN = "continue-params-btn"
ID_CONTINUE_INCENTIVES_BTN = "continue-incentives-btn"
ID_MAIN_TABS = "main-tabs"
ID_UTILITY_DROPDOWN = "utility-dropdown"
ID_OFF_PEAK = "off-peak-rate"
ID_MID_PEAK = "mid-peak-rate"
ID_PEAK = "peak-rate"
ID_DEMAND_CHARGE = "demand-charge"
ID_SEASONAL_TOGGLE = "seasonal-toggle"
ID_SEASONAL_CONTAINER = "seasonal-container"
ID_TOU_CONTAINER = "tou-container"
ID_ADD_TOU_BTN = "add-tou-btn"
ID_EAF_SIZE = "eaf-size"
ID_EAF_COUNT = "eaf-count"
ID_GRID_CAP = "grid-cap"
ID_CYCLES_PER_DAY = "cycles-per-day"
ID_CYCLE_DURATION = "cycle-duration"
ID_DAYS_PER_YEAR = "days-per-year"
ID_BESS_CAPACITY = "bess-capacity"
ID_BESS_POWER = "bess-power"
ID_BESS_C_RATE_DISPLAY = "bess-c-rate-display"
ID_BESS_TECH_DROPDOWN = "bess-tech-dropdown"
ID_BESS_EXAMPLE_PRODUCT = "bess-example-product"
ID_BESS_SB_BOS_COST = "bess-sb-bos-cost"
ID_BESS_PCS_COST = "bess-pcs-cost"
ID_BESS_SYS_INT_COST = "bess-sys-int-cost"
ID_BESS_EPC_COST = "bess-epc-cost"
ID_BESS_OPEX_CONTAINER = "bess-opex-container"
ID_BESS_FIXED_OM = "bess-fixed-om"
ID_BESS_OM_KWHR_YR = "bess-om-kwhr-yr"
ID_BESS_RTE = "bess-rte"
ID_BESS_INSURANCE = "bess-insurance"
ID_BESS_DISCONNECT_COST = "bess-disconnect-cost"
ID_BESS_RECYCLING_COST = "bess-recycling-cost"
ID_BESS_CYCLE_LIFE = "bess-cycle-life"
ID_BESS_DOD = "bess-dod"
ID_BESS_CALENDAR_LIFE = "bess-calendar-life"
ID_WACC = "wacc"
ID_LIFESPAN = "lifespan"
ID_TAX_RATE = "tax-rate"
ID_INFLATION_RATE = "inflation-rate"
ID_SALVAGE = "salvage"
ID_ITC_ENABLED = "itc-enabled"
ID_ITC_PERCENT = "itc-percent"
ID_CALC_BTN = "calc-btn"
ID_OPTIMIZE_BTN = "optimize-btn"
ID_RESULTS_OUTPUT = "results-output"
ID_OPTIMIZE_OUTPUT = "optimize-output"
ID_WINTER_MULTIPLIER = "winter-multiplier"
ID_SUMMER_MULTIPLIER = "summer-multiplier"
ID_SHOULDER_MULTIPLIER = "shoulder-multiplier"
ID_WINTER_MONTHS = "winter-months"
ID_SUMMER_MONTHS = "summer-months"
ID_SHOULDER_MONTHS = "shoulder-months"

# Data Keys
KEY_TECH = "technology"
KEY_CAPACITY = "capacity_mwh"
KEY_POWER_MAX = "power_max_mw"
KEY_EXAMPLE_PRODUCT = "example_product"
KEY_SB_BOS_COST = "sb_bos_cost_per_kwh"
KEY_PCS_COST = "pcs_cost_per_kw"
KEY_EPC_COST = "epc_cost_per_kwh"
KEY_SYS_INT_COST = "sys_int_cost_per_kwh"
KEY_FIXED_OM = "fixed_om_per_kw_yr"
KEY_OM_KWHR_YR = "om_cost_per_kwh_yr"
KEY_RTE = "round_trip_efficiency_percent"
KEY_INSURANCE = "insurance_percent_yr"
KEY_DISCONNECT_COST = "disconnect_cost_per_kwh"
KEY_RECYCLING_COST = "recycling_cost_per_kwh"
KEY_CYCLE_LIFE = "cycle_life"
KEY_DOD = "depth_of_discharge_percent"
KEY_CALENDAR_LIFE = "calendar_life_years"
KEY_ENERGY_RATES = "energy_rates"
KEY_DEMAND_CHARGE = "demand_charge"
KEY_TOU_RAW = "tou_raw"
KEY_TOU_FILLED = "tou_filled"
KEY_SEASONAL = "seasonal_enabled"
KEY_WINTER_MONTHS = "winter_months"
KEY_SUMMER_MONTHS = "summer_months"
KEY_SHOULDER_MONTHS = "shoulder_months"
KEY_WINTER_MULT = "winter_multiplier"
KEY_SUMMER_MULT = "summer_multiplier"
KEY_SHOULDER_MULT = "shoulder_multiplier"
KEY_EAF_SIZE = "eaf_size_tons"
KEY_CYCLES_PER_DAY = "cycles_per_day"
KEY_DAYS_PER_YEAR = "days_per_year"
KEY_CYCLE_DURATION = "cycle_duration_min"
KEY_CYCLE_DURATION_INPUT = "cycle_duration_input_min"  # Track user input separately
KEY_GRID_CAP = "grid_capacity_mw"
KEY_WACC = "wacc_rate"
KEY_LIFESPAN = "project_lifespan_years"
KEY_TAX_RATE = "tax_rate"
KEY_INFLATION = "inflation_rate"
KEY_SALVAGE = "salvage_value"
KEY_DEBT_PARAMS = "debt_parameters"
KEY_DEPREC_PARAMS = "depreciation_parameters"
KEY_DEGRAD_PARAMS = "degradation_parameters"
KEY_ANCILLARY_REVENUE = "ancillary_revenue_per_year"
KEY_LOAN_PERCENT = "loan_percent"
KEY_LOAN_INTEREST = "loan_interest_rate"
KEY_LOAN_TERM = "loan_term_years"
KEY_MACRS_SCHEDULE = "macrs_schedule"  # e.g., '5-Year'
KEY_DEGRAD_CAP_YR = "degradation_capacity_percent_yr"
KEY_DEGRAD_RTE_YR = "degradation_rte_percent_yr"
KEY_REPL_THRESH = "replacement_threshold_percent"


# --- BESS Parameter Helpers ---
def get_default_bess_params():
    """Return a complete set of default BESS parameters with all required fields."""
    return {
        KEY_TECH: "LFP",
        KEY_CAPACITY: 0.001,  # Small positive value instead of 0
        KEY_POWER_MAX: 0.001,  # Small positive value instead of 0
        KEY_EXAMPLE_PRODUCT: "Tesla Megapack 2XL (Illustrative)",
        KEY_SB_BOS_COST: 210,
        KEY_PCS_COST: 75,
        KEY_EPC_COST: 56,
        KEY_SYS_INT_COST: 42,
        KEY_FIXED_OM: 5,  # Make sure this is always included
        KEY_OM_KWHR_YR: 0,  # Include both O&M parameters
        KEY_RTE: 86,
        KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2,
        KEY_RECYCLING_COST: 1,
        KEY_CYCLE_LIFE: 4000,
        KEY_DOD: 95,
        KEY_CALENDAR_LIFE: 16,
    }


def ensure_bess_params_complete(params_dict):
    """Ensure any BESS params dictionary has all required fields."""
    if not params_dict or not isinstance(params_dict, dict):
        return get_default_bess_params()

    # Start with default values
    complete_params = get_default_bess_params()

    # Update with provided values
    for key, value in params_dict.items():
        complete_params[key] = value

    # Explicitly ensure both O&M fields exist
    if KEY_FIXED_OM not in complete_params:
        complete_params[KEY_FIXED_OM] = 0
    if KEY_OM_KWHR_YR not in complete_params:
        complete_params[KEY_OM_KWHR_YR] = 0

    return complete_params


# --- Initialize App ---
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
)
server = app.server
app.title = "Advanced Battery Profitability Tool"

# --- Default Parameters ---
default_utility_params = {
    KEY_ENERGY_RATES: {"off_peak": 50, "mid_peak": 100, "peak": 150},
    KEY_DEMAND_CHARGE: 10,
    KEY_TOU_RAW: [
        (0.0, 8.0, "off_peak"),
        (8.0, 10.0, "peak"),
        (10.0, 16.0, "mid_peak"),
        (16.0, 20.0, "peak"),
        (20.0, 24.0, "off_peak"),
    ],
    KEY_TOU_FILLED: [
        (0.0, 8.0, "off_peak"),
        (8.0, 10.0, "peak"),
        (10.0, 16.0, "mid_peak"),
        (16.0, 20.0, "peak"),
        (20.0, 24.0, "off_peak"),
    ],
    KEY_SEASONAL: False,
    KEY_WINTER_MONTHS: [11, 12, 1, 2, 3],
    KEY_SUMMER_MONTHS: [6, 7, 8, 9],
    KEY_SHOULDER_MONTHS: [4, 5, 10],
    KEY_WINTER_MULT: 1.0,
    KEY_SUMMER_MULT: 1.2,
    KEY_SHOULDER_MULT: 1.1,
}
default_financial_params = {
    KEY_WACC: 0.131,
    KEY_LIFESPAN: 30,
    KEY_TAX_RATE: 0.2009,
    KEY_INFLATION: 0.024,
    KEY_SALVAGE: 0.1,
    # New Defaults
    KEY_DEBT_PARAMS: {
        KEY_LOAN_PERCENT: 70.0,
        KEY_LOAN_INTEREST: 0.08,
        KEY_LOAN_TERM: 10,
    },
    KEY_DEPREC_PARAMS: {KEY_MACRS_SCHEDULE: "5-Year"},
    KEY_DEGRAD_PARAMS: {
        KEY_DEGRAD_CAP_YR: 1.5,
        KEY_DEGRAD_RTE_YR: 0.25,
        KEY_REPL_THRESH: 70.0,
    },
    KEY_ANCILLARY_REVENUE: 0.0,
}
default_incentive_params = {
    "itc_enabled": False,
    "itc_percentage": 30,
    "ceic_enabled": False,
    "ceic_percentage": 30,
    "bonus_credit_enabled": False,
    "bonus_credit_percentage": 10,
    "sgip_enabled": False,
    "sgip_amount": 400,
    "ess_enabled": False,
    "ess_amount": 280,
    "mabi_enabled": False,
    "mabi_amount": 250,
    "cs_enabled": False,
    "cs_amount": 225,
    "custom_incentive_enabled": False,
    "custom_incentive_type": "per_kwh",
    "custom_incentive_amount": 100,
    "custom_incentive_description": "Custom incentive",
}

# --- BESS Technology Data ---
bess_technology_data = {
    "LFP": {
        KEY_EXAMPLE_PRODUCT: "Tesla Megapack 2XL (Illustrative)",
        KEY_SB_BOS_COST: 210,
        KEY_PCS_COST: 75,
        KEY_EPC_COST: 56,
        KEY_SYS_INT_COST: 42,
        KEY_FIXED_OM: 5,
        KEY_RTE: 86,
        KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2,
        KEY_RECYCLING_COST: 1,
        KEY_CYCLE_LIFE: 4000,
        KEY_DOD: 95,
        KEY_CALENDAR_LIFE: 16,
    },
    "NMC": {
        KEY_EXAMPLE_PRODUCT: "Samsung SDI E3 (Illustrative)",
        KEY_SB_BOS_COST: 250,
        KEY_PCS_COST: 75,
        KEY_EPC_COST: 63,
        KEY_SYS_INT_COST: 48,
        KEY_FIXED_OM: 6,
        KEY_RTE: 86,
        KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2,
        KEY_RECYCLING_COST: -2,
        KEY_CYCLE_LIFE: 3500,
        KEY_DOD: 90,
        KEY_CALENDAR_LIFE: 13,
    },
    "Redox Flow (Vanadium)": {
        KEY_EXAMPLE_PRODUCT: "Invinity VS3 / Generic VRFB (Illustrative)",
        KEY_SB_BOS_COST: 250,
        KEY_PCS_COST: 138,
        KEY_EPC_COST: 70,
        KEY_SYS_INT_COST: 60,
        KEY_FIXED_OM: 7,
        KEY_RTE: 68,
        KEY_INSURANCE: 0.6,
        KEY_DISCONNECT_COST: 3,
        KEY_RECYCLING_COST: 5,
        KEY_CYCLE_LIFE: 15000,
        KEY_DOD: 100,
        KEY_CALENDAR_LIFE: 20,
    },
    "Sodium-Ion": {
        KEY_EXAMPLE_PRODUCT: "Natron Energy BlueTray 4000 (Illustrative - High Power Focus)",
        KEY_SB_BOS_COST: 300,
        KEY_PCS_COST: 100,
        KEY_EPC_COST: 60,
        KEY_SYS_INT_COST: 50,
        KEY_FIXED_OM: 5,
        KEY_RTE: 90,
        KEY_INSURANCE: 0.5,
        KEY_DISCONNECT_COST: 2,
        KEY_RECYCLING_COST: 3,
        KEY_CYCLE_LIFE: 10000,
        KEY_DOD: 100,
        KEY_CALENDAR_LIFE: 20,
    },
    "Iron-Air": {
        KEY_EXAMPLE_PRODUCT: "Form Energy (Illustrative - Long Duration Focus)",
        KEY_SB_BOS_COST: 30,
        KEY_PCS_COST: 300,
        KEY_EPC_COST: 20,
        KEY_SYS_INT_COST: 15,
        KEY_FIXED_OM: 8,
        KEY_RTE: 50,
        KEY_INSURANCE: 0.7,
        KEY_DISCONNECT_COST: 3,
        KEY_RECYCLING_COST: 1,
        KEY_CYCLE_LIFE: 10000,
        KEY_DOD: 100,
        KEY_CALENDAR_LIFE: 20,
    },
    "Hybrid Supercapacitor": {
        KEY_EXAMPLE_PRODUCT: "Hycap Hybrid Supercapacitor System",
        KEY_SB_BOS_COST: 900,
        KEY_PCS_COST: 100,
        KEY_EPC_COST: 50,
        KEY_SYS_INT_COST: 50,
        KEY_OM_KWHR_YR: 2,
        KEY_RTE: 98,
        KEY_INSURANCE: 0.1,
        KEY_DISCONNECT_COST: 0.5,
        KEY_RECYCLING_COST: 1.0,
        KEY_CYCLE_LIFE: 100000,
        KEY_DOD: 100,
        KEY_CALENDAR_LIFE: 30,
    },
}

# --- Default BESS Parameters Store Structure ---
default_bess_params_store = {
    KEY_TECH: "LFP",
    KEY_CAPACITY: 40,
    KEY_POWER_MAX: 20,
    **bess_technology_data["LFP"],  # Populate with defaults for LFP
}

# --- Nucor Mill Data ---
nucor_mills = {
    "West Virginia": {
        "location": "Apple Grove, WV",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "DC",
        "eaf_manufacturer": "SMS",
        KEY_EAF_SIZE: 190,
        KEY_CYCLES_PER_DAY: 26,
        "tons_per_year": 3000000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Appalachian Power",
        KEY_GRID_CAP: 50,
    },
    "Auburn": {
        "location": "Auburn, NY",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Unknown",
        KEY_EAF_SIZE: 60,
        KEY_CYCLES_PER_DAY: 28,
        "tons_per_year": 510000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "New York State Electric & Gas",
        KEY_GRID_CAP: 25,
    },
    "Birmingham": {
        "location": "Birmingham, AL",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Unknown",
        KEY_EAF_SIZE: 52,
        KEY_CYCLES_PER_DAY: 20,
        "tons_per_year": 310000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Alabama Power",
        KEY_GRID_CAP: 20,
    },
    "Arkansas": {
        "location": "Blytheville, AR",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "Demag",
        KEY_EAF_SIZE: 150,
        KEY_CYCLES_PER_DAY: 28,
        "tons_per_year": 2500000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 38,
        "utility": "Entergy Arkansas",
        KEY_GRID_CAP: 45,
    },
    "Kankakee": {
        "location": "Bourbonnais, IL",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Danieli",
        KEY_EAF_SIZE: 73,
        KEY_CYCLES_PER_DAY: 39,
        "tons_per_year": 850000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "ComEd",
        KEY_GRID_CAP: 30,
    },
    "Brandenburg": {
        "location": "Brandenburg, KY",
        "type": "Sheet",
        "eaf_count": 1,
        "eaf_type": "DC",
        "eaf_manufacturer": "Danieli",
        KEY_EAF_SIZE: 150,
        KEY_CYCLES_PER_DAY: 27,
        "tons_per_year": 1200000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "LG&E KU",
        KEY_GRID_CAP: 45,
    },
    "Hertford": {
        "location": "Cofield, NC",
        "type": "Plate",
        "eaf_count": 1,
        "eaf_type": "DC",
        "eaf_manufacturer": "MAN GHH",
        KEY_EAF_SIZE: 150,
        KEY_CYCLES_PER_DAY: 30,
        "tons_per_year": 1350000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Dominion Energy",
        KEY_GRID_CAP: 45,
    },
    "Crawfordsville": {
        "location": "Crawfordsville, IN",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "Brown-Boveri",
        KEY_EAF_SIZE: 118,
        KEY_CYCLES_PER_DAY: 27,
        "tons_per_year": 1890000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Duke Energy",
        KEY_GRID_CAP: 40,
    },
    "Darlington": {
        "location": "Darlington, SC",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "MAN GHH",
        KEY_EAF_SIZE: 110,
        KEY_CYCLES_PER_DAY: 30,
        "tons_per_year": 980000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Duke Energy",
        KEY_GRID_CAP: 40,
    },
    "Decatur": {
        "location": "Decatur, AL",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "DC",
        "eaf_manufacturer": "NKK-SE",
        KEY_EAF_SIZE: 165,
        KEY_CYCLES_PER_DAY: 20,
        "tons_per_year": 2000000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Alabama Power",
        KEY_GRID_CAP: 48,
    },
    "Gallatin": {
        "location": "Ghent, KY",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "?",
        "eaf_manufacturer": "NKK-SE, Danieli",
        KEY_EAF_SIZE: 175,
        KEY_CYCLES_PER_DAY: 27,
        "tons_per_year": 2800000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Kentucky Utilities",
        KEY_GRID_CAP: 53,
    },
    "Hickman": {
        "location": "Hickman, AR",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "MAN GHH",
        KEY_EAF_SIZE: 150,
        KEY_CYCLES_PER_DAY: 22,
        "tons_per_year": 2000000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Entergy Arkansas",
        KEY_GRID_CAP: 45,
    },
    "Berkeley": {
        "location": "Huger, SC",
        "type": "Sheet/Beam Mill",
        "eaf_count": 2,
        "eaf_type": "?",
        "eaf_manufacturer": "MAN GHH",
        KEY_EAF_SIZE: 154,
        KEY_CYCLES_PER_DAY: 26,
        "tons_per_year": 2430000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Santee Cooper",
        KEY_GRID_CAP: 46,
    },
    "Texas": {
        "location": "Jewett, TX",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "SMS Concast",
        KEY_EAF_SIZE: 100,
        KEY_CYCLES_PER_DAY: 33,
        "tons_per_year": 1000000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Oncor Electric Delivery",
        KEY_GRID_CAP: 30,
    },
    "Kingman": {
        "location": "Kingman, AZ",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Danieli",
        KEY_EAF_SIZE: 100,
        KEY_CYCLES_PER_DAY: 21,
        "tons_per_year": 630000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "UniSource Energy Services",
        KEY_GRID_CAP: 30,
    },
    "Marion": {
        "location": "Marion, OH",
        "type": "Bar Mill/Sign Pos",
        "eaf_count": 1,
        "eaf_type": "?",
        "eaf_manufacturer": "?",
        KEY_EAF_SIZE: 100,
        KEY_CYCLES_PER_DAY: 40,
        "tons_per_year": 1200000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "AEP Ohio",
        KEY_GRID_CAP: 30,
    },
    "Nebraska": {
        "location": "Nebraska, NE",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "?",
        "eaf_manufacturer": "MAN GHH",
        KEY_EAF_SIZE: 95,
        KEY_CYCLES_PER_DAY: 35,
        "tons_per_year": 1000000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Nebraska Public Power District",
        KEY_GRID_CAP: 29,
    },
    "Utah": {
        "location": "Plymouth, UT",
        "type": "Bar",
        "eaf_count": 2,
        "eaf_type": "?",
        "eaf_manufacturer": "Fuchs",
        KEY_EAF_SIZE: 51,
        KEY_CYCLES_PER_DAY: 42,
        "tons_per_year": 1290000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Rocky Mountain Power",
        KEY_GRID_CAP: 15,
    },
    "Seattle": {
        "location": "Seattle, WA",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "?",
        "eaf_manufacturer": "Fuchs",
        KEY_EAF_SIZE: 100,
        KEY_CYCLES_PER_DAY: 29,
        "tons_per_year": 855000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Seattle City Light",
        KEY_GRID_CAP: 30,
    },
    "Sedalia": {
        "location": "Sedalia, MO",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "?",
        "eaf_manufacturer": "Danieli",
        KEY_EAF_SIZE: 40,
        KEY_CYCLES_PER_DAY: 39,
        "tons_per_year": 470000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Evergy",
        KEY_GRID_CAP: 12,
    },
    "Tuscaloosa": {
        "location": "Tuscaloosa, AL",
        "type": "Plate",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "MAN GHH",
        KEY_EAF_SIZE: 122,
        KEY_CYCLES_PER_DAY: 17,
        "tons_per_year": 610000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Alabama Power",
        KEY_GRID_CAP: 37,
    },
    "Florida": {
        "location": "Frostproof, FL",
        "type": "?",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Danieli",
        KEY_EAF_SIZE: 40,
        KEY_CYCLES_PER_DAY: 38,
        "tons_per_year": 450000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Duke Energy Florida",
        KEY_GRID_CAP: 12,
    },
    "Jackson": {
        "location": "Flowood, MS",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "?",
        KEY_EAF_SIZE: 50,
        KEY_CYCLES_PER_DAY: 33,
        "tons_per_year": 490000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Entergy Mississippi (Assumed)",
        KEY_GRID_CAP: 15,
    },
    "Nucor-Yamato": {
        "location": "Blytheville, AR",
        "type": "Structural (implied)",
        "eaf_count": 2,
        "eaf_type": "?",
        "eaf_manufacturer": "?",
        KEY_EAF_SIZE: 150,
        KEY_CYCLES_PER_DAY: 25,
        "tons_per_year": 2500000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Mississippi County Electric Cooperative",
        KEY_GRID_CAP: 45,
    },
    "Custom": {
        "location": "Custom Location",
        "type": "Custom",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Custom",
        KEY_EAF_SIZE: 100,
        KEY_CYCLES_PER_DAY: 24,
        "tons_per_year": 1000000,
        KEY_DAYS_PER_YEAR: 300,
        KEY_CYCLE_DURATION: 36,
        "utility": "Custom Utility",
        KEY_GRID_CAP: 35,
    },
}

# --- Utility Rate Data ---
utility_rates = {
    "Appalachian Power": {
        KEY_ENERGY_RATES: {"off_peak": 45, "mid_peak": 90, "peak": 135},
        KEY_DEMAND_CHARGE: 12,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 11, "peak"),
            (11, 16, "mid_peak"),
            (16, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [3, 4, 5, 10],
        KEY_WINTER_MULT: 1.0,
        KEY_SUMMER_MULT: 1.3,
        KEY_SHOULDER_MULT: 1.1,
    },
    "New York State Electric & Gas": {
        KEY_ENERGY_RATES: {"off_peak": 60, "mid_peak": 110, "peak": 180},
        KEY_DEMAND_CHARGE: 15,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 10, "peak"),
            (10, 17, "mid_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2, 3],
        KEY_SUMMER_MONTHS: [6, 7, 8],
        KEY_SHOULDER_MONTHS: [4, 5, 9, 10],
        KEY_WINTER_MULT: 1.2,
        KEY_SUMMER_MULT: 1.5,
        KEY_SHOULDER_MULT: 1.3,
    },
    "Alabama Power": {
        KEY_ENERGY_RATES: {"off_peak": 40, "mid_peak": 80, "peak": 120},
        KEY_DEMAND_CHARGE: 10,
        "tou_periods": [
            (0, 8, "off_peak"),
            (8, 11, "peak"),
            (11, 15, "mid_peak"),
            (15, 19, "peak"),
            (19, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [12, 1, 2],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [3, 4, 5, 10, 11],
        KEY_WINTER_MULT: 0.9,
        KEY_SUMMER_MULT: 1.4,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Entergy Arkansas": {
        KEY_ENERGY_RATES: {"off_peak": 42, "mid_peak": 85, "peak": 130},
        KEY_DEMAND_CHARGE: 11,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 10, "peak"),
            (10, 16, "mid_peak"),
            (16, 19, "peak"),
            (19, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [3, 4, 5, 10],
        KEY_WINTER_MULT: 0.9,
        KEY_SUMMER_MULT: 1.3,
        KEY_SHOULDER_MULT: 1.0,
    },
    "ComEd": {
        KEY_ENERGY_RATES: {"off_peak": 48, "mid_peak": 95, "peak": 140},
        KEY_DEMAND_CHARGE: 13,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 10, "peak"),
            (10, 17, "mid_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2, 3],
        KEY_SUMMER_MONTHS: [6, 7, 8],
        KEY_SHOULDER_MONTHS: [4, 5, 9, 10],
        KEY_WINTER_MULT: 1.1,
        KEY_SUMMER_MULT: 1.6,
        KEY_SHOULDER_MULT: 1.2,
    },
    "LG&E KU": {
        KEY_ENERGY_RATES: {"off_peak": 44, "mid_peak": 88, "peak": 125},
        KEY_DEMAND_CHARGE: 12.5,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 11, "peak"),
            (11, 17, "mid_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [3, 4, 5, 10],
        KEY_WINTER_MULT: 1.0,
        KEY_SUMMER_MULT: 1.35,
        KEY_SHOULDER_MULT: 1.1,
    },
    "Dominion Energy": {
        KEY_ENERGY_RATES: {"off_peak": 47, "mid_peak": 94, "peak": 138},
        KEY_DEMAND_CHARGE: 13.5,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 11, "peak"),
            (11, 16, "mid_peak"),
            (16, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [12, 1, 2, 3],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [4, 5, 10, 11],
        KEY_WINTER_MULT: 1.05,
        KEY_SUMMER_MULT: 1.45,
        KEY_SHOULDER_MULT: 1.15,
    },
    "Duke Energy": {
        KEY_ENERGY_RATES: {"off_peak": 46, "mid_peak": 92, "peak": 135},
        KEY_DEMAND_CHARGE: 14,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 10, "peak"),
            (10, 16, "mid_peak"),
            (16, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [3, 4, 5, 10],
        KEY_WINTER_MULT: 0.95,
        KEY_SUMMER_MULT: 1.4,
        KEY_SHOULDER_MULT: 1.1,
    },
    "Kentucky Utilities": default_utility_params.copy(),  # Placeholder
    "Mississippi County Electric Cooperative": {
        KEY_ENERGY_RATES: {"off_peak": 32.72, "mid_peak": 32.72, "peak": 32.72},
        KEY_DEMAND_CHARGE: 12.28,
        "tou_periods": [(0, 24, "off_peak")],
        KEY_SEASONAL: False,
        KEY_WINTER_MONTHS: default_utility_params[KEY_WINTER_MONTHS],
        KEY_SUMMER_MONTHS: default_utility_params[KEY_SUMMER_MONTHS],
        KEY_SHOULDER_MONTHS: default_utility_params[KEY_SHOULDER_MONTHS],
        KEY_WINTER_MULT: 1.0,
        KEY_SUMMER_MULT: 1.0,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Santee Cooper": {
        KEY_ENERGY_RATES: {"off_peak": 37.50, "mid_peak": 37.50, "peak": 57.50},
        KEY_DEMAND_CHARGE: 19.26,
        "tou_periods": [(0, 13, "off_peak"), (13, 22, "peak"), (22, 24, "off_peak")],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [1, 2, 3, 4, 5, 9, 10, 11, 12],
        KEY_SUMMER_MONTHS: [6, 7, 8],
        KEY_SHOULDER_MONTHS: [],
        KEY_WINTER_MULT: 1.0,
        KEY_SUMMER_MULT: 1.0,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Oncor Electric Delivery": default_utility_params.copy(),  # Placeholder
    "UniSource Energy Services": {
        KEY_ENERGY_RATES: {"off_peak": 52.5, "mid_peak": 52.5, "peak": 77.5},
        KEY_DEMAND_CHARGE: 16.5,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 10, "peak"),
            (10, 17, "off_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [11, 12, 1, 2, 3, 4],
        KEY_SUMMER_MONTHS: [5, 6, 7, 8, 9, 10],
        KEY_SHOULDER_MONTHS: [],
        KEY_WINTER_MULT: 0.85,
        KEY_SUMMER_MULT: 1.15,
        KEY_SHOULDER_MULT: 1.0,
    },
    "AEP Ohio": default_utility_params.copy(),  # Placeholder
    "Nebraska Public Power District": {
        KEY_ENERGY_RATES: {"off_peak": 19.3, "mid_peak": 19.3, "peak": 34.4},
        KEY_DEMAND_CHARGE: 19.0,
        "tou_periods": default_utility_params[KEY_TOU_FILLED],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [],
        KEY_WINTER_MULT: 0.9,
        KEY_SUMMER_MULT: 1.1,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Rocky Mountain Power": {
        KEY_ENERGY_RATES: {"off_peak": 24.7, "mid_peak": 24.7, "peak": 48.5},
        KEY_DEMAND_CHARGE: 15.79,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 9, "peak"),
            (9, 15, "off_peak"),
            (15, 22, "peak"),
            (22, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [],
        KEY_WINTER_MULT: 0.95,
        KEY_SUMMER_MULT: 1.05,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Seattle City Light": {
        KEY_ENERGY_RATES: {"off_peak": 55.30, "mid_peak": 55.30, "peak": 110.70},
        KEY_DEMAND_CHARGE: 5.13,
        "tou_periods": [(0, 6, "off_peak"), (6, 22, "peak"), (22, 24, "off_peak")],
        KEY_SEASONAL: False,
        KEY_WINTER_MONTHS: default_utility_params[KEY_WINTER_MONTHS],
        KEY_SUMMER_MONTHS: default_utility_params[KEY_SUMMER_MONTHS],
        KEY_SHOULDER_MONTHS: default_utility_params[KEY_SHOULDER_MONTHS],
        KEY_WINTER_MULT: 1.0,
        KEY_SUMMER_MULT: 1.0,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Evergy": {
        KEY_ENERGY_RATES: {"off_peak": 32.59, "mid_peak": 37.19, "peak": 53.91},
        KEY_DEMAND_CHARGE: 9.69,
        "tou_periods": [(0, 24, "off_peak")],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [],
        KEY_WINTER_MULT: 0.69,
        KEY_SUMMER_MULT: 1.31,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Duke Energy Florida": default_utility_params.copy(),  # Placeholder
    "Entergy Mississippi (Assumed)": {
        KEY_ENERGY_RATES: {"off_peak": 41.0, "mid_peak": 41.0, "peak": 67.0},
        KEY_DEMAND_CHARGE: 16.75,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 10, "peak"),
            (10, 12, "off_peak"),
            (12, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        KEY_SEASONAL: True,
        KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5],
        KEY_SUMMER_MONTHS: [6, 7, 8, 9],
        KEY_SHOULDER_MONTHS: [],
        KEY_WINTER_MULT: 0.84,
        KEY_SUMMER_MULT: 1.16,
        KEY_SHOULDER_MULT: 1.0,
    },
    "Custom Utility": default_utility_params.copy(),
}

# --- MACRS Depreciation Schedules (Simplified Example - Half-Year Convention) ---
MACRS_TABLES = {
    "3-Year": [0.3333, 0.4445, 0.1481, 0.0741],
    "5-Year": [0.2000, 0.3200, 0.1920, 0.1152, 0.1152, 0.0576],
    "7-Year": [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
    # Add more schedules if needed
}


# --- Helper Functions ---
def fill_tou_gaps(periods):
    """Fills gaps in TOU periods with 'off_peak' and ensures 24hr coverage."""
    if not periods:
        return [(0.0, 24.0, "off_peak")]

    clean_periods = []
    for period in periods:
        try:
            if len(period) == 3:
                start, end, rate = float(period[0]), float(period[1]), str(period[2])
                if 0 <= start < end <= 24:
                    clean_periods.append((start, end, rate))
                else:
                    print(f"Warning: Skipping invalid TOU period range: {period}")
            else:
                print(f"Warning: Skipping malformed TOU period data: {period}")
        except (ValueError, TypeError):
            print(f"Warning: Skipping invalid TOU period data: {period}")

    clean_periods.sort(key=lambda x: x[0])

    # Check for overlaps (optional warning)
    for i in range(len(clean_periods) - 1):
        if clean_periods[i][1] > clean_periods[i + 1][0]:
            print(
                f"Warning: Overlapping TOU periods: {clean_periods[i]} and {clean_periods[i+1]}."
            )

    filled_periods = []
    current_time = 0.0
    for start, end, rate in clean_periods:
        if start > current_time:
            filled_periods.append((current_time, start, "off_peak"))  # Fill gap
        filled_periods.append((start, end, rate))
        current_time = end

    if current_time < 24.0:
        filled_periods.append((current_time, 24.0, "off_peak"))  # Fill to end of day

    # Ensure at least one period exists
    if not filled_periods:
        filled_periods.append((0.0, 24.0, "off_peak"))

    return filled_periods


def get_month_season_multiplier(month, seasonal_data):
    """Gets the rate multiplier for a given month based on seasonal settings."""
    if not seasonal_data.get(KEY_SEASONAL, False):
        return 1.0
    if month in seasonal_data.get(KEY_WINTER_MONTHS, []):
        return seasonal_data.get(KEY_WINTER_MULT, 1.0)
    elif month in seasonal_data.get(KEY_SUMMER_MONTHS, []):
        return seasonal_data.get(KEY_SUMMER_MULT, 1.0)
    elif month in seasonal_data.get(KEY_SHOULDER_MONTHS, []):
        return seasonal_data.get(KEY_SHOULDER_MULT, 1.0)
    else:
        # Default if month not found in any list (shouldn't happen if lists cover all 12)
        return 1.0


def calculate_eaf_profile(time_minutes, eaf_size=100, cycle_duration=36):
    """Generates a simplified EAF power profile over a cycle."""
    if cycle_duration <= 0:
        return np.zeros_like(time_minutes)

    eaf_power = np.zeros_like(time_minutes)
    scale = (eaf_size / 100) ** 0.6 if eaf_size > 0 else 0  # Simple scaling factor

    # Reference cycle timings (fractions of duration)
    ref_duration = 28.0  # Reference duration for profile shape
    bore_in_end_frac = 3 / ref_duration
    main_melting_end_frac = 17 / ref_duration
    melting_end_frac = 20 / ref_duration

    for i, t_actual in enumerate(time_minutes):
        # Normalize time within the *actual* cycle duration
        t_norm_actual_cycle = t_actual / cycle_duration if cycle_duration > 0 else 0
        # Scale frequency of sine waves based on duration difference
        freq_scale = ref_duration / cycle_duration if cycle_duration > 0 else 1

        if t_norm_actual_cycle <= bore_in_end_frac:
            # Bore-in phase (ramp up)
            power = (
                15
                + (25 - 15)
                * (
                    t_norm_actual_cycle / bore_in_end_frac
                    if bore_in_end_frac > 0
                    else 0
                )
            ) * scale
        elif t_norm_actual_cycle <= main_melting_end_frac:
            # Main melting phase (high power with variation)
            power = (55 + 5 * np.sin(t_actual * 0.5 * freq_scale)) * scale
        elif t_norm_actual_cycle <= melting_end_frac:
            # End of melting (ramp down slightly)
            power = (
                50
                - (50 - 40)
                * (
                    (
                        (t_norm_actual_cycle - main_melting_end_frac)
                        / (melting_end_frac - main_melting_end_frac)
                    )
                    if (melting_end_frac > main_melting_end_frac)
                    else 0
                )
            ) * scale
        else:
            # Refining/Holding phase (lower power with variation)
            power = (20 + 5 * np.sin(t_actual * 0.3 * freq_scale)) * scale

        eaf_power[i] = max(0.0, power)  # Ensure non-negative power

    return eaf_power


def calculate_grid_bess_power(eaf_power, grid_cap, bess_power_max):
    """Calculates grid draw and BESS discharge needed to meet EAF load under grid cap."""
    grid_power = np.zeros_like(eaf_power)
    bess_power = np.zeros_like(eaf_power)  # Positive values indicate discharge

    # Safely convert inputs
    try:
        grid_cap_val = 0.0 if grid_cap is None else float(grid_cap)
    except (ValueError, TypeError):
        grid_cap_val = 0.0
    try:
        bess_power_max_val = 0.0 if bess_power_max is None else float(bess_power_max)
    except (ValueError, TypeError):
        bess_power_max_val = 0.0

    grid_cap_val = max(0.0, grid_cap_val)
    bess_power_max_val = max(0.0, bess_power_max_val)

    for i, p_eaf in enumerate(eaf_power):
        p_eaf = max(0.0, p_eaf)  # Ensure EAF power is non-negative

        if p_eaf > grid_cap_val:
            # Need BESS support
            required_discharge = p_eaf - grid_cap_val
            actual_discharge = min(
                required_discharge, bess_power_max_val
            )  # Limited by BESS power

            bess_power[i] = actual_discharge
            grid_power[i] = (
                p_eaf - actual_discharge
            )  # Grid supplies the rest (up to grid_cap + any shortfall)
            # Ensure grid power doesn't exceed EAF demand if BESS covers part of it
            grid_power[i] = min(grid_power[i], p_eaf)
            # Ensure grid power doesn't exceed grid cap (unless BESS couldn't cover the full excess)
            grid_power[i] = (
                max(grid_cap_val, grid_power[i])
                if required_discharge > actual_discharge
                else grid_cap_val
            )

        else:
            # Grid can handle the load
            grid_power[i] = p_eaf
            bess_power[i] = 0.0  # No discharge needed

    return grid_power, bess_power


def calculate_initial_bess_cost(bess_params):
    """Calculates the gross initial capital cost of the BESS."""
    try:
        capacity_mwh = (
            0.0
            if bess_params.get(KEY_CAPACITY) is None
            else float(bess_params.get(KEY_CAPACITY, 0))
        )
    except (ValueError, TypeError):
        capacity_mwh = 0.0
    try:
        power_mw = (
            0.0
            if bess_params.get(KEY_POWER_MAX) is None
            else float(bess_params.get(KEY_POWER_MAX, 0))
        )
    except (ValueError, TypeError):
        power_mw = 0.0

    capacity_mwh = max(0.0, capacity_mwh)
    power_mw = max(0.0, power_mw)
    capacity_kwh = capacity_mwh * 1000.0
    power_kw = power_mw * 1000.0

    # Get unit costs safely, defaulting to 0
    sb_bos_cost_unit = bess_params.get(KEY_SB_BOS_COST, 0)
    pcs_cost_unit = bess_params.get(KEY_PCS_COST, 0)
    epc_cost_unit = bess_params.get(KEY_EPC_COST, 0)
    sys_int_cost_unit = bess_params.get(KEY_SYS_INT_COST, 0)

    sb_bos_cost = sb_bos_cost_unit * capacity_kwh
    pcs_cost = pcs_cost_unit * power_kw
    epc_cost = epc_cost_unit * capacity_kwh
    sys_int_cost = sys_int_cost_unit * capacity_kwh

    return sb_bos_cost + pcs_cost + epc_cost + sys_int_cost


def create_bess_input_group(
    label,
    input_id,
    value,
    unit,
    tooltip_text=None,
    type="number",
    step=None,
    min_val=0,
    max_val=None,
    style=None,
):
    """Helper to create a consistent input row with label, input, unit, and tooltip."""
    label_content = [label]
    if tooltip_text:
        tooltip_id = f"{input_id}-tooltip"
        label_content.extend(
            [
                " ",
                html.I(
                    className="fas fa-info-circle",
                    id=tooltip_id,
                    style={"cursor": "pointer", "color": "#6c757d"},
                ),
                dbc.Tooltip(tooltip_text, target=tooltip_id, placement="right"),
            ]
        )

    row_style = style if style is not None else {}

    input_props = {
        "id": input_id,
        "type": type,
        "value": value,
        "className": "form-control form-control-sm",
        "step": step,
        "min": min_val,
    }
    if max_val is not None:
        input_props["max"] = max_val

    return dbc.Row(
        [
            dbc.Label(label_content, html_for=input_id, width=6),
            dbc.Col(dcc.Input(**input_props), width=4),
            dbc.Col(
                html.Span(unit, className="input-group-text input-group-text-sm"),
                width=2,
            ),
        ],
        className="mb-2 align-items-center",
        style=row_style,
    )


# --- New Helper Functions ---
def calculate_macrs_depreciation(depreciable_basis, schedule_name, year):
    """Calculates depreciation for a given year based on a simplified MACRS schedule."""
    schedule = MACRS_TABLES.get(schedule_name, [])
    if year > 0 and year <= len(schedule):
        return depreciable_basis * schedule[year - 1]
    return 0.0


def calculate_debt_payment(loan_amount, annual_interest_rate, loan_term_years):
    """Calculates level annual debt payment (principal + interest). Returns payment only."""
    # Note: Interest/Principal split is handled year-by-year in the main financial loop
    if loan_term_years <= 0 or loan_amount <= 0:
        return 0.0
    if annual_interest_rate == 0:  # Handle zero interest case
        return loan_amount / loan_term_years

    # Standard annuity formula for annual payment
    r = annual_interest_rate  # Already annual
    n = loan_term_years
    try:
        if r > 0:
            annual_payment = loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        else:  # Should be caught above, but as fallback
            annual_payment = loan_amount / n
        return annual_payment
    except OverflowError:
        print(
            f"Warning: OverflowError calculating PMT for rate={r}, term={n}, amount={loan_amount}. Returning 0."
        )
        return 0.0  # Avoid crashing if numbers get too large


def create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month):
    """
    Calculate the monthly electricity bill without BESS (Simplified).
    Assumes all energy charged at peak rate for simplicity in this version.
    """

    # Get parameters safely
    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    grid_cap = safe_float(eaf_params.get(KEY_GRID_CAP))
    eaf_size = safe_float(eaf_params.get(KEY_EAF_SIZE))
    cycle_duration = safe_float(eaf_params.get(KEY_CYCLE_DURATION), 36)
    cycles_per_day = safe_int(eaf_params.get(KEY_CYCLES_PER_DAY), 24)
    days_per_year = safe_int(eaf_params.get(KEY_DAYS_PER_YEAR), 300)
    days_active = min(days_in_month, days_per_year / 12.0)  # Pro-rate operating days

    # Get seasonal multiplier if applicable
    seasonal_multiplier = get_month_season_multiplier(month, utility_params)

    # Simulate one cycle to get peak demand and energy per cycle
    time_minutes = np.linspace(0, cycle_duration, 200)  # 200 steps for profile
    eaf_power = calculate_eaf_profile(time_minutes, eaf_size, cycle_duration)
    peak_demand_mw = np.max(eaf_power) if len(eaf_power) > 0 else 0.0
    # Energy per cycle in MWh: integral(Power(MW) dt) = sum(Power_i * delta_t_hours


def create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month):
    """
    Calculate the monthly electricity bill without BESS (Simplified).
    Assumes all energy charged at peak rate for simplicity in this version.
    """

    # Get parameters safely
    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    grid_cap = safe_float(eaf_params.get(KEY_GRID_CAP))
    eaf_size = safe_float(eaf_params.get(KEY_EAF_SIZE))
    cycle_duration = safe_float(eaf_params.get(KEY_CYCLE_DURATION), 36)
    cycles_per_day = safe_int(eaf_params.get(KEY_CYCLES_PER_DAY), 24)
    days_per_year = safe_int(eaf_params.get(KEY_DAYS_PER_YEAR), 300)
    days_active = min(days_in_month, days_per_year / 12.0)  # Pro-rate operating days

    # Get seasonal multiplier if applicable
    seasonal_multiplier = get_month_season_multiplier(month, utility_params)

    # Simulate one cycle to get peak demand and energy per cycle
    time_minutes = np.linspace(0, cycle_duration, 200)  # 200 steps for profile
    eaf_power = calculate_eaf_profile(time_minutes, eaf_size, cycle_duration)
    peak_demand_mw = np.max(eaf_power) if len(eaf_power) > 0 else 0.0
    # Energy per cycle in MWh: integral(Power(MW) dt) = sum(Power_i * delta_t_hours)
    delta_t_hours = (
        (cycle_duration / 60.0) / (len(time_minutes) - 1)
        if len(time_minutes) > 1
        else 0
    )
    energy_per_cycle_mwh = (
        np.sum(eaf_power) * delta_t_hours if len(eaf_power) > 0 else 0.0
    )

    # Calculate total monthly energy and peak demand
    total_energy_mwh = energy_per_cycle_mwh * cycles_per_day * days_active
    peak_demand_kw = peak_demand_mw * 1000.0  # Demand charge is usually $/kW

    # Get rates safely
    energy_rates = utility_params.get(KEY_ENERGY_RATES, {})
    # *** SIMPLIFICATION: Using peak rate for all energy ***
    # A more accurate model would use the TOU schedule and EAF profile timing.
    peak_rate_per_mwh = safe_float(energy_rates.get("peak")) * seasonal_multiplier
    demand_charge_per_kw = (
        safe_float(utility_params.get(KEY_DEMAND_CHARGE)) * seasonal_multiplier
    )

    # Calculate charges
    energy_charge = total_energy_mwh * peak_rate_per_mwh
    demand_charge = peak_demand_kw * demand_charge_per_kw

    # Total bill
    total_bill = energy_charge + demand_charge

    return {
        "total_bill": total_bill,
        "energy_charge": energy_charge,
        "demand_charge": demand_charge,
        "peak_demand_mw": peak_demand_mw,
        "total_energy_mwh": total_energy_mwh,
    }


def create_monthly_bill_with_bess(
    eaf_params, bess_params_yr_t, utility_params, days_in_month, month
):
    """
    Calculate the monthly electricity bill with BESS (Simplified).
    Uses peak shaving logic and assumes all grid energy charged at peak rate.
    """

    # Get parameters safely
    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def safe_int(val, default=0):
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    grid_cap = safe_float(eaf_params.get(KEY_GRID_CAP))
    eaf_size = safe_float(eaf_params.get(KEY_EAF_SIZE))
    cycle_duration = safe_float(eaf_params.get(KEY_CYCLE_DURATION), 36)
    cycles_per_day = safe_int(eaf_params.get(KEY_CYCLES_PER_DAY), 24)
    days_per_year = safe_int(eaf_params.get(KEY_DAYS_PER_YEAR), 300)
    days_active = min(days_in_month, days_per_year / 12.0)

    # Get BESS power limits (potentially degraded for year t)
    bess_power_max_mw = safe_float(bess_params_yr_t.get(KEY_POWER_MAX))

    # Get seasonal multiplier if applicable
    seasonal_multiplier = get_month_season_multiplier(month, utility_params)

    # Simulate one cycle to get modified demand and BESS discharge
    time_minutes = np.linspace(0, cycle_duration, 200)
    eaf_power = calculate_eaf_profile(time_minutes, eaf_size, cycle_duration)
    grid_power, bess_discharge_power = calculate_grid_bess_power(
        eaf_power, grid_cap, bess_power_max_mw
    )

    # Calculate peak demand after BESS
    peak_demand_mw = np.max(grid_power) if len(grid_power) > 0 else 0.0
    peak_demand_kw = peak_demand_mw * 1000.0

    # Calculate energy from grid and BESS discharge per cycle
    delta_t_hours = (
        (cycle_duration / 60.0) / (len(time_minutes) - 1)
        if len(time_minutes) > 1
        else 0
    )
    grid_energy_per_cycle_mwh = (
        np.sum(grid_power) * delta_t_hours if len(grid_power) > 0 else 0.0
    )
    bess_discharge_per_cycle_mwh = (
        np.sum(bess_discharge_power) * delta_t_hours
        if len(bess_discharge_power) > 0
        else 0.0
    )

    # Calculate total monthly grid energy and BESS discharge
    total_grid_energy_mwh = grid_energy_per_cycle_mwh * cycles_per_day * days_active
    total_bess_discharge_mwh = (
        bess_discharge_per_cycle_mwh * cycles_per_day * days_active
    )

    # Get rates safely
    energy_rates = utility_params.get(KEY_ENERGY_RATES, {})
    # *** SIMPLIFICATION: Using peak rate for all grid energy ***
    peak_rate_per_mwh = safe_float(energy_rates.get("peak")) * seasonal_multiplier
    demand_charge_per_kw = (
        safe_float(utility_params.get(KEY_DEMAND_CHARGE)) * seasonal_multiplier
    )

    # Calculate charges
    energy_charge = total_grid_energy_mwh * peak_rate_per_mwh
    demand_charge = peak_demand_kw * demand_charge_per_kw

    # Total bill from grid
    total_bill = energy_charge + demand_charge


    return {
        "total_bill": total_bill,
        "energy_charge": energy_charge,
        "demand_charge": demand_charge,
        "peak_demand_mw": peak_demand_mw,
        "total_grid_energy_mwh": total_grid_energy_mwh,
        "bess_discharged_total_mwh": total_bess_discharge_mwh,  # Note: This is discharge, not net energy delivered
    }
# --- Billing Calculation (Modified for Degradation & Charging) ---
def calculate_yearly_savings_discharge(
    eaf_params, bess_params_yr_t, utility_params, year_t
):
    """
    Calculates utility savings and BESS discharge for a specific year,
    considering degraded BESS parameters and basic charging costs.
    Returns: dict {'annual_savings': $, 'total_annual_discharge_mwh': MWh, 'annual_charging_cost': $}
    """
    annual_bill_with_bess = 0.0
    annual_bill_without_bess = 0.0
    total_annual_discharge_mwh = 0.0
    total_annual_charging_cost = 0.0

    # Get degraded RTE for charging calculation safely
    rte_t_percent = bess_params_yr_t.get(KEY_RTE, 85.0)
    try:
        rte_t = float(rte_t_percent) / 100.0
    except (ValueError, TypeError):
        rte_t = 0.85
    rte_t = max(0.01, min(1.0, rte_t))  # Clamp between 1% and 100%

    # Find off-peak rate for charging cost estimate (simplification)
    energy_rates = utility_params.get(KEY_ENERGY_RATES, {})
    try:
        off_peak_rate = float(energy_rates.get("off_peak", 0.0))  # $/MWh
    except (ValueError, TypeError):
        off_peak_rate = 0.0

    current_sim_year = (
        datetime.now().year + year_t - 1
    )  # Approximate year for calendar days

    for month in range(1, 13):
        try:
            days_in_month = calendar.monthrange(current_sim_year, month)[1]
        except ValueError:  # Handle potential invalid year (unlikely but safe)
            days_in_month = 30  # Default

        # Calculate baseline bill without BESS
        bill_wo = create_monthly_bill_without_bess(
            eaf_params, utility_params, days_in_month, month
        )
        annual_bill_without_bess += bill_wo.get("total_bill", 0.0)

        # Calculate bill WITH degraded BESS
        bill_w = create_monthly_bill_with_bess(
            eaf_params, bess_params_yr_t, utility_params, days_in_month, month
        )
        annual_bill_with_bess += bill_w.get("total_bill", 0.0)
        monthly_discharge_mwh = bill_w.get("bess_discharged_total_mwh", 0.0)
        total_annual_discharge_mwh += monthly_discharge_mwh

        # Estimate charging cost for the energy discharged this month
        # Assumes all charging happens off-peak (simplification)
        energy_charged_mwh = monthly_discharge_mwh / rte_t if rte_t > 0 else 0.0
        monthly_charging_cost = energy_charged_mwh * off_peak_rate  # MWh * $/MWh
        total_annual_charging_cost += monthly_charging_cost

    # Savings = Baseline Bill - (BESS Bill + Charging Cost)
    annual_savings = annual_bill_without_bess - (
        annual_bill_with_bess + total_annual_charging_cost
    )

    return {
        "annual_savings": annual_savings,
        "total_annual_discharge_mwh": total_annual_discharge_mwh,
        "annual_charging_cost": total_annual_charging_cost,
        # Pass through for reference if needed
        "annual_bill_without_bess": annual_bill_without_bess,
        "annual_bill_with_bess": annual_bill_with_bess,
    }


# --- Incentive Calculation Function ---
def calculate_incentives(bess_params, incentive_params):
    """Calculates total incentives based on selected programs and BESS cost/size."""
    total_incentive = 0.0
    incentive_breakdown = {}
    total_cost = calculate_initial_bess_cost(bess_params)

    try:
        capacity_mwh = (
            0.0
            if bess_params.get(KEY_CAPACITY) is None
            else float(bess_params.get(KEY_CAPACITY, 0))
        )
    except (ValueError, TypeError):
        capacity_mwh = 0.0
    capacity_kwh = max(0.0, capacity_mwh) * 1000.0

    # Helper to safely get incentive params
    def get_incentive_param(key, default):
        val = incentive_params.get(key, default)
        if isinstance(default, (int, float)):
            try:
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default
        elif isinstance(default, bool):
            return bool(val)
        elif isinstance(default, str):
            return str(val) if val is not None else default
        return val  # Return as is for other types (like lists)

    # Calculate individual incentives
    itc_enabled = get_incentive_param("itc_enabled", False)
    itc_perc = get_incentive_param("itc_percentage", 30) / 100.0
    itc_amount = total_cost * itc_perc if itc_enabled else 0.0

    ceic_enabled = get_incentive_param("ceic_enabled", False)
    ceic_perc = get_incentive_param("ceic_percentage", 30) / 100.0
    ceic_amount = total_cost * ceic_perc if ceic_enabled else 0.0

    bonus_enabled = get_incentive_param("bonus_credit_enabled", False)
    bonus_perc = get_incentive_param("bonus_credit_percentage", 10) / 100.0
    bonus_amount = total_cost * bonus_perc if bonus_enabled else 0.0

    sgip_enabled = get_incentive_param("sgip_enabled", False)
    sgip_rate = get_incentive_param("sgip_amount", 400)
    sgip_amount = capacity_kwh * sgip_rate if sgip_enabled else 0.0

    ess_enabled = get_incentive_param("ess_enabled", False)
    ess_rate = get_incentive_param("ess_amount", 280)
    ess_amount = capacity_kwh * ess_rate if ess_enabled else 0.0

    mabi_enabled = get_incentive_param("mabi_enabled", False)
    mabi_rate = get_incentive_param("mabi_amount", 250)
    mabi_amount = capacity_kwh * mabi_rate if mabi_enabled else 0.0

    cs_enabled = get_incentive_param("cs_enabled", False)
    cs_rate = get_incentive_param("cs_amount", 225)
    cs_amount = capacity_kwh * cs_rate if cs_enabled else 0.0

    custom_enabled = get_incentive_param("custom_incentive_enabled", False)
    custom_type = get_incentive_param("custom_incentive_type", "per_kwh")
    custom_rate = get_incentive_param("custom_incentive_amount", 100)
    custom_desc = get_incentive_param("custom_incentive_description", "Custom")
    custom_amount = 0.0
    if custom_enabled:
        if custom_type == "per_kwh":
            custom_amount = capacity_kwh * custom_rate
        elif custom_type == "percentage":
            custom_amount = total_cost * (custom_rate / 100.0)

    # Apply Federal Logic (ITC vs CEIC)
    applied_federal_base = 0.0
    federal_base_desc = ""
    if itc_enabled and ceic_enabled:
        if itc_amount >= ceic_amount:
            applied_federal_base, federal_base_desc = (
                itc_amount,
                "Investment Tax Credit (ITC)",
            )
        else:
            applied_federal_base, federal_base_desc = (
                ceic_amount,
                "Clean Electricity Investment Credit (CEIC)",
            )
    elif itc_enabled:
        applied_federal_base, federal_base_desc = (
            itc_amount,
            "Investment Tax Credit (ITC)",
        )
    elif ceic_enabled:
        applied_federal_base, federal_base_desc = (
            ceic_amount,
            "Clean Electricity Investment Credit (CEIC)",
        )

    # Sum up applied incentives
    if applied_federal_base > 0:
        total_incentive += applied_federal_base
        incentive_breakdown[federal_base_desc] = applied_federal_base
    if bonus_amount > 0:
        total_incentive += bonus_amount
        incentive_breakdown["Bonus Credits"] = bonus_amount
    if sgip_amount > 0:
        total_incentive += sgip_amount
        incentive_breakdown["CA Self-Generation Incentive Program"] = sgip_amount
    if ess_amount > 0:
        total_incentive += ess_amount
        incentive_breakdown["CT Energy Storage Solutions"] = ess_amount
    if mabi_amount > 0:
        total_incentive += mabi_amount
        incentive_breakdown["NY Market Acceleration Bridge Incentive"] = mabi_amount
    if cs_amount > 0:
        total_incentive += cs_amount
        incentive_breakdown["MA Connected Solutions"] = cs_amount
    if custom_amount > 0:
        total_incentive += custom_amount
        incentive_breakdown[custom_desc] = custom_amount

    return {
        "total_incentive": total_incentive,
        "breakdown": incentive_breakdown,
        "calculated_initial_cost": total_cost,
    }
# section 3
# --- Formatting Helper ---
def fmt_c(v, decimals=0):
    """Format a currency value with commas and specified decimal places."""
    if pd.notna(v) and isinstance(v, (int, float)) and abs(v) < 1e15:  # Avoid formatting huge numbers
        return f"${v:,.{decimals}f}"
    else:
        return "N/A"

# --- Financial Metrics Calculation (HEAVILY REVISED) ---
def calculate_financial_metrics_advanced(bess_params, financial_params, eaf_params, utility_params, incentive_results):
    """
    Calculate advanced financial metrics including Debt, Depreciation, Degradation.
    """
    detailed_cash_flows = []
    try:
        # --- Get Base Parameters & Perform Safe Conversions ---
        technology = bess_params.get(KEY_TECH, "LFP")

        # Define safe_float locally to avoid dependency on external definition
        def local_safe_float(value, default=0.0):
            if value is None: return default
            try: return float(value)
            except (ValueError, TypeError): return default

        base_capacity_mwh = max(0.001, local_safe_float(bess_params.get(KEY_CAPACITY, 0.001)))
        base_power_mw = max(0.001, local_safe_float(bess_params.get(KEY_POWER_MAX, 0.001)))
        base_rte_percent = max(1.0, local_safe_float(bess_params.get(KEY_RTE, 86.0)))
        base_capacity_kwh = base_capacity_mwh * 1000.0
        base_power_kw = base_power_mw * 1000.0

        # Financial Base Params
        years = int(local_safe_float(financial_params.get(KEY_LIFESPAN, 30), 30))
        wacc = local_safe_float(financial_params.get(KEY_WACC, 0.131), 0.131)
        inflation_rate = local_safe_float(financial_params.get(KEY_INFLATION, 0.024), 0.024)
        tax_rate = local_safe_float(financial_params.get(KEY_TAX_RATE, 0.2009), 0.2009)
        ancillary_revenue_yr1 = local_safe_float(financial_params.get(KEY_ANCILLARY_REVENUE, 0.0), 0.0)
        years = max(1, years)

        # Debt Params
        debt_params = financial_params.get(KEY_DEBT_PARAMS, {})
        loan_percent = local_safe_float(debt_params.get(KEY_LOAN_PERCENT, 0.0), 0.0) / 100.0
        loan_interest = local_safe_float(debt_params.get(KEY_LOAN_INTEREST, 0.0), 0.0)
        loan_term = int(local_safe_float(debt_params.get(KEY_LOAN_TERM, 0), 0))

        # Depreciation Params
        deprec_params = financial_params.get(KEY_DEPREC_PARAMS, {})
        macrs_schedule_name = deprec_params.get(KEY_MACRS_SCHEDULE, '5-Year')

        # Degradation Params
        degrad_params = financial_params.get(KEY_DEGRAD_PARAMS, {})
        degrad_cap_yr = local_safe_float(degrad_params.get(KEY_DEGRAD_CAP_YR, 0.0), 0.0) / 100.0
        degrad_rte_yr = local_safe_float(degrad_params.get(KEY_DEGRAD_RTE_YR, 0.0), 0.0) / 100.0
        repl_thresh_percent = local_safe_float(degrad_params.get(KEY_REPL_THRESH, 70.0), 70.0)

        # BESS Performance Params (Base)
        base_cycle_life = local_safe_float(bess_params.get(KEY_CYCLE_LIFE, 5000), 5000)
        base_calendar_life = local_safe_float(bess_params.get(KEY_CALENDAR_LIFE, 15), 15)
        base_cycle_life = max(1.0, base_cycle_life)
        base_calendar_life = max(1.0, base_calendar_life)

        # --- Initial Calculations ---
        total_initial_cost = calculate_initial_bess_cost(bess_params)
        total_incentive = incentive_results.get("total_incentive", 0.0)

        # Depreciable Basis (Simplified: Initial Cost - 50% of ITC if taken)
        # Note: Real tax rules are complex. Consult a tax professional.
        itc_taken = incentive_results.get("breakdown", {}).get("Investment Tax Credit (ITC)", 0.0)
        depreciable_basis = total_initial_cost - (0.5 * itc_taken if itc_taken > 0 else 0.0)

        # Loan Amount & Equity
        loan_amount = total_initial_cost * loan_percent
        equity_investment = total_initial_cost - loan_amount - total_incentive  # Equity needed after loan and incentives

        # Initial O&M Cost (Year 1 - Base)
        fixed_om_per_kw_yr = local_safe_float(bess_params.get(KEY_FIXED_OM, 0.0), 0.0)
        om_cost_per_kwh_yr = local_safe_float(bess_params.get(KEY_OM_KWHR_YR, 0.0), 0.0)
        insurance_percent_yr = local_safe_float(bess_params.get(KEY_INSURANCE, 0.0), 0.0)

        om_base_cost = 0.0
        # Use the value from the *relevant* O&M input based on the technology template
        tech_template = bess_technology_data.get(technology, {})
        if KEY_OM_KWHR_YR in tech_template and om_cost_per_kwh_yr > 0:  # Check if this key exists AND has a value in the template
             om_base_cost = om_cost_per_kwh_yr * base_capacity_kwh
        elif KEY_FIXED_OM in tech_template and fixed_om_per_kw_yr > 0:  # Check if this key exists AND has a value
             om_base_cost = fixed_om_per_kw_yr * base_power_kw
        else:  # Fallback if template is missing O&M keys or values are zero
             om_base_cost = (fixed_om_per_kw_yr * base_power_kw) + (om_cost_per_kwh_yr * base_capacity_kwh)  # Sum both if unsure

        insurance_cost_yr1 = (insurance_percent_yr / 100.0) * total_initial_cost
        total_initial_om_cost = om_base_cost + insurance_cost_yr1

        # Decommissioning Base Cost
        disconnect_cost_per_kwh = local_safe_float(bess_params.get(KEY_DISCONNECT_COST, 0.0), 0.0)
        recycling_cost_per_kwh = local_safe_float(bess_params.get(KEY_RECYCLING_COST, 0.0), 0.0)
        decomm_cost_base = (disconnect_cost_per_kwh + recycling_cost_per_kwh) * base_capacity_kwh

        # --- Initialize Loop Variables ---
        project_cash_flows = [-total_initial_cost + total_incentive]  # Project CF: Start with net cost before loan
        equity_cash_flows = [-equity_investment]  # Equity CF: Start with equity invested
        discounted_costs_lcos = [total_initial_cost]  # For LCOS (Year 0 cost)
        discounted_discharge_lcos = [0.0]  # For LCOS (No discharge in Year 0)
        remaining_loan_balance = loan_amount
        current_capacity_mwh = base_capacity_mwh
        current_rte_percent = base_rte_percent
        cumulative_cycles = 0.0
        battery_age_years = 0
        replacement_scheduled_this_year = False  # Flag to prevent multiple replacements in one year trigger

        # --- Cash Flow Calculation Loop ---
        for year in range(1, years + 1):
            inflation_factor = (1 + inflation_rate) ** (year - 1)

            # 1. Degradation
            # Apply degradation BEFORE calculating savings for the year
            # Linear degradation model
            capacity_degradation_factor = max(0, 1.0 - (degrad_cap_yr * battery_age_years))
            rte_degradation_factor = max(0, 1.0 - (degrad_rte_yr * battery_age_years))
            current_capacity_mwh = base_capacity_mwh * capacity_degradation_factor
            current_rte_percent = base_rte_percent * rte_degradation_factor
            current_power_mw = base_power_mw  # Assume power doesn't degrade (simplification)

            # Create degraded BESS params for billing calc
            bess_params_t = bess_params.copy()
            bess_params_t[KEY_CAPACITY] = current_capacity_mwh
            bess_params_t[KEY_POWER_MAX] = current_power_mw  # Could degrade power too if needed
            bess_params_t[KEY_RTE] = current_rte_percent

            # 2. Calculate Annual Savings & Discharge for this year (using degraded params)
            # This now includes charging costs internally
            billing_results_t = calculate_yearly_savings_discharge(eaf_params, bess_params_t, utility_params, year)
            savings_t = billing_results_t.get('annual_savings', 0.0)  # Net savings after charging costs
            annual_discharge_t = billing_results_t.get('total_annual_discharge_mwh', 0.0)

            # Update cumulative cycles (approximation based on annual discharge)
            # Assumes full DoD cycles for simplicity; real cycle counting is complex
            dod_fraction = local_safe_float(bess_params.get(KEY_DOD, 100.0), 100.0) / 100.0
            dod_fraction = max(0.01, min(1.0, dod_fraction))  # Ensure DoD is valid
            equiv_cycles_t = (annual_discharge_t / (base_capacity_mwh * dod_fraction)) if (base_capacity_mwh * dod_fraction) > 0 else 0.0
            cumulative_cycles += equiv_cycles_t
            #secton 4
            # 3. Check Replacement Need (End of Year Check)
            replacement_cost_year_gross = 0.0
            trigger_repl = False
            # Check thresholds *before* incrementing age for the year just completed
            if battery_age_years >= base_calendar_life:
                trigger_repl = True
            if cumulative_cycles >= base_cycle_life:
                trigger_repl = True
            if base_capacity_mwh > 0:
                capacity_percentage = (current_capacity_mwh / base_capacity_mwh * 100.0)
                if capacity_percentage < repl_thresh_percent:
                    trigger_repl = True

            if trigger_repl and not replacement_scheduled_this_year:
                inflated_replacement_cost = total_initial_cost * inflation_factor
                replacement_cost_year_gross = inflated_replacement_cost
                # Reset degradation & cycle counters for the *next* year's calculation
                battery_age_years = 0  # Reset age after replacement
                cumulative_cycles = 0.0  # Reset cycles after replacement
                replacement_scheduled_this_year = True  # Flag that replacement happened this year
            else:
                battery_age_years += 1  # Increment age if no replacement
                replacement_scheduled_this_year = False  # Reset flag for next year

            # 4. O&M Cost
            o_m_cost_t = total_initial_om_cost * inflation_factor

            # 5. Ancillary Revenue
            ancillary_revenue_t = ancillary_revenue_yr1 * inflation_factor

            # 6. Debt Service (Calculate Interest & Principal for the year)
            interest_payment_t = 0.0
            principal_payment_t = 0.0
            annual_debt_payment = 0.0
            if remaining_loan_balance > 0 and year <= loan_term and loan_term > 0:
                # Calculate interest for the current year based on remaining balance
                interest_payment_t = remaining_loan_balance * loan_interest

                # Calculate the level payment based on the *original* loan parameters
                # Use helper function or npf.pmt if available
                try:
                    # Use npf.pmt for accurate level payment calculation
                    original_loan_payment = npf.pmt(loan_interest, loan_term, loan_amount) * -1 if loan_term > 0 else 0
                except Exception as pmt_err:
                    # Fallback if npf.pmt fails (e.g., not installed or calculation issue)
                    original_loan_payment = calculate_debt_payment(loan_amount, loan_interest, loan_term)

                # Principal is the remainder of the level payment, capped by remaining balance + interest
                principal_payment_t = original_loan_payment - interest_payment_t
                principal_payment_t = max(0, principal_payment_t)  # Ensure principal isn't negative if interest > payment
                principal_payment_t = min(principal_payment_t, remaining_loan_balance)  # Cap principal at remaining balance

                # The actual payment this year is Interest + Capped Principal
                annual_debt_payment = interest_payment_t + principal_payment_t

                # Update remaining balance
                remaining_loan_balance -= principal_payment_t
                # Ensure balance doesn't go below zero due to float issues
                if remaining_loan_balance < 0.01: remaining_loan_balance = 0.0

            # 7. Depreciation
            depreciation_t = calculate_macrs_depreciation(depreciable_basis, macrs_schedule_name, year)

            # 8. Decommissioning Cost (Gross) - Occurs only in the final year
            decommissioning_cost_gross = 0.0
            if year == years:
                decommissioning_cost_gross = decomm_cost_base * inflation_factor

            # 9. Taxes
            taxable_income = savings_t + ancillary_revenue_t - o_m_cost_t - interest_payment_t - depreciation_t
            taxes = max(0, taxable_income * tax_rate)  # Apply tax rate, floor at 0

            # 10. Calculate Cash Flows
            # Project Cash Flow (CF before financing effects like interest/principal)
            ebit = savings_t + ancillary_revenue_t - o_m_cost_t - depreciation_t
            nopat = ebit * (1.0 - tax_rate)
            project_cf_t = nopat + depreciation_t - replacement_cost_year_gross - decommissioning_cost_gross
            project_cash_flows.append(project_cf_t)

            # Equity Cash Flow = (Savings + Ancillary - O&M - Interest)*(1-Tax) + (Deprec*Tax) - Principal - Repl - Decomm
            equity_cf_t = (savings_t + ancillary_revenue_t - o_m_cost_t - interest_payment_t) * (1.0 - tax_rate) \
                          + (depreciation_t * tax_rate) \
                          - principal_payment_t \
                          - replacement_cost_year_gross \
                          - decommissioning_cost_gross
            equity_cash_flows.append(equity_cf_t)

            # 11. LCOS Components
            # Total Gross Costs = O&M + Replacement + Decommissioning + Charging Costs
            total_gross_costs_t = o_m_cost_t + replacement_cost_year_gross + decommissioning_cost_gross + billing_results_t.get('annual_charging_cost', 0.0)
            discounted_costs_lcos.append(total_gross_costs_t / ((1 + wacc) ** year))
            discounted_discharge_lcos.append(annual_discharge_t / ((1 + wacc) ** year))

            # 12. Detailed Table Data
            detailed_cash_flows.append({
                "Year": year,
                "Gross Savings (Before Charging)": savings_t + billing_results_t.get('annual_charging_cost', 0.0),  # Show savings before charging cost
                "Charging Cost": billing_results_t.get('annual_charging_cost', 0.0),
                "Net Savings": savings_t,
                "Ancillary Revenue": ancillary_revenue_t,
                "O&M Cost": o_m_cost_t,
                "Interest Payment": interest_payment_t,
                "Principal Payment": principal_payment_t,
                "Depreciation": depreciation_t,
                "Replacement Cost": replacement_cost_year_gross,
                "Decommissioning Cost": decommissioning_cost_gross,
                "Taxable Income": taxable_income,
                "Taxes": taxes,
                "Project Net Cash Flow": project_cf_t,
                "Equity Net Cash Flow": equity_cf_t,
                "Cumulative Equity Cash Flow": sum(equity_cash_flows),  # Recalculate cumulative CF
                "Remaining Loan Balance": remaining_loan_balance,
                "BESS Capacity (%)": (current_capacity_mwh / base_capacity_mwh * 100.0) if base_capacity_mwh > 0 else 0.0,
            })

        # --- Calculate Final Metrics ---
        project_npv = npf.npv(wacc, project_cash_flows) if wacc > -1 else float('nan')
        project_irr = npf.irr(project_cash_flows) if project_cash_flows and project_cash_flows[0] < 0 and any(cf > 0 for cf in project_cash_flows[1:]) else float('nan')
        equity_npv = npf.npv(wacc, equity_cash_flows) if wacc > -1 else float('nan')  # Discount equity CFs at WACC (or cost of equity if known)
        equity_irr = npf.irr(equity_cash_flows) if equity_cash_flows and equity_cash_flows[0] < 0 and any(cf > 0 for cf in equity_cash_flows[1:]) else float('nan')

        # Payback Period (based on Equity Cash Flow)
        cumulative_equity_cf = 0.0
        payback_years = float('inf')
        if equity_cash_flows:
            initial_investment = equity_cash_flows[0]
            if initial_investment >= 0:  # Payback is immediate if no investment or positive CF in year 0
                payback_years = 0.0
            else:
                cumulative_equity_cf = initial_investment
                for yr_pbk in range(1, len(equity_cash_flows)):
                    cf_yr = equity_cash_flows[yr_pbk]
                    if cumulative_equity_cf + cf_yr >= 0 and cf_yr > 0:  # Check if CF crosses zero and is positive
                        fraction = abs(cumulative_equity_cf) / cf_yr
                        payback_years = (yr_pbk - 1) + fraction
                        break
                    cumulative_equity_cf += cf_yr
                    if yr_pbk == len(equity_cash_flows) - 1 and cumulative_equity_cf < 0:
                         payback_years = float('inf')  # Never pays back if still negative at the end

        # LCOS Calculation
        lcos = float('nan')
        total_discounted_costs = sum(discounted_costs_lcos)
        total_discounted_discharge_mwh = sum(discounted_discharge_lcos)
        if total_discounted_discharge_mwh > 0:
            lcos = total_discounted_costs / total_discounted_discharge_mwh

        # DSCR (Debt Service Coverage Ratio) - Average or Minimum over loan term
        dscr_values = []
        for row in detailed_cash_flows:  # Iterates Year 1 onwards
            if row['Year'] > loan_term: continue  # Only consider years during the loan term
            debt_service = row['Interest Payment'] + row['Principal Payment']
            if debt_service <= 0: continue  # Skip years with no debt service

            # CFADS (Cash Flow Available for Debt Service)
            cfads_proxy = (row['Net Savings'] + row['Ancillary Revenue'] - row['O&M Cost'] - row['Depreciation']) * (1 - tax_rate) \
                          + row['Depreciation'] \
                          - row['Replacement Cost']  # Subtract replacement cost as a proxy for capex needed before debt service

            dscr_values.append(cfads_proxy / debt_service)

        avg_dscr = np.mean(dscr_values) if dscr_values else float('nan')
        min_dscr = np.min(dscr_values) if dscr_values else float('nan')

        # Estimate Yr 1 discharge - Get it directly from the detailed cash flow for Year 1
        total_annual_discharge_mwh_yr1 = 0.0
        if detailed_cash_flows:
            # Re-calculate discharge for year 1 using the billing function
            billing_yr1 = calculate_yearly_savings_discharge(eaf_params, bess_params, utility_params, 1)  # Use non-degraded params for year 1
            total_annual_discharge_mwh_yr1 = billing_yr1.get('total_annual_discharge_mwh', 0.0)

        return {
            "project_npv": project_npv, "project_irr": project_irr,
            "equity_npv": equity_npv, "equity_irr": equity_irr,
            "payback_years": payback_years, "lcos": lcos,
            "avg_dscr": avg_dscr, "min_dscr": min_dscr,
            "project_cash_flows": project_cash_flows,  # For plots
            "equity_cash_flows": equity_cash_flows,  # For plots
            "detailed_cash_flows": detailed_cash_flows,  # For table
            "net_initial_cost": total_initial_cost - total_incentive,  # Net cost before loan
            "total_initial_cost": total_initial_cost,
            "equity_investment": equity_investment,
            "initial_om_cost_year1": total_initial_om_cost,
            "total_annual_discharge_mwh_yr1": total_annual_discharge_mwh_yr1,
            }

    except Exception as e:
        print(f"Error in ADVANCED financial metrics calculation: {e}")
        traceback.print_exc()
        return {  # Return default structure on error
            "project_npv": float('nan'), "project_irr": float('nan'), "equity_npv": float('nan'), "equity_irr": float('nan'),
            "payback_years": float('inf'), "lcos": float('nan'), "avg_dscr": float('nan'), "min_dscr": float('nan'),
            "project_cash_flows": [], "equity_cash_flows": [], "detailed_cash_flows": [],
            "net_initial_cost": 0, "total_initial_cost": 0, "equity_investment": 0,
            "initial_om_cost_year1": 0, "total_annual_discharge_mwh_yr1": 0,
        }
# section 5
# --- Optimization Function (Uses Advanced Metrics) ---
def optimize_battery_size_advanced(eaf_params, utility_params, financial_params, incentive_params, bess_base_params):
    """Find optimal battery size using advanced metrics (Equity IRR or Project NPV)."""
    technology = bess_base_params.get(KEY_TECH, "LFP")
    capacity_options = np.linspace(5, 100, 5)  # Reduced steps for performance
    power_options = np.linspace(2, 50, 5)      # Reduced steps for performance
    best_metric_val = -float('inf')
    metric_to_optimize = "equity_irr"  # or "project_npv"
    best_capacity = None
    best_power = None
    best_metrics = None
    optimization_results = []
    count = 0
    total_combinations = len(capacity_options) * len(power_options)

    for capacity in capacity_options:
        for power in power_options:
            count += 1
            # Create a *complete* set of parameters for this test case
            # Start with the base parameters provided (which should be complete)
            test_bess_params = bess_base_params.copy()
            # Override capacity and power for this iteration
            test_bess_params[KEY_CAPACITY] = capacity
            test_bess_params[KEY_POWER_MAX] = power
            # Ensure it's complete using the helper
            test_bess_params = ensure_bess_params_complete(test_bess_params)

            try:
                # Need to run the full advanced calculation for each combo
                incentive_results = calculate_incentives(test_bess_params, incentive_params)
                metrics = calculate_financial_metrics_advanced(test_bess_params, financial_params, eaf_params, utility_params, incentive_results)

                current_metric = metrics.get(metric_to_optimize, float('nan'))
                current_result = {
                    "capacity": capacity, "power": power,
                    metric_to_optimize: current_metric,  # Store the optimized metric
                    "project_npv": metrics.get("project_npv", float('nan')),
                    "equity_irr": metrics.get("equity_irr", float('nan')),
                    "payback_years": metrics.get("payback_years", float('inf')),
                    "lcos": metrics.get("lcos", float('nan')),
                    "equity_investment": metrics.get("equity_investment", 0),
                }
                optimization_results.append(current_result)

                # Check if this is the best result so far (handle NaN)
                if pd.notna(current_metric) and current_metric > best_metric_val:
                    best_metric_val = current_metric
                    best_capacity = capacity
                    best_power = power
                    best_metrics = metrics  # Store full metrics

            except Exception as e:
                print(f"Error during optimization step (Cap={capacity:.1f}, Pow={power:.1f}): {e}")
                optimization_results.append({"capacity": capacity, "power": power, metric_to_optimize: float('nan'), "error": str(e)})


    return {
        "best_capacity": best_capacity, "best_power": best_power, f"best_{metric_to_optimize}": best_metric_val,
        "best_metrics": best_metrics, "all_results": optimization_results, "optimized_metric": metric_to_optimize
    }
# Section 6
# --- Technology Comparison Table ---
def create_technology_comparison_table(current_tech, capacity_mwh, power_mw):
    """Creates a Dash DataTable comparing key metrics across different BESS technologies."""

    def fmt_c(v):
        return f"${v:,.0f}" if pd.notna(v) and abs(v) < 1e15 else "N/A"

    techs_to_compare = list(bess_technology_data.keys())
    # Ensure current tech is in the list if it's custom or somehow missing
    if current_tech not in techs_to_compare and current_tech:
        techs_to_compare.append(current_tech)

    comp_data = []
    try:
        safe_capacity_mwh = 0.0 if capacity_mwh is None else float(capacity_mwh)
    except (ValueError, TypeError):
        safe_capacity_mwh = 0.0
    try:
        safe_power_mw = 0.0 if power_mw is None else float(power_mw)
    except (ValueError, TypeError):
        safe_power_mw = 0.0

    safe_capacity_mwh = max(0.0, safe_capacity_mwh)
    safe_power_mw = max(0.0, safe_power_mw)
    capacity_kwh = safe_capacity_mwh * 1000.0
    power_kw = safe_power_mw * 1000.0

    for tech in techs_to_compare:
        if tech not in bess_technology_data:
            continue  # Skip if data is missing
        tech_data = bess_technology_data[tech]
        try:
            # Calculate costs safely
            sb_bos_cost_unit = tech_data.get(KEY_SB_BOS_COST, 0)
            pcs_cost_unit = tech_data.get(KEY_PCS_COST, 0)
            epc_cost_unit = tech_data.get(KEY_EPC_COST, 0)
            sys_int_cost_unit = tech_data.get(KEY_SYS_INT_COST, 0)

            sb_bos_cost = sb_bos_cost_unit * capacity_kwh
            pcs_cost = pcs_cost_unit * power_kw
            epc_cost = epc_cost_unit * capacity_kwh
            sys_int_cost = sys_int_cost_unit * capacity_kwh
            total_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost

            # Calculate Annual O&M based on the correct key for the technology
            annual_om = 0.0
            fixed_om_unit = tech_data.get(KEY_FIXED_OM, 0)
            om_kwhyr_unit = tech_data.get(KEY_OM_KWHR_YR, 0)

            if KEY_OM_KWHR_YR in tech_data and om_kwhyr_unit > 0:
                annual_om = om_kwhyr_unit * capacity_kwh
            elif KEY_FIXED_OM in tech_data and fixed_om_unit > 0:
                annual_om = fixed_om_unit * power_kw
            else:  # Fallback
                annual_om = (fixed_om_unit * power_kw) + (om_kwhyr_unit * capacity_kwh)

            # Unit costs
            energy_cost_per_kwh = sb_bos_cost_unit + epc_cost_unit + sys_int_cost_unit
            power_cost_per_kw = pcs_cost_unit

            # Performance metrics
            cycle_life = tech_data.get(KEY_CYCLE_LIFE, 0)
            calendar_life = tech_data.get(KEY_CALENDAR_LIFE, 0)
            rte = tech_data.get(KEY_RTE, 0)

        except Exception as e:
            print(f"Error calculating comparison row for {tech}: {e}")
            total_cost, annual_om, energy_cost_per_kwh, power_cost_per_kw = 0, 0, 0, 0
            cycle_life, calendar_life, rte = 0, 0, 0

        row = {
            "Technology": tech + (" (Current)" if tech == current_tech else ""),
            "Cycle Life": f"{cycle_life:,}",
            "Calendar Life (yrs)": f"{calendar_life:.1f}",
            "RTE (%)": f"{rte:.1f}",
            "Capital Cost": fmt_c(total_cost),
            "Annual O&M (Yr 1)": fmt_c(annual_om),
            "Unit Energy Cost ($/kWh)": f"${energy_cost_per_kwh:.0f}",
            "Unit Power Cost ($/kW)": f"${power_cost_per_kw:.0f}",
        }
        comp_data.append(row)

    if not comp_data:
        return html.Div("No technology data available.")

    return dash_table.DataTable(
        data=comp_data,
        columns=[{"name": i, "id": i} for i in comp_data[0].keys()],
        style_cell={
            "textAlign": "center",
            "padding": "5px",
            "whiteSpace": "normal",
            "height": "auto",
        },  # Allow wrapping
        style_header={
            "fontWeight": "bold",
            "backgroundColor": "#f0f0f0",
            "textAlign": "center",
        },
        style_cell_conditional=[
            {
                "if": {"column_id": "Technology"},
                "textAlign": "left",
                "fontWeight": "bold",
            },
            {
                "if": {"filter_query": '{Technology} contains "Current"'},
                "backgroundColor": "#e6f7ff",
            },
        ],
        style_table={"overflowX": "auto"},
    )


# TOU UI Management Helper
def generate_tou_ui_elements(tou_periods_list):
    """Generates the UI rows for TOU period inputs."""
    tou_elements = []
    if not tou_periods_list:
        tou_periods_list = [(0.0, 24.0, "off_peak")]  # Default if empty

    for i, period_data in enumerate(tou_periods_list):
        # Ensure period_data is valid tuple/list
        if isinstance(period_data, (list, tuple)) and len(period_data) == 3:
            start, end, rate_type = period_data
        else:
            start, end, rate_type = (0.0, 0.0, "off_peak")  # Fallback for invalid data

        tou_row = html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            dcc.Input(
                                id={"type": "tou-start", "index": i},
                                type="number",
                                min=0,
                                max=24,
                                step=0.1,
                                value=start,
                                className="form-control form-control-sm",
                                placeholder="Start Hr (0-24)",
                            ),
                            className="col-3",
                        ),
                        html.Div(
                            dcc.Input(
                                id={"type": "tou-end", "index": i},
                                type="number",
                                min=0,
                                max=24,
                                step=0.1,
                                value=end,
                                className="form-control form-control-sm",
                                placeholder="End Hr (0-24)",
                            ),
                            className="col-3",
                        ),
                        html.Div(
                            dcc.Dropdown(
                                id={"type": "tou-rate", "index": i},
                                options=[
                                    {"label": "Off-Peak", "value": "off_peak"},
                                    {"label": "Mid-Peak", "value": "mid_peak"},
                                    {"label": "Peak", "value": "peak"},
                                ],
                                value=rate_type,
                                clearable=False,
                                className="form-select form-select-sm",
                            ),
                            className="col-4",
                        ),
                        html.Div(
                            dbc.Button(
                                "×",
                                id={"type": "remove-tou", "index": i},
                                color="danger",
                                size="sm",
                                title="Remove Period",
                                style={"lineHeight": "1"},
                                disabled=len(tou_periods_list) <= 1,
                            ),
                            className="col-2 d-flex align-items-center justify-content-center",
                        ),
                    ],
                    className="row g-1 mb-1 align-items-center",
                ),
            ],
            id=f"tou-row-{i}",
            className="tou-period-row",
        )
        tou_elements.append(tou_row)
    return tou_elements
# Section 7
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
    dcc.Store(id=STORE_LOADED_STATE, data=None),  # Trigger for updates after load

    dbc.Row([
        dbc.Col(html.H1("Advanced Battery Profitability Tool", className="text-center"), width=10),
        dbc.Col([  # Save/Load Buttons
            dcc.Upload(
                id=ID_LOAD_PROJECT_UPLOAD,
                children=dbc.Button("Load Project", outline=True, color="secondary", size="sm", className="me-2"),
                multiple=False,
                accept=".json"  # Specify accepted file type
            ),
            dbc.Button("Save Project", id=ID_SAVE_PROJECT_BTN, outline=True, color="secondary", size="sm"),
            dcc.Download(id=ID_DOWNLOAD_PROJECT_JSON),
        ], width=2, className="d-flex justify-content-end align-items-center")
    ], className="mb-4 align-items-center"),

    # Error Containers
    dbc.Alert(id=ID_VALIDATION_ERR, color="danger", is_open=False, dismissable=True, style={"max-width": "90%", "margin": "10px auto"}),
    dbc.Alert(id=ID_CALCULATION_ERR, color="warning", is_open=False, dismissable=True, style={"max-width": "90%", "margin": "10px auto"}),

    # Tabs
    dbc.Tabs(id=ID_MAIN_TABS, active_tab="tab-mill", children=[
        # Mill Selection Tab
        dbc.Tab(label="1. Mill Selection", tab_id="tab-mill", children=[
             dbc.Container(children=[
                html.H3("Select Nucor Mill", className="mb-3"),
                html.P("Choose a mill to pre-fill parameters, or select 'Custom' to enter values manually.", className="text-muted mb-4"),
                html.Div([
                    html.Label("Mill Selection:", className="form-label"),
                    dcc.Dropdown(
                        id=ID_MILL_DROPDOWN,
                        options=[{"label": f"Nucor Steel {mill}", "value": mill} for mill in nucor_mills.keys()],
                        value="Custom",
                        clearable=False,
                        className="form-select mb-3"
                    ),
                ], className="mb-4"),
                dbc.Card(id=ID_MILL_INFO_CARD, className="mb-4"),
                html.Div(dbc.Button("Continue to Parameters", id=ID_CONTINUE_PARAMS_BTN, n_clicks=0, color="primary", className="mt-3"), className="d-flex justify-content-center"),
            ], className="mt-4")
        ]),  # End Tab 1

        # Parameters Tab (with Accordion)
        dbc.Tab(label="2. System Parameters", tab_id="tab-params", children=[
             dbc.Container(children=[
                html.H3("System Parameters", className="my-4 text-center"),
                dbc.Accordion(id=ID_PARAM_ACCORDION, start_collapsed=False, always_open=True, children=[
                    # --- Utility Accordion Item ---
                    dbc.AccordionItem(title="Utility Rates & TOU", children=[
                        dbc.Card(className="p-3", children=[
                            html.Div([
                                html.Label("Utility Provider:", className="form-label"),
                                dcc.Dropdown(
                                    id=ID_UTILITY_DROPDOWN,
                                    options=[{"label": utility, "value": utility} for utility in utility_rates.keys()],
                                    value="Custom Utility",
                                    clearable=False,
                                    className="form-select mb-3"
                                ),
                            ], className="mb-3"),
                            dbc.Row([
                                dbc.Col([html.Label("Off-Peak Rate ($/MWh):"), dcc.Input(id=ID_OFF_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["off_peak"], min=0, className="form-control form-control-sm")], md=4),
                                dbc.Col([html.Label("Mid-Peak Rate ($/MWh):"), dcc.Input(id=ID_MID_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["mid_peak"], min=0, className="form-control form-control-sm")], md=4),
                                dbc.Col([html.Label("Peak Rate ($/MWh):"), dcc.Input(id=ID_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["peak"], min=0, className="form-control form-control-sm")], md=4),
                            ], className="mb-2"),
                            html.Div([html.Label("Demand Charge ($/kW/month):"), dcc.Input(id=ID_DEMAND_CHARGE, type="number", value=default_utility_params[KEY_DEMAND_CHARGE], min=0, className="form-control form-control-sm")], className="mb-3"),
                            dbc.Checklist(
                                id=ID_SEASONAL_TOGGLE,
                                options=[{"label": "Enable Seasonal Rate Variations", "value": "enabled"}],
                                value=(["enabled"] if default_utility_params[KEY_SEASONAL] else []),
                                switch=True,
                                className="mb-2"
                            ),
                            # Container for seasonal inputs
                            html.Div(id=ID_SEASONAL_CONTAINER, className="mb-3 border p-2 rounded"),
                            html.H6("Time-of-Use Periods", className="mt-3 mb-1"),
                            html.P("Define periods covering 24 hours. Gaps filled with Off-Peak.", className="small text-muted"),
                            html.Div(
                                id=ID_TOU_CONTAINER,
                                children=generate_tou_ui_elements(
                                    default_utility_params.get(KEY_TOU_RAW, [(0.0, 24.0, "off_peak")])
                                )
                            ),
                            dbc.Button("Add TOU Period", id=ID_ADD_TOU_BTN, n_clicks=0, size="sm", outline=True, color="success", className="mt-2"),
                        ])
                    ]),
                    # --- EAF Accordion Item ---
                    dbc.AccordionItem(title="EAF Parameters", children=[
                        dbc.Card(className="p-3", children=[
                            dbc.Row([
                                dbc.Col([html.Label("EAF Size (tons):"), dcc.Input(id=ID_EAF_SIZE, type="number", value=nucor_mills["Custom"][KEY_EAF_SIZE], min=1, className="form-control form-control-sm")], md=4),
                                dbc.Col([html.Label("Number of EAFs:"), dcc.Input(id=ID_EAF_COUNT, type="number", value=nucor_mills["Custom"]["eaf_count"], min=1, className="form-control form-control-sm")], md=4),
                                dbc.Col([html.Label("Grid Power Limit (MW):"), dcc.Input(id=ID_GRID_CAP, type="number", value=nucor_mills["Custom"][KEY_GRID_CAP], min=1, className="form-control form-control-sm")], md=4),
                            ], className="mb-2"),
                             dbc.Row([
                                dbc.Col([html.Label("EAF Cycles per Day:"), dcc.Input(id=ID_CYCLES_PER_DAY, type="number", value=nucor_mills["Custom"][KEY_CYCLES_PER_DAY], min=1, className="form-control form-control-sm")], md=4),
                                dbc.Col([html.Label("Avg. Cycle Duration (min):"), dcc.Input(id=ID_CYCLE_DURATION, type="number", value=nucor_mills["Custom"][KEY_CYCLE_DURATION], min=1, className="form-control form-control-sm")], md=4),
                                dbc.Col([html.Label("Operating Days per Year:"), dcc.Input(id=ID_DAYS_PER_YEAR, type="number", value=nucor_mills["Custom"][KEY_DAYS_PER_YEAR], min=1, max=366, className="form-control form-control-sm")], md=4),
                            ], className="mb-2"),
                        ])
                    ]),
                    # --- BESS Accordion Item ---
                    dbc.AccordionItem(title="BESS Parameters", children=[
                        dbc.Card(className="p-3", children=[
                            dbc.Row([
                                dbc.Col(create_bess_input_group("Total Energy Capacity:", ID_BESS_CAPACITY, default_bess_params_store[KEY_CAPACITY], "MWh", tooltip_text="Total energy the BESS can store."), md=6),
                                dbc.Col(create_bess_input_group("Total Power Rating:", ID_BESS_POWER, default_bess_params_store[KEY_POWER_MAX], "MW", min_val=0.1, tooltip_text="Maximum rate of charge/discharge."), md=6),
                            ]),
                            html.Div(id=ID_BESS_C_RATE_DISPLAY, className="mt-1 mb-3 text-muted small text-center"),
                            html.Div([
                                dbc.Label("Select BESS Technology:", html_for=ID_BESS_TECH_DROPDOWN),
                                dcc.Dropdown(
                                    id=ID_BESS_TECH_DROPDOWN,
                                    options=[{"label": tech, "value": tech} for tech in bess_technology_data.keys()],
                                    value=default_bess_params_store[KEY_TECH],
                                    clearable=False,
                                    className="mb-1"
                                ),
                                html.P(id=ID_BESS_EXAMPLE_PRODUCT, className="small text-muted fst-italic mb-3"),
                            ]),
                            html.Hr(),
                            dbc.Row([
                                dbc.Col(dbc.Card([dbc.CardHeader("Capex (Unit Costs)"), dbc.CardBody([
                                    create_bess_input_group("SB + BOS Cost:", ID_BESS_SB_BOS_COST, default_bess_params_store[KEY_SB_BOS_COST], "$/kWh", tooltip_text="Storage Block + Balance of System cost per kWh."),
                                    create_bess_input_group("PCS Cost:", ID_BESS_PCS_COST, default_bess_params_store[KEY_PCS_COST], "$/kW", tooltip_text="Power Conversion System cost per kW."),
                                    create_bess_input_group("System Integration:", ID_BESS_SYS_INT_COST, default_bess_params_store[KEY_SYS_INT_COST], "$/kWh", tooltip_text="Engineering, Software, Commissioning cost per kWh."),
                                    create_bess_input_group("EPC Cost:", ID_BESS_EPC_COST, default_bess_params_store[KEY_EPC_COST], "$/kWh", tooltip_text="Engineering, Procurement, Construction cost per kWh."),
                                ])], className="h-100"), md=6),  # Capex Col
                                dbc.Col([
                                    dbc.Card([dbc.CardHeader("Opex"), dbc.CardBody([
                                        # Opex container populated by callback based on tech selection
                                        html.Div(id=ID_BESS_OPEX_CONTAINER),
                                        create_bess_input_group("Round Trip Efficiency:", ID_BESS_RTE, default_bess_params_store[KEY_RTE], "%", min_val=1, tooltip_text="AC-to-AC efficiency for a full charge/discharge cycle."),
                                        create_bess_input_group("Insurance Rate:", ID_BESS_INSURANCE, default_bess_params_store[KEY_INSURANCE], "%/yr", step=0.01, tooltip_text="Annual insurance cost as a percentage of initial capital cost."),
                                    ])], className="mb-3"),
                                    dbc.Card([dbc.CardHeader("Decommissioning"), dbc.CardBody([
                                        create_bess_input_group("Disconnect/Removal:", ID_BESS_DISCONNECT_COST, default_bess_params_store[KEY_DISCONNECT_COST], "$/kWh", min_val=None),  # Allow negative
                                        create_bess_input_group("Recycling/Disposal:", ID_BESS_RECYCLING_COST, default_bess_params_store[KEY_RECYCLING_COST], "$/kWh", min_val=None, tooltip_text="Net cost (can be negative)."),  # Allow negative
                                    ])]),
                                ], md=6),  # Opex/Decomm Col
                            ], className="mb-3"),
                            dbc.Card([dbc.CardHeader("Performance & Degradation"), dbc.CardBody([
                                dbc.Row([
                                    dbc.Col(create_bess_input_group("Base Cycle Life:", ID_BESS_CYCLE_LIFE, default_bess_params_store[KEY_CYCLE_LIFE], "cycles", min_val=100, tooltip_text="Cycles until end-of-life (e.g., 80% capacity)."), md=6),
                                    dbc.Col(create_bess_input_group("Base Calendar Life:", ID_BESS_CALENDAR_LIFE, default_bess_params_store[KEY_CALENDAR_LIFE], "years", min_val=1, tooltip_text="Expected lifespan based on time."), md=6),
                                ]),
                                dbc.Row([
                                    dbc.Col(create_bess_input_group("Depth of Discharge:", ID_BESS_DOD, default_bess_params_store[KEY_DOD], "%", min_val=1, max_val=100, tooltip_text="Recommended max discharge per cycle."), md=6),
                                    dbc.Col(create_bess_input_group("Capacity Degrad Rate:", ID_DEGRAD_RATE_CAP_YR, default_financial_params[KEY_DEGRAD_PARAMS][KEY_DEGRAD_CAP_YR], "%/yr", min_val=0, step=0.1, tooltip_text="Annual capacity loss."), md=6),
                                ]),
                                dbc.Row([
                                     dbc.Col(create_bess_input_group("RTE Degrad Rate:", ID_DEGRAD_RATE_RTE_YR, default_financial_params[KEY_DEGRAD_PARAMS][KEY_DEGRAD_RTE_YR], "%/yr", min_val=0, step=0.05, tooltip_text="Annual RTE loss."), md=6),
                                     dbc.Col(create_bess_input_group("Replacement Threshold:", ID_REPLACEMENT_THRESHOLD, default_financial_params[KEY_DEGRAD_PARAMS][KEY_REPL_THRESH], "% Cap", min_val=0, max_val=100, tooltip_text="Replace when capacity drops below this % of original."), md=6),
                                ]),
                            ])]),
                        ])
                    ]),
                    # --- Financial Accordion Item ---
                    dbc.AccordionItem(title="Financial Assumptions", children=[
                        dbc.Card(className="p-3", children=[
                            dbc.Row([
                                dbc.Col([html.Label("WACC (%):"), dcc.Input(id=ID_WACC, type="number", value=round(default_financial_params[KEY_WACC]*100, 1), min=0, max=100, className="form-control form-control-sm")], md=3),
                                dbc.Col([html.Label("Project Lifespan (yrs):"), dcc.Input(id=ID_LIFESPAN, type="number", value=default_financial_params[KEY_LIFESPAN], min=1, max=50, className="form-control form-control-sm")], md=3),
                                dbc.Col([html.Label("Tax Rate (%):"), dcc.Input(id=ID_TAX_RATE, type="number", value=default_financial_params[KEY_TAX_RATE]*100, min=0, max=100, className="form-control form-control-sm")], md=3),
                                dbc.Col([html.Label("Inflation Rate (%):"), dcc.Input(id=ID_INFLATION_RATE, type="number", value=default_financial_params[KEY_INFLATION]*100, min=-5, max=100, className="form-control form-control-sm")], md=3),
                            ], className="mb-3"),
                            dbc.Row([
                                dbc.Col([html.Label("Ancillary Revenue ($/yr):"), dcc.Input(id=ID_ANCILLARY_REVENUE_INPUT, type="number", value=default_financial_params[KEY_ANCILLARY_REVENUE], min=0, className="form-control form-control-sm")], md=6),
                                dbc.Col([html.Label("Salvage Value (% of initial):"), dcc.Input(id=ID_SALVAGE, type="number", value=default_financial_params[KEY_SALVAGE]*100, min=0, max=100, className="form-control form-control-sm"), html.P("Note: Less critical with decomm.", className="small text-muted")], md=6),
                            ], className="mb-3"),
                            html.Hr(),
                            dbc.Row([
                                dbc.Col(dbc.Card([dbc.CardHeader("Debt Financing"), dbc.CardBody([
                                    create_bess_input_group("Loan Amount:", ID_LOAN_AMOUNT_PERCENT, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_PERCENT], "% Capex", min_val=0, max_val=100, tooltip_text="Percentage of Initial Gross Cost financed."),
                                    create_bess_input_group("Interest Rate:", ID_LOAN_INTEREST_RATE, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_INTEREST]*100, "%/yr", min_val=0, step=0.1, tooltip_text="Annual loan interest rate."),
                                    create_bess_input_group("Loan Term:", ID_LOAN_TERM_YEARS, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_TERM], "years", min_val=1, step=1, tooltip_text="Loan repayment period."),
                                ])]), md=6),
                                dbc.Col(dbc.Card([dbc.CardHeader("Tax Depreciation"), dbc.CardBody([
                                     html.Label("MACRS Schedule:", className="form-label"),
                                     dcc.Dropdown(
                                         id=ID_MACRS_SCHEDULE,
                                         options=[{'label': k, 'value': k} for k in MACRS_TABLES.keys()],
                                         value=default_financial_params[KEY_DEPREC_PARAMS][KEY_MACRS_SCHEDULE],
                                         clearable=False,
                                         className="form-select form-select-sm"
                                     ),
                                     dbc.Tooltip("Modified Accelerated Cost Recovery System (US Tax Depreciation). Select the appropriate schedule for energy storage property.", target=ID_MACRS_SCHEDULE)
                                ])]), md=6),
                            ]),
                        ])
                    ]),
                ]),  # End Accordion
                html.Div(dbc.Button("Continue to Incentives", id=ID_CONTINUE_INCENTIVES_BTN, n_clicks=0, color="primary", className="mt-4 mb-3"), className="d-flex justify-content-center"),
            ], className="mt-4")
        ]),  # End Tab 2

        # Incentives Tab
        dbc.Tab(label="3. Battery Incentives", tab_id="tab-incentives", children=[
             dbc.Container(children=[
                html.H3("Battery Incentive Programs", className="mb-4 text-center"),
                html.P("Select applicable incentives. Ensure values are correct for your location/project.", className="text-muted mb-4 text-center"),
                dbc.Row([
                    dbc.Col(md=6, children=[  # Federal
                        dbc.Card(className="p-3 mb-4", children=[
                            html.H4("Federal Incentives", className="mb-3"),
                            html.Div([
                                dbc.Checklist(id=ID_ITC_ENABLED, options=[{"label": " Investment Tax Credit (ITC)", "value": "enabled"}], value=(["enabled"] if default_incentive_params["itc_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("ITC Percentage (%):", html_for=ID_ITC_PERCENT, size="sm"), dcc.Input(id=ID_ITC_PERCENT, type="number", value=default_incentive_params["itc_percentage"], min=0, max=100, className="form-control form-control-sm")], className="mb-2 ms-4"),
                                html.P("Tax credit on capital expenditure.", className="text-muted small ms-4"),
                            ], className="mb-3"),
                            html.Div([
                                dbc.Checklist(id="ceic-enabled", options=[{"label": " Clean Electricity Investment Credit (CEIC)", "value": "enabled"}], value=(["enabled"] if default_incentive_params["ceic_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("CEIC Percentage (%):", html_for="ceic-percentage", size="sm"), dcc.Input(id="ceic-percentage", type="number", value=default_incentive_params["ceic_percentage"], min=0, max=100, className="form-control form-control-sm")], className="mb-2 ms-4"),
                                html.P("Mutually exclusive with ITC; higher value applies.", className="text-muted small ms-4"),
                            ], className="mb-3"),
                            html.Div([
                                dbc.Checklist(id="bonus-credit-enabled", options=[{"label": " Bonus Credits (Energy Communities, Domestic Content)", "value": "enabled"}], value=(["enabled"] if default_incentive_params["bonus_credit_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("Bonus Percentage (%):", html_for="bonus-credit-percentage", size="sm"), dcc.Input(id="bonus-credit-percentage", type="number", value=default_incentive_params["bonus_credit_percentage"], min=0, max=100, className="form-control form-control-sm")], className="mb-2 ms-4"),
                                html.P("Stacks with ITC/CEIC.", className="text-muted small ms-4"),
                            ], className="mb-3"),
                        ])
                    ]),
                    dbc.Col(md=6, children=[  # State & Custom
                        dbc.Card(className="p-3 mb-4", children=[  # State
                            html.H4("State Incentives (Examples)", className="mb-3"),
                            html.Div([
                                dbc.Checklist(id="sgip-enabled", options=[{"label": " CA Self-Generation Incentive Program (SGIP)", "value": "enabled"}], value=(["enabled"] if default_incentive_params["sgip_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("SGIP Amount ($/kWh):", html_for="sgip-amount", size="sm"), dcc.Input(id="sgip-amount", type="number", value=default_incentive_params["sgip_amount"], min=0, className="form-control form-control-sm")], className="mb-2 ms-4"),
                            ], className="mb-3"),
                            html.Div([
                                dbc.Checklist(id="ess-enabled", options=[{"label": " CT Energy Storage Solutions", "value": "enabled"}], value=(["enabled"] if default_incentive_params["ess_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("ESS Amount ($/kWh):", html_for="ess-amount", size="sm"), dcc.Input(id="ess-amount", type="number", value=default_incentive_params["ess_amount"], min=0, className="form-control form-control-sm")], className="mb-2 ms-4"),
                            ], className="mb-3"),
                            html.Div([
                                dbc.Checklist(id="mabi-enabled", options=[{"label": " NY Market Acceleration Bridge Incentive", "value": "enabled"}], value=(["enabled"] if default_incentive_params["mabi_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("MABI Amount ($/kWh):", html_for="mabi-amount", size="sm"), dcc.Input(id="mabi-amount", type="number", value=default_incentive_params["mabi_amount"], min=0, className="form-control form-control-sm")], className="mb-2 ms-4"),
                            ], className="mb-3"),
                            html.Div([
                                dbc.Checklist(id="cs-enabled", options=[{"label": " MA Connected Solutions", "value": "enabled"}], value=(["enabled"] if default_incentive_params["cs_enabled"] else []), className="form-check mb-1"),
                                html.Div([dbc.Label("CS Amount ($/kWh):", html_for="cs-amount", size="sm"), dcc.Input(id="cs-amount", type="number", value=default_incentive_params["cs_amount"], min=0, className="form-control form-control-sm")], className="mb-2 ms-4"),
                            ], className="mb-3"),
                        ]),
                        dbc.Card(className="p-3", children=[  # Custom
                            html.H4("Custom Incentive", className="mb-3"),
                            dbc.Checklist(id="custom-incentive-enabled", options=[{"label": " Enable Custom Incentive", "value": "enabled"}], value=(["enabled"] if default_incentive_params["custom_incentive_enabled"] else []), className="form-check mb-2"),
                            html.Div([dbc.Label("Incentive Type:", html_for="custom-incentive-type", size="sm"), dcc.RadioItems(id="custom-incentive-type", options=[{"label": " $/kWh", "value": "per_kwh"}, {"label": " % of Cost", "value": "percentage"}], value=default_incentive_params["custom_incentive_type"], inline=True, className="form-check")], className="mb-2 ms-4"),
                            html.Div([dbc.Label("Incentive Amount:", html_for="custom-incentive-amount", size="sm"), dcc.Input(id="custom-incentive-amount", type="number", value=default_incentive_params["custom_incentive_amount"], min=0, className="form-control form-control-sm")], className="mb-2 ms-4"),
                            html.Div([dbc.Label("Description:", html_for="custom-incentive-description", size="sm"), dcc.Input(id="custom-incentive-description", type="text", value=default_incentive_params["custom_incentive_description"], className="form-control form-control-sm")], className="mb-2 ms-4"),
                        ]),
                    ]),
                ]),  # End Incentive Row
                html.Div([
                    dbc.Button("Calculate Results", id=ID_CALC_BTN, n_clicks=0, color="primary", className="mt-4 mb-3 me-3"),
                    dbc.Button("Optimize Battery Size", id=ID_OPTIMIZE_BTN, n_clicks=0, color="success", className="mt-4 mb-3"),
                ], className="d-flex justify-content-center"),
            ], className="mt-4")
        ]),  # End Tab 3

        # Results Tab
        dbc.Tab(label="4. Results & Analysis", tab_id="tab-results", children=[
            dbc.Container(children=[
                dcc.Loading(id="loading-results", type="circle", children=[
                    html.Div(id=ID_RESULTS_OUTPUT, className="mt-4")  # Populated by callback
                ])
            ], fluid=True, className="mt-4")  # Use fluid container for results
        ]),  # End Tab 4

        # Optimization Tab
        dbc.Tab(label="5. Battery Sizing Tool", tab_id="tab-optimization", children=[
             dbc.Container(children=[
                dcc.Loading(id="loading-optimization", type="circle", children=[
                    html.Div(id=ID_OPTIMIZE_OUTPUT, className="mt-4")  # Populated by callback
                ])
            ], className="mt-4")
        ]),  # End Tab 5
    ]),  # End Tabs
])  # End Main Container
# Section 8
# --- Tab Navigation Callback ---
@app.callback(
    Output(ID_MAIN_TABS, "active_tab"),
    [
        Input(ID_CONTINUE_PARAMS_BTN, "n_clicks"),
        Input(ID_CONTINUE_INCENTIVES_BTN, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def navigate_tabs(n_params, n_incentives):
    triggered_id = ctx.triggered_id
    if not triggered_id:
        return dash.no_update
    if triggered_id == ID_CONTINUE_PARAMS_BTN:
        return "tab-params"
    elif triggered_id == ID_CONTINUE_INCENTIVES_BTN:
        return "tab-incentives"
    return dash.no_update


# --- EAF Store Update ---
@app.callback(
    Output(STORE_EAF, "data"),
    [
        Input(ID_EAF_SIZE, "value"),
        Input(ID_EAF_COUNT, "value"),
        Input(ID_GRID_CAP, "value"),
        Input(ID_CYCLES_PER_DAY, "value"),
        Input(ID_CYCLE_DURATION, "value"),
        Input(ID_DAYS_PER_YEAR, "value"),
        Input(ID_MILL_DROPDOWN, "value"),
    ],
    State(STORE_EAF, "data"),
)
def update_eaf_params_store(
    size, count, grid_cap, cycles, duration, days, selected_mill, existing_data
):
    triggered_id = ctx.triggered_id if ctx.triggered_id else "unknown"
    output_data = (
        existing_data.copy()
        if existing_data and isinstance(existing_data, dict)
        else nucor_mills["Custom"].copy()
    )

    # Initialize input tracker if missing
    if KEY_CYCLE_DURATION_INPUT not in output_data:
        output_data[KEY_CYCLE_DURATION_INPUT] = output_data.get(KEY_CYCLE_DURATION, 36)

    if triggered_id == ID_MILL_DROPDOWN:
        # Load all data from selected mill
        output_data = nucor_mills.get(selected_mill, nucor_mills["Custom"]).copy()
        # Ensure input tracker matches loaded duration
        output_data[KEY_CYCLE_DURATION_INPUT] = output_data.get(KEY_CYCLE_DURATION, 36)
    else:
        # Update individual fields from UI inputs
        if size is not None:
            output_data[KEY_EAF_SIZE] = size
        if count is not None:
            output_data["eaf_count"] = count
        if grid_cap is not None:
            output_data[KEY_GRID_CAP] = grid_cap
        if cycles is not None:
            output_data[KEY_CYCLES_PER_DAY] = cycles
        if duration is not None:
            output_data[KEY_CYCLE_DURATION] = duration  # Update the main duration
            output_data[KEY_CYCLE_DURATION_INPUT] = duration  # Also update the tracker
        if days is not None:
            output_data[KEY_DAYS_PER_YEAR] = days

    # Ensure cycle duration is valid (use input tracker if valid, else default)
    try:
        input_duration = float(output_data.get(KEY_CYCLE_DURATION_INPUT, 0))
    except (ValueError, TypeError):
        input_duration = 0.0
    if input_duration > 0:
        output_data[KEY_CYCLE_DURATION] = input_duration
    else:
        # If input tracker is invalid, fall back to default or existing valid duration
        try:
            base_duration = float(output_data.get(KEY_CYCLE_DURATION, 0))
        except (ValueError, TypeError):
            base_duration = 0.0
        output_data[KEY_CYCLE_DURATION] = base_duration if base_duration > 0 else 36.0
        output_data[KEY_CYCLE_DURATION_INPUT] = output_data[
            KEY_CYCLE_DURATION
        ]  # Reset tracker

    return output_data


# --- Financial Store Update ---
@app.callback(
    Output(STORE_FINANCIAL, "data"),
    [
        Input(ID_WACC, "value"),
        Input(ID_LIFESPAN, "value"),
        Input(ID_TAX_RATE, "value"),
        Input(ID_INFLATION_RATE, "value"),
        Input(ID_SALVAGE, "value"),
        # New Inputs
        Input(ID_LOAN_AMOUNT_PERCENT, "value"),
        Input(ID_LOAN_INTEREST_RATE, "value"),
        Input(ID_LOAN_TERM_YEARS, "value"),
        Input(ID_MACRS_SCHEDULE, "value"),
        Input(ID_DEGRAD_RATE_CAP_YR, "value"),
        Input(ID_DEGRAD_RATE_RTE_YR, "value"),
        Input(ID_REPLACEMENT_THRESHOLD, "value"),
        Input(ID_ANCILLARY_REVENUE_INPUT, "value"),
    ],
    State(STORE_FINANCIAL, "data"),  # Keep state to preserve structure
)
def update_financial_params_store(
    wacc,
    lifespan,
    tax,
    inflation,
    salvage,
    loan_pct,
    loan_int,
    loan_term,
    macrs,
    degrad_cap,
    degrad_rte,
    repl_thresh,
    ancillary_rev,
    existing_data,
):
    # Start with existing or default structure
    fin_data = (
        existing_data
        if existing_data and isinstance(existing_data, dict)
        else default_financial_params.copy()
    )
    # Ensure nested dicts exist
    if KEY_DEBT_PARAMS not in fin_data or not isinstance(
        fin_data[KEY_DEBT_PARAMS], dict
    ):
        fin_data[KEY_DEBT_PARAMS] = {}
    if KEY_DEPREC_PARAMS not in fin_data or not isinstance(
        fin_data[KEY_DEPREC_PARAMS], dict
    ):
        fin_data[KEY_DEPREC_PARAMS] = {}
    if KEY_DEGRAD_PARAMS not in fin_data or not isinstance(
        fin_data[KEY_DEGRAD_PARAMS], dict
    ):
        fin_data[KEY_DEGRAD_PARAMS] = {}

    # Helper for safe conversion
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def safe_int(value, default=0):
        if value is None:
            return default
        try:
            return int(float(value))  # Float first
        except (ValueError, TypeError):
            return default

    # Update top-level keys
    fin_data[KEY_WACC] = (
        safe_float(wacc, default_financial_params[KEY_WACC] * 100) / 100.0
    )
    fin_data[KEY_LIFESPAN] = safe_int(lifespan, default_financial_params[KEY_LIFESPAN])
    fin_data[KEY_TAX_RATE] = (
        safe_float(tax, default_financial_params[KEY_TAX_RATE] * 100) / 100.0
    )
    fin_data[KEY_INFLATION] = (
        safe_float(inflation, default_financial_params[KEY_INFLATION] * 100) / 100.0
    )
    fin_data[KEY_SALVAGE] = (
        safe_float(salvage, default_financial_params[KEY_SALVAGE] * 100) / 100.0
    )
    fin_data[KEY_ANCILLARY_REVENUE] = safe_float(
        ancillary_rev, default_financial_params[KEY_ANCILLARY_REVENUE]
    )

    # Update nested keys
    fin_data[KEY_DEBT_PARAMS][KEY_LOAN_PERCENT] = safe_float(
        loan_pct, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_PERCENT]
    )
    fin_data[KEY_DEBT_PARAMS][KEY_LOAN_INTEREST] = (
        safe_float(
            loan_int, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_INTEREST] * 100
        )
        / 100.0
    )
    fin_data[KEY_DEBT_PARAMS][KEY_LOAN_TERM] = safe_int(
        loan_term, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_TERM]
    )

    fin_data[KEY_DEPREC_PARAMS][KEY_MACRS_SCHEDULE] = (
        macrs
        if macrs is not None
        else default_financial_params[KEY_DEPREC_PARAMS][KEY_MACRS_SCHEDULE]
    )

    fin_data[KEY_DEGRAD_PARAMS][KEY_DEGRAD_CAP_YR] = safe_float(
        degrad_cap, default_financial_params[KEY_DEGRAD_PARAMS][KEY_DEGRAD_CAP_YR]
    )
    fin_data[KEY_DEGRAD_PARAMS][KEY_DEGRAD_RTE_YR] = safe_float(
        degrad_rte, default_financial_params[KEY_DEGRAD_PARAMS][KEY_DEGRAD_RTE_YR]
    )
    fin_data[KEY_DEGRAD_PARAMS][KEY_REPL_THRESH] = safe_float(
        repl_thresh, default_financial_params[KEY_DEGRAD_PARAMS][KEY_REPL_THRESH]
    )

    return fin_data


# --- Incentive Store Update ---
@app.callback(
    Output(STORE_INCENTIVE, "data"),
    [
        Input(ID_ITC_ENABLED, "value"),
        Input(ID_ITC_PERCENT, "value"),
        Input("ceic-enabled", "value"),
        Input("ceic-percentage", "value"),
        Input("bonus-credit-enabled", "value"),
        Input("bonus-credit-percentage", "value"),
        Input("sgip-enabled", "value"),
        Input("sgip-amount", "value"),
        Input("ess-enabled", "value"),
        Input("ess-amount", "value"),
        Input("mabi-enabled", "value"),
        Input("mabi-amount", "value"),
        Input("cs-enabled", "value"),
        Input("cs-amount", "value"),
        Input("custom-incentive-enabled", "value"),
        Input("custom-incentive-type", "value"),
        Input("custom-incentive-amount", "value"),
        Input("custom-incentive-description", "value"),
    ],
)
def update_incentive_params_store(
    itc_en,
    itc_pct,
    ceic_en,
    ceic_pct,
    bonus_en,
    bonus_pct,
    sgip_en,
    sgip_amt,
    ess_en,
    ess_amt,
    mabi_en,
    mabi_amt,
    cs_en,
    cs_amt,
    custom_en,
    custom_type,
    custom_amt,
    custom_desc,
):
    # Helper for safe conversion
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


    return {
        "itc_enabled": "enabled" in itc_en if itc_en else False,
        "itc_percentage": safe_float(
            itc_pct, default_incentive_params["itc_percentage"]
        ),
        "ceic_enabled": "enabled" in ceic_en if ceic_en else False,
        "ceic_percentage": safe_float(
            ceic_pct, default_incentive_params["ceic_percentage"]
        ),
        "bonus_credit_enabled": "enabled" in bonus_en if bonus_en else False,
        "bonus_credit_percentage": safe_float(
            bonus_pct, default_incentive_params["bonus_credit_percentage"]
        ),
        "sgip_enabled": "enabled" in sgip_en if sgip_en else False,
        "sgip_amount": safe_float(sgip_amt, default_incentive_params["sgip_amount"]),
        "ess_enabled": "enabled" in ess_en if ess_en else False,
        "ess_amount": safe_float(ess_amt, default_incentive_params["ess_amount"]),
        "mabi_enabled": "enabled" in mabi_en if mabi_en else False,
        "mabi_amount": safe_float(mabi_amt, default_incentive_params["mabi_amount"]),
        "cs_enabled": "enabled" in cs_en if cs_en else False,
        "cs_amount": safe_float(cs_amt, default_incentive_params["cs_amount"]),
        "custom_incentive_enabled": "enabled" in custom_en if custom_en else False,
        "custom_incentive_type": (
            custom_type
            if custom_type
            else default_incentive_params["custom_incentive_type"]
        ),
        "custom_incentive_amount": safe_float(
            custom_amt, default_incentive_params["custom_incentive_amount"]
        ),
        "custom_incentive_description": (
            custom_desc
            if custom_desc
            else default_incentive_params["custom_incentive_description"]
        ),
    }
# Section 9
# --- Seasonal Rates UI Toggle & Population ---
@app.callback(
    [Output(ID_SEASONAL_CONTAINER, "children"), Output(ID_SEASONAL_CONTAINER, "style")],
    [
        Input(ID_SEASONAL_TOGGLE, "value"),
        Input(ID_UTILITY_DROPDOWN, "value"),
    ],  # Trigger on toggle OR utility change
)
def update_seasonal_rates_ui(toggle_value, selected_utility):
    """Create and control visibility of seasonal rate inputs"""
    # Determine visibility based on toggle
    is_enabled = toggle_value and "enabled" in toggle_value
    display_style = (
        {
            "display": "block",
            "border": "1px solid #ccc",
            "padding": "10px",
            "border-radius": "5px",
            "background-color": "#f9f9f9",
        }
        if is_enabled
        else {"display": "none"}
    )

    # Determine which utility data to use for populating the inputs
    utility_data_source = utility_rates.get(selected_utility)
    if not utility_data_source:  # Handle empty utility entries
        utility_data_source = utility_rates["Custom Utility"]

    # Get values from the utility data source safely
    winter_mult = utility_data_source.get(
        KEY_WINTER_MULT, default_utility_params[KEY_WINTER_MULT]
    )
    summer_mult = utility_data_source.get(
        KEY_SUMMER_MULT, default_utility_params[KEY_SUMMER_MULT]
    )
    shoulder_mult = utility_data_source.get(
        KEY_SHOULDER_MULT, default_utility_params[KEY_SHOULDER_MULT]
    )
    winter_m = ",".join(
        map(
            str,
            utility_data_source.get(
                KEY_WINTER_MONTHS, default_utility_params[KEY_WINTER_MONTHS]
            ),
        )
    )
    summer_m = ",".join(
        map(
            str,
            utility_data_source.get(
                KEY_SUMMER_MONTHS, default_utility_params[KEY_SUMMER_MONTHS]
            ),
        )
    )
    shoulder_m = ",".join(
        map(
            str,
            utility_data_source.get(
                KEY_SHOULDER_MONTHS, default_utility_params[KEY_SHOULDER_MONTHS]
            ),
        )
    )

    # Create the UI elements
    seasonal_ui = html.Div(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Winter Multiplier:", size="sm"),
                            dcc.Input(
                                id=ID_WINTER_MULTIPLIER,
                                type="number",
                                value=winter_mult,
                                min=0,
                                step=0.01,
                                className="form-control form-control-sm",
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Summer Multiplier:", size="sm"),
                            dcc.Input(
                                id=ID_SUMMER_MULTIPLIER,
                                type="number",
                                value=summer_mult,
                                min=0,
                                step=0.01,
                                className="form-control form-control-sm",
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Shoulder Multiplier:", size="sm"),
                            dcc.Input(
                                id=ID_SHOULDER_MULTIPLIER,
                                type="number",
                                value=shoulder_mult,
                                min=0,
                                step=0.01,
                                className="form-control form-control-sm",
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                ],
                className="row mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Label("Winter Months (1-12):", size="sm"),
                            dcc.Input(
                                id=ID_WINTER_MONTHS,
                                type="text",
                                value=winter_m,
                                placeholder="e.g., 11,12,1,2",
                                className="form-control form-control-sm",
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Summer Months (1-12):", size="sm"),
                            dcc.Input(
                                id=ID_SUMMER_MONTHS,
                                type="text",
                                value=summer_m,
                                placeholder="e.g., 6,7,8,9",
                                className="form-control form-control-sm",
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                    dbc.Col(
                        [
                            dbc.Label("Shoulder Months (1-12):", size="sm"),
                            dcc.Input(
                                id=ID_SHOULDER_MONTHS,
                                type="text",
                                value=shoulder_m,
                                placeholder="e.g., 3,4,5,10",
                                className="form-control form-control-sm",
                            ),
                        ],
                        md=4,
                        className="mb-2",
                    ),
                ],
                className="row",
            ),
            html.P(
                "Use comma-separated month numbers (1-12). Ensure all 12 months are assigned.",
                className="small text-muted mt-1",
            ),
        ]
    )
    return seasonal_ui, display_style


# --- Utility Store Update (Using State for seasonal inputs) ---
@app.callback(
    Output(STORE_UTILITY, "data"),
    [
        Input(ID_UTILITY_DROPDOWN, "value"),
        Input(ID_OFF_PEAK, "value"),
        Input(ID_MID_PEAK, "value"),
        Input(ID_PEAK, "value"),
        Input(ID_DEMAND_CHARGE, "value"),
        Input(ID_SEASONAL_TOGGLE, "value"),
        Input({"type": "tou-start", "index": ALL}, "value"),
        Input({"type": "tou-end", "index": ALL}, "value"),
        Input({"type": "tou-rate", "index": ALL}, "value"),
    ],
    [
        State(STORE_UTILITY, "data"),
        # Changed: Seasonal inputs from Input to State
        State(ID_WINTER_MULTIPLIER, "value"),
        State(ID_SUMMER_MULTIPLIER, "value"),
        State(ID_SHOULDER_MULTIPLIER, "value"),
        State(ID_WINTER_MONTHS, "value"),
        State(ID_SUMMER_MONTHS, "value"),
        State(ID_SHOULDER_MONTHS, "value"),
    ],
    prevent_initial_call=True,
)
def update_utility_params_store(
    utility_provider,
    off_peak_rate,
    mid_peak_rate,
    peak_rate,
    demand_charge,
    seasonal_toggle_value,
    tou_starts,
    tou_ends,
    tou_rates,
    existing_data,
    winter_mult,
    summer_mult,
    shoulder_mult,
    winter_months_str,
    summer_months_str,
    shoulder_months_str,
):

    triggered_id = ctx.triggered_id
    params = {}

    # Determine base parameters (from dropdown or existing state)
    if isinstance(triggered_id, str) and triggered_id == ID_UTILITY_DROPDOWN:
        params = utility_rates.get(utility_provider, default_utility_params).copy()
        # Ensure TOU raw data uses the key from the utility_rates structure
        params[KEY_TOU_RAW] = params.get(
            "tou_periods", default_utility_params[KEY_TOU_RAW]
        )
    elif existing_data and isinstance(existing_data, dict):
        params = existing_data.copy()
    else:
        params = default_utility_params.copy()

    # Helper for safe conversion
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    # Update basic rates
    params[KEY_ENERGY_RATES] = {
        "off_peak": safe_float(
            off_peak_rate, default_utility_params[KEY_ENERGY_RATES]["off_peak"]
        ),
        "mid_peak": safe_float(
            mid_peak_rate, default_utility_params[KEY_ENERGY_RATES]["mid_peak"]
        ),
        "peak": safe_float(peak_rate, default_utility_params[KEY_ENERGY_RATES]["peak"]),
    }
    params[KEY_DEMAND_CHARGE] = safe_float(
        demand_charge, default_utility_params[KEY_DEMAND_CHARGE]
    )

    # Update seasonal settings based on toggle and State values
    is_seasonal_enabled = seasonal_toggle_value and "enabled" in seasonal_toggle_value
    params[KEY_SEASONAL] = is_seasonal_enabled

    def parse_months(month_str, default_list):
        """Safely parses comma-separated month string into list of ints."""
        if not isinstance(month_str, str):
            return default_list
        try:
            parsed = [
                int(m.strip())
                for m in month_str.split(",")
                if m.strip().isdigit() and 1 <= int(m.strip()) <= 12
            ]
            return parsed if parsed else default_list
        except ValueError:
            return default_list

    if is_seasonal_enabled:
        # Use the State values for seasonal parameters
        params[KEY_WINTER_MONTHS] = parse_months(
            winter_months_str, default_utility_params[KEY_WINTER_MONTHS]
        )
        params[KEY_SUMMER_MONTHS] = parse_months(
            summer_months_str, default_utility_params[KEY_SUMMER_MONTHS]
        )
        params[KEY_SHOULDER_MONTHS] = parse_months(
            shoulder_months_str, default_utility_params[KEY_SHOULDER_MONTHS]
        )
        params[KEY_WINTER_MULT] = safe_float(
            winter_mult, default_utility_params[KEY_WINTER_MULT]
        )
        params[KEY_SUMMER_MULT] = safe_float(
            summer_mult, default_utility_params[KEY_SUMMER_MULT]
        )
        params[KEY_SHOULDER_MULT] = safe_float(
            shoulder_mult, default_utility_params[KEY_SHOULDER_MULT]
        )
    else:
        # If seasonal is disabled, reset to defaults but keep the values
        params[KEY_WINTER_MONTHS] = default_utility_params[KEY_WINTER_MONTHS]
        params[KEY_SUMMER_MONTHS] = default_utility_params[KEY_SUMMER_MONTHS]
        params[KEY_SHOULDER_MONTHS] = default_utility_params[KEY_SHOULDER_MONTHS]
        params[KEY_WINTER_MULT] = 1.0  # Use 1.0 when disabled
        params[KEY_SUMMER_MULT] = 1.0  # Use 1.0 when disabled
        params[KEY_SHOULDER_MULT] = 1.0  # Use 1.0 when disabled

    # Update TOU periods (unless triggered by utility dropdown, which already set it)
    if not (isinstance(triggered_id, str) and triggered_id == ID_UTILITY_DROPDOWN):
        raw_tou_periods = []
        for i in range(len(tou_starts)):
            start_val, end_val, rate_val = tou_starts[i], tou_ends[i], tou_rates[i]
            # Check if all values for a row are present
            if start_val is not None and end_val is not None and rate_val is not None:
                try:
                    start_f, end_f = float(start_val), float(end_val)
                    # Basic validation for start < end
                    if 0 <= start_f < end_f <= 24:
                        raw_tou_periods.append((start_f, end_f, str(rate_val)))
                    else:
                        print(
                            f"Warning: Skipping invalid TOU time range: Start={start_f}, End={end_f}"
                        )
                except (ValueError, TypeError):
                    print(
                        f"Warning: Skipping invalid TOU numeric value: Start={start_val}, End={end_val}"
                    )
                    pass  # Skip row if conversion fails
        params[KEY_TOU_RAW] = raw_tou_periods

    # Always refill gaps based on the current raw periods
    params[KEY_TOU_FILLED] = fill_tou_gaps(params.get(KEY_TOU_RAW, []))

    return params


# --- TOU Container Management ---
@app.callback(
    Output(ID_TOU_CONTAINER, "children", allow_duplicate=True),
    [
        Input(ID_ADD_TOU_BTN, "n_clicks"),
        Input({"type": "remove-tou", "index": ALL}, "n_clicks"),
    ],
    State(ID_TOU_CONTAINER, "children"),
    prevent_initial_call=True,
)
def modify_tou_rows(add_clicks, remove_clicks_list, current_rows):
    triggered_input = ctx.triggered_id
    if not triggered_input:
        return dash.no_update

    # Ensure current_rows is a list
    new_rows = current_rows[:] if current_rows else []

    if triggered_input == ID_ADD_TOU_BTN:
        new_index = len(new_rows)
        default_start = 0.0
        # Try to get the end time of the last row to suggest a start time
        if new_rows:
            try:
                # Access the value property of the 'tou-end' input in the last row
                last_end_input = current_rows[-1]["props"]["children"][0]["props"][
                    "children"
                ][1]["props"]["children"]
                default_start = last_end_input["props"].get("value", 0.0)
            except (IndexError, KeyError, AttributeError):
                pass  # Keep default_start as 0.0 if structure is unexpected

        # Generate UI for a single new row
        new_row_elements = generate_tou_ui_elements(
            [(default_start, default_start, "off_peak")]
        )
        if new_row_elements:
            new_row_div = new_row_elements[0]
            # Update the index in the IDs within the new row
            new_row_div.id = f"tou-row-{new_index}"  # Update outer div ID
            try:
                for component_wrapper in new_row_div["props"]["children"][0]["props"][
                    "children"
                ]:
                    component = component_wrapper["props"]["children"]
                    if hasattr(component, "id") and isinstance(component.id, dict):
                        component.id["index"] = new_index
            except (IndexError, KeyError, AttributeError):
                print("Error updating index for new TOU row components")

            new_rows.append(new_row_div)

    elif (
        isinstance(triggered_input, dict)
        and triggered_input.get("type") == "remove-tou"
    ):
        if len(new_rows) > 1:  # Only remove if more than one row exists
            clicked_index = triggered_input["index"]
            row_to_remove_id = f"tou-row-{clicked_index}"
            # Filter out the row with the matching ID
            new_rows = [
                row
                for row in new_rows
                if row.get("props", {}).get("id") != row_to_remove_id
            ]

            # Re-index the remaining rows to be sequential
            for i, row in enumerate(new_rows):
                row["props"]["id"] = f"tou-row-{i}"  # Update outer div ID
                try:
                    for component_wrapper in row["props"]["children"][0]["props"][
                        "children"
                    ]:
                        component = component_wrapper["props"]["children"]
                        if hasattr(component, "id") and isinstance(component.id, dict):
                            component.id["index"] = i
                except (IndexError, KeyError, AttributeError):
                    print(f"Error re-indexing TOU row {i}")

    # Update the disabled state of remove buttons
    num_rows = len(new_rows)
    for i, row in enumerate(new_rows):
        try:
            # Access the remove button component
            remove_button = row["props"]["children"][0]["props"]["children"][-1][
                "props"
            ]["children"]
            remove_button["props"]["disabled"] = num_rows <= 1
        except (IndexError, KeyError, AttributeError):
            print(f"Error updating disable state for TOU row {i}")
            pass  # Continue if structure is unexpected

    return new_rows


# --- Mill Info Card Update ---
@app.callback(Output(ID_MILL_INFO_CARD, "children"), Input(ID_MILL_DROPDOWN, "value"))
def update_mill_info(selected_mill):
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]
        selected_mill = "Custom"
        card_header_class = "card-header bg-secondary text-white"
    else:
        mill_data = nucor_mills[selected_mill]
        card_header_class = "card-header bg-primary text-white"

    # Helper to format numbers with commas or return N/A
    def fmt_num(key, data, is_int=True):
        val = data.get(key)
        if val is None:
            return "N/A"
        try:
            num = int(val) if is_int else float(val)
            return f"{num:,}" if is_int else f"{num:,.1f}"  # Add commas
        except (ValueError, TypeError):
            return "N/A"


    return dbc.Card(
        [
            dbc.CardHeader(
                f"Selected: Nucor Steel {selected_mill}", className=card_header_class
            ),
            dbc.CardBody(
                [
                    html.Div(
                        [
                            html.Strong("Location: "),
                            html.Span(mill_data.get("location", "N/A")),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Mill Type: "),
                            html.Span(mill_data.get("type", "N/A")),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("EAF Config: "),
                            html.Span(
                                f"{fmt_num('eaf_count', mill_data)} x {fmt_num(KEY_EAF_SIZE, mill_data)} ton {mill_data.get('eaf_type', 'N/A')} ({mill_data.get('eaf_manufacturer', 'N/A')})"
                            ),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Production: "),
                            html.Span(
                                f"{fmt_num('tons_per_year', mill_data)} tons/year"
                            ),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Schedule: "),
                            html.Span(
                                f"{fmt_num(KEY_CYCLES_PER_DAY, mill_data)} cycles/day, {fmt_num(KEY_DAYS_PER_YEAR, mill_data)} days/year, {fmt_num(KEY_CYCLE_DURATION, mill_data)} min/cycle"
                            ),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Utility: "),
                            html.Span(mill_data.get("utility", "N/A")),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Grid Cap (Est): "),
                            html.Span(f"{fmt_num(KEY_GRID_CAP, mill_data)} MW"),
                        ],
                        className="mb-1",
                    ),
                ]
            ),
        ]
    )
# Section 10
# --- C-Rate Display Update ---
@app.callback(
    Output(ID_BESS_C_RATE_DISPLAY, "children"),
    [Input(ID_BESS_CAPACITY, "value"), Input(ID_BESS_POWER, "value")],
)
def update_c_rate_display(capacity, power):
    try:
        cap_val = float(capacity)
        pow_val = float(power)
        if cap_val is not None and pow_val is not None and cap_val > 0:
            c_rate = pow_val / cap_val
            return f"Calculated C-Rate: {c_rate:.2f} h⁻¹"
        elif cap_val == 0 and pow_val > 0:
            return "C-Rate: Infinite (Capacity is zero)"
        else:
            return ""  # Hide if inputs are invalid or zero power
    except (ValueError, TypeError, ZeroDivisionError):
        return ""  # Hide on error


# --- BESS Input Update on Technology Selection ---
@app.callback(
    [
        Output(ID_BESS_EXAMPLE_PRODUCT, "children"),
        Output(ID_BESS_SB_BOS_COST, "value"),
        Output(ID_BESS_PCS_COST, "value"),
        Output(ID_BESS_EPC_COST, "value"),
        Output(ID_BESS_SYS_INT_COST, "value"),
        Output(ID_BESS_OPEX_CONTAINER, "children"),  # Update Opex container
        Output(ID_BESS_RTE, "value"),
        Output(ID_BESS_INSURANCE, "value"),
        Output(ID_BESS_DISCONNECT_COST, "value"),
        Output(ID_BESS_RECYCLING_COST, "value"),
        Output(ID_BESS_CYCLE_LIFE, "value"),
        Output(ID_BESS_DOD, "value"),
        Output(ID_BESS_CALENDAR_LIFE, "value"),
    ],
    Input(ID_BESS_TECH_DROPDOWN, "value"),
    prevent_initial_call=True,
)
def update_bess_inputs_from_technology(selected_technology):
    if not selected_technology or selected_technology not in bess_technology_data:
        selected_technology = "LFP"  # Fallback to default

    tech_data = bess_technology_data[selected_technology]

    # Determine which O&M input to show based on keys present in the tech data
    show_om_kwhyr = KEY_OM_KWHR_YR in tech_data
    show_fixed_om = KEY_FIXED_OM in tech_data

    # Decide which input group to show
    # Show OM_KWHR_YR if it exists, otherwise show FIXED_OM
    style_fixed_om = (
        {"display": "flex"}
        if show_fixed_om and not show_om_kwhyr
        else {"display": "none"}
    )
    style_om_kwhyr = {"display": "flex"} if show_om_kwhyr else {"display": "none"}

    # Create the input groups, they will be hidden/shown via style
    fixed_om_input_group = create_bess_input_group(
        "Fixed O&M:",
        ID_BESS_FIXED_OM,
        tech_data.get(KEY_FIXED_OM, 0),
        "$/kW/yr",
        tooltip_text="Annual Fixed O&M cost per kW.",
        style=style_fixed_om,
    )
    om_kwhyr_input_group = create_bess_input_group(
        "O&M Cost:",
        ID_BESS_OM_KWHR_YR,
        tech_data.get(KEY_OM_KWHR_YR, 0),
        "$/kWh/yr",
        tooltip_text="Annual O&M cost per kWh.",
        style=style_om_kwhyr,
    )

    # The container will hold both input groups, but only one is visible
    opex_container_children = [fixed_om_input_group, om_kwhyr_input_group]

    return (
        tech_data.get(KEY_EXAMPLE_PRODUCT, "N/A"),
        tech_data.get(KEY_SB_BOS_COST, 0),
        tech_data.get(KEY_PCS_COST, 0),
        tech_data.get(KEY_EPC_COST, 0),
        tech_data.get(KEY_SYS_INT_COST, 0),
        opex_container_children,  # Pass the container with both input groups
        tech_data.get(KEY_RTE, 0),
        tech_data.get(KEY_INSURANCE, 0),
        tech_data.get(KEY_DISCONNECT_COST, 0),
        tech_data.get(KEY_RECYCLING_COST, 0),
        tech_data.get(KEY_CYCLE_LIFE, 0),
        tech_data.get(KEY_DOD, 0),
        tech_data.get(KEY_CALENDAR_LIFE, 0),
    )


# --- BESS Store Update (Using State for Opex inputs) ---
@app.callback(
    Output(STORE_BESS, "data"),
    [
        Input(ID_BESS_CAPACITY, "value"),
        Input(ID_BESS_POWER, "value"),
        Input(ID_BESS_TECH_DROPDOWN, "value"),
        Input(ID_BESS_SB_BOS_COST, "value"),
        Input(ID_BESS_PCS_COST, "value"),
        Input(ID_BESS_EPC_COST, "value"),
        Input(ID_BESS_SYS_INT_COST, "value"),
        Input(ID_BESS_RTE, "value"),
        Input(ID_BESS_INSURANCE, "value"),
        Input(ID_BESS_DISCONNECT_COST, "value"),
        Input(ID_BESS_RECYCLING_COST, "value"),
        Input(ID_BESS_CYCLE_LIFE, "value"),
        Input(ID_BESS_DOD, "value"),
        Input(ID_BESS_CALENDAR_LIFE, "value"),
    ],
    # Using State for Opex inputs to handle conditionally visible components
    [State(ID_BESS_FIXED_OM, "value"), State(ID_BESS_OM_KWHR_YR, "value")],
    prevent_initial_call=True,
)
def update_bess_params_store(
    capacity,
    power,
    technology,
    sb_bos_cost,
    pcs_cost,
    epc_cost,
    sys_int_cost,
    rte,
    insurance,
    disconnect_cost,
    recycling_cost,
    cycle_life,
    dod,
    calendar_life,
    # State values for Opex inputs
    fixed_om,
    om_kwhyr,
):
    """
    Updates the BESS parameter store. Always rebuilds the dictionary based on
    the selected technology template and then overwrites with current UI values
    to ensure consistency. Adds explicit None checks and type conversions.
    """
    try:
        # Use selected technology, fallback to LFP if invalid
        if not technology or technology not in bess_technology_data:
            technology = "LFP"

        # Start with the defaults for the currently selected technology
        default_tech_data = bess_technology_data.get(
            technology, bess_technology_data.get("LFP", {})
        )
        store_data = default_tech_data.copy()

        # Helper to safely convert input to float, defaulting to 0.0 if None or error
        def safe_float(value, default=0.0):
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        # Helper to safely convert input to int, defaulting to 0 if None or error
        def safe_int(value, default=0):
            if value is None:
                return default
            try:
                return int(float(value))  # Float first to handle "10.0" etc.
            except (ValueError, TypeError):
                return default

        # Update with actual UI values (these will override defaults)
        store_data[KEY_CAPACITY] = safe_float(
            capacity, 0.001
        )  # Use small positive default
        store_data[KEY_POWER_MAX] = safe_float(
            power, 0.001
        )  # Use small positive default
        store_data[KEY_TECH] = technology
        store_data[KEY_SB_BOS_COST] = safe_float(
            sb_bos_cost, store_data.get(KEY_SB_BOS_COST, 0)
        )
        store_data[KEY_PCS_COST] = safe_float(pcs_cost, store_data.get(KEY_PCS_COST, 0))
        store_data[KEY_EPC_COST] = safe_float(epc_cost, store_data.get(KEY_EPC_COST, 0))
        store_data[KEY_SYS_INT_COST] = safe_float(
            sys_int_cost, store_data.get(KEY_SYS_INT_COST, 0)
        )
        store_data[KEY_RTE] = safe_float(rte, store_data.get(KEY_RTE, 0))
        store_data[KEY_INSURANCE] = safe_float(
            insurance, store_data.get(KEY_INSURANCE, 0)
        )
        store_data[KEY_DISCONNECT_COST] = safe_float(
            disconnect_cost, store_data.get(KEY_DISCONNECT_COST, 0)
        )
        store_data[KEY_RECYCLING_COST] = safe_float(
            recycling_cost, store_data.get(KEY_RECYCLING_COST, 0)
        )
        store_data[KEY_CYCLE_LIFE] = safe_int(
            cycle_life, store_data.get(KEY_CYCLE_LIFE, 1000)
        )
        store_data[KEY_DOD] = safe_float(dod, store_data.get(KEY_DOD, 0))
        store_data[KEY_CALENDAR_LIFE] = safe_int(
            calendar_life, store_data.get(KEY_CALENDAR_LIFE, 10)
        )

        # Handle O&M fields - ALWAYS INCLUDE BOTH, using the State values
        store_data[KEY_FIXED_OM] = safe_float(fixed_om, store_data.get(KEY_FIXED_OM, 0))
        store_data[KEY_OM_KWHR_YR] = safe_float(
            om_kwhyr, store_data.get(KEY_OM_KWHR_YR, 0)
        )

        # Add any missing keys from the technology template (like example_product)
        # This ensures the dict passed to calculation is complete
        tech_template = bess_technology_data.get(store_data[KEY_TECH], {})
        for key, value in tech_template.items():
            if key not in store_data:
                store_data[key] = value

        return store_data


    except Exception as e:
        print(f"Error in update_bess_params_store: {e}")
        traceback.print_exc()
        # Return no_update to prevent storing potentially corrupted data
        return dash.no_update
# Section 11
# --- Input Validation Callback ---
@app.callback(
    [
        Output(ID_VALIDATION_ERR, "children"),
        Output(ID_VALIDATION_ERR, "is_open"),
        Output(ID_CALCULATION_ERR, "is_open", allow_duplicate=True),
    ],
    [Input(ID_CALC_BTN, "n_clicks"), Input(ID_OPTIMIZE_BTN, "n_clicks")],
    [
        State(STORE_UTILITY, "data"),
        State(STORE_EAF, "data"),
        State(STORE_BESS, "data"),
        State(STORE_FINANCIAL, "data"),
    ],
    prevent_initial_call=True,
)
def validate_inputs_advanced(
    calc_clicks, opt_clicks, utility_params, eaf_params, bess_params, fin_params
):
    triggered_id = ctx.triggered_id if ctx.triggered_id else "initial"
    # Only perform validation if a calculation or optimization was triggered
    is_calc_attempt = triggered_id in [ID_CALC_BTN, ID_OPTIMIZE_BTN] and (
        calc_clicks > 0 or opt_clicks > 0
    )

    if not is_calc_attempt:
        return "", False, False  # No errors, validation closed, calc error closed

    errors = []

    # Helper for safe conversion during validation
    def safe_float(value, default=None):  # Default to None to check existence
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return None  # Indicate conversion failure

    # Utility Validation
    if not utility_params or not isinstance(utility_params, dict):
        errors.append("Utility parameters missing.")
    else:
        rates = utility_params.get(KEY_ENERGY_RATES, {})
        if safe_float(rates.get("off_peak")) is None or rates.get("off_peak", 0) < 0:
            errors.append("Invalid Off-Peak Rate.")
        if safe_float(rates.get("mid_peak")) is None or rates.get("mid_peak", 0) < 0:
            errors.append("Invalid Mid-Peak Rate.")
        if safe_float(rates.get("peak")) is None or rates.get("peak", 0) < 0:
            errors.append("Invalid Peak Rate.")
        if (
            safe_float(utility_params.get(KEY_DEMAND_CHARGE)) is None
            or utility_params.get(KEY_DEMAND_CHARGE, 0) < 0
        ):
            errors.append("Invalid Demand Charge.")

    # EAF Validation
    if not eaf_params or not isinstance(eaf_params, dict):
        errors.append("EAF parameters missing.")
    else:
        if (
            safe_float(eaf_params.get(KEY_EAF_SIZE)) is None
            or eaf_params.get(KEY_EAF_SIZE, 0) <= 0
        ):
            errors.append("EAF Size must be positive.")
        if (
            safe_float(eaf_params.get(KEY_GRID_CAP)) is None
            or eaf_params.get(KEY_GRID_CAP, 0) <= 0
        ):
            errors.append("Grid Capacity must be positive.")
        if (
            safe_float(eaf_params.get(KEY_CYCLES_PER_DAY)) is None
            or eaf_params.get(KEY_CYCLES_PER_DAY, 0) <= 0
        ):
            errors.append("Cycles per Day must be positive.")
        if (
            safe_float(eaf_params.get(KEY_CYCLE_DURATION)) is None
            or eaf_params.get(KEY_CYCLE_DURATION, 0) <= 0
        ):
            errors.append("Cycle Duration must be positive.")
        if safe_float(eaf_params.get(KEY_DAYS_PER_YEAR)) is None or not (
            0 < eaf_params.get(KEY_DAYS_PER_YEAR, 0) <= 366
        ):
            errors.append("Operating Days must be between 1 and 366.")

    # BESS Validation
    if not bess_params or not isinstance(bess_params, dict):
        errors.append("BESS parameters missing.")
    else:
        if (
            safe_float(bess_params.get(KEY_CAPACITY)) is None
            or bess_params.get(KEY_CAPACITY, 0) <= 0
        ):
            errors.append("BESS Capacity must be positive.")
        if (
            safe_float(bess_params.get(KEY_POWER_MAX)) is None
            or bess_params.get(KEY_POWER_MAX, 0) <= 0
        ):
            errors.append("BESS Power must be positive.")
        if safe_float(bess_params.get(KEY_RTE)) is None or not (
            0 < bess_params.get(KEY_RTE, 0) <= 100
        ):
            errors.append("BESS RTE must be between 0% and 100%.")

    # Financial Validation
    if not fin_params or not isinstance(fin_params, dict):
        errors.append("Financial parameters missing.")
    else:
        if safe_float(fin_params.get(KEY_WACC)) is None or not (
            0 <= fin_params.get(KEY_WACC, 0) <= 1
        ):
            errors.append("WACC must be between 0% and 100%.")
        if (
            safe_float(fin_params.get(KEY_LIFESPAN)) is None
            or fin_params.get(KEY_LIFESPAN, 0) <= 0
        ):
            errors.append("Project Lifespan must be positive.")
        if safe_float(fin_params.get(KEY_TAX_RATE)) is None or not (
            0 <= fin_params.get(KEY_TAX_RATE, 0) <= 1
        ):
            errors.append("Tax Rate must be between 0% and 100%.")
        if safe_float(fin_params.get(KEY_INFLATION)) is None:
            errors.append("Inflation Rate missing or invalid.")
        if (
            safe_float(fin_params.get(KEY_ANCILLARY_REVENUE)) is None
            or fin_params.get(KEY_ANCILLARY_REVENUE, 0) < 0
        ):
            errors.append("Ancillary Revenue cannot be negative.")

        # Debt
        debt_p = fin_params.get(KEY_DEBT_PARAMS, {})
        if safe_float(debt_p.get(KEY_LOAN_PERCENT)) is None or not (
            0 <= debt_p.get(KEY_LOAN_PERCENT, 0) <= 100
        ):
            errors.append("Loan Amount % must be between 0% and 100%.")
        if (
            safe_float(debt_p.get(KEY_LOAN_INTEREST)) is None
            or debt_p.get(KEY_LOAN_INTEREST, 0) < 0
        ):
            errors.append("Loan Interest Rate cannot be negative.")
        if (
            safe_float(debt_p.get(KEY_LOAN_TERM)) is None
            or debt_p.get(KEY_LOAN_TERM, 0) <= 0
        ):
            errors.append("Loan Term must be positive.")

        # Depreciation
        dep_p = fin_params.get(KEY_DEPREC_PARAMS, {})
        if dep_p.get(KEY_MACRS_SCHEDULE) not in MACRS_TABLES:
            errors.append("Invalid MACRS Schedule selected.")

        # Degradation
        deg_p = fin_params.get(KEY_DEGRAD_PARAMS, {})
        if (
            safe_float(deg_p.get(KEY_DEGRAD_CAP_YR)) is None
            or deg_p.get(KEY_DEGRAD_CAP_YR, 0) < 0
        ):
            errors.append("Capacity Degradation Rate cannot be negative.")
        if (
            safe_float(deg_p.get(KEY_DEGRAD_RTE_YR)) is None
            or deg_p.get(KEY_DEGRAD_RTE_YR, 0) < 0
        ):
            errors.append("RTE Degradation Rate cannot be negative.")
        if safe_float(deg_p.get(KEY_REPL_THRESH)) is None or not (
            0 < deg_p.get(KEY_REPL_THRESH, 0) <= 100
        ):
            errors.append("Replacement Threshold must be between 0% and 100%.")

    output_elements = []
    is_open = False
    calc_error_open = False  # Keep calculation error closed if validation fails
    if errors:
        output_elements.append(html.H5("Validation Errors:", className="text-danger"))
        output_elements.append(html.Ul([html.Li(e) for e in errors]))
        is_open = True
    return output_elements, is_open, calc_error_open


# --- Main Calculation Callback ---
@app.callback(
    [
        Output(ID_RESULTS_OUTPUT, "children"),
        Output(STORE_RESULTS, "data"),
        Output(ID_CALCULATION_ERR, "children"),
        Output(ID_CALCULATION_ERR, "is_open", allow_duplicate=True),
    ],
    Input(ID_CALC_BTN, "n_clicks"),
    [
        State(STORE_EAF, "data"),
        State(STORE_UTILITY, "data"),
        State(STORE_FINANCIAL, "data"),
        State(STORE_INCENTIVE, "data"),
        State(ID_VALIDATION_ERR, "is_open"),
        # Get BESS parameters directly from UI components
        State(ID_BESS_CAPACITY, "value"),
        State(ID_BESS_POWER, "value"),
        State(ID_BESS_TECH_DROPDOWN, "value"),
        State(ID_BESS_SB_BOS_COST, "value"),
        State(ID_BESS_PCS_COST, "value"),
        State(ID_BESS_EPC_COST, "value"),
        State(ID_BESS_SYS_INT_COST, "value"),
        State(ID_BESS_FIXED_OM, "value"),
        State(ID_BESS_OM_KWHR_YR, "value"),
        State(ID_BESS_RTE, "value"),
        State(ID_BESS_INSURANCE, "value"),
        State(ID_BESS_DISCONNECT_COST, "value"),
        State(ID_BESS_RECYCLING_COST, "value"),
        State(ID_BESS_CYCLE_LIFE, "value"),
        State(ID_BESS_DOD, "value"),
        State(ID_BESS_CALENDAR_LIFE, "value"),
        State(ID_BESS_EXAMPLE_PRODUCT, "children"),
    ],
    prevent_initial_call=True,
)
def display_advanced_calculation_results(
    n_clicks,
    eaf_params,
    utility_params,
    financial_params,
    incentive_params,
    validation_is_open,
    # BESS UI State values
    ui_capacity,
    ui_power,
    ui_technology,
    ui_sb_bos_cost,
    ui_pcs_cost,
    ui_epc_cost,
    ui_sys_int_cost,
    ui_fixed_om,
    ui_om_kwhyr,
    ui_rte,
    ui_insurance,
    ui_disconnect_cost,
    ui_recycling_cost,
    ui_cycle_life,
    ui_dod,
    ui_calendar_life,
    ui_example_product,
):

    results_output = html.Div(
        "Click 'Calculate Results' to generate the analysis.",
        className="text-center text-muted",
    )
    stored_data = {}
    error_output = ""
    error_open = False

    # 1. Check if button was clicked
    if n_clicks is None or n_clicks == 0:
        return results_output, stored_data, error_output, error_open

    # 2. Check if validation errors are currently displayed
    if validation_is_open:
        error_output = html.Div(
            [
                html.H5(
                    "Cannot Calculate - Validation Errors Exist",
                    className="text-danger",
                ),
                html.P("Please fix errors in the parameters tabs before calculating."),
            ]
        )
        error_open = True
        # Return current results (or default message), empty stored data, error message
        return dash.no_update, dash.no_update, error_output, error_open

    # 3. Check for missing essential params from stores
    if not all([eaf_params, utility_params, financial_params, incentive_params]):
        error_output = html.Div(
            [
                html.H5("Internal Error", className="text-danger"),
                html.P(
                    "Could not retrieve EAF/Utility/Financial/Incentive parameters. Try reloading."
                ),
            ]
        )
        error_open = True
        return results_output, stored_data, error_output, error_open

    # 4. Construct bess_params dictionary from UI State values
    # Use the same safe conversion logic as in update_bess_params_store
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def safe_int(value, default=0):
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    # Start with complete defaults for the selected technology
    effective_tech = (
        ui_technology
        if ui_technology and ui_technology in bess_technology_data
        else "LFP"
    )
    bess_params = bess_technology_data.get(effective_tech, {}).copy()

    # Update with UI state values, ensuring all keys are present
    bess_params[KEY_CAPACITY] = safe_float(ui_capacity, 0.001)
    bess_params[KEY_POWER_MAX] = safe_float(ui_power, 0.001)
    bess_params[KEY_TECH] = effective_tech
    bess_params[KEY_SB_BOS_COST] = safe_float(
        ui_sb_bos_cost, bess_params.get(KEY_SB_BOS_COST, 0)
    )
    bess_params[KEY_PCS_COST] = safe_float(
        ui_pcs_cost, bess_params.get(KEY_PCS_COST, 0)
    )
    bess_params[KEY_EPC_COST] = safe_float(
        ui_epc_cost, bess_params.get(KEY_EPC_COST, 0)
    )
    bess_params[KEY_SYS_INT_COST] = safe_float(
        ui_sys_int_cost, bess_params.get(KEY_SYS_INT_COST, 0)
    )
    bess_params[KEY_RTE] = safe_float(ui_rte, bess_params.get(KEY_RTE, 0))
    bess_params[KEY_INSURANCE] = safe_float(
        ui_insurance, bess_params.get(KEY_INSURANCE, 0)
    )
    bess_params[KEY_DISCONNECT_COST] = safe_float(
        ui_disconnect_cost, bess_params.get(KEY_DISCONNECT_COST, 0)
    )
    bess_params[KEY_RECYCLING_COST] = safe_float(
        ui_recycling_cost, bess_params.get(KEY_RECYCLING_COST, 0)
    )
    bess_params[KEY_CYCLE_LIFE] = safe_int(
        ui_cycle_life, bess_params.get(KEY_CYCLE_LIFE, 1000)
    )
    bess_params[KEY_DOD] = safe_float(ui_dod, bess_params.get(KEY_DOD, 100))
    bess_params[KEY_CALENDAR_LIFE] = safe_int(
        ui_calendar_life, bess_params.get(KEY_CALENDAR_LIFE, 10)
    )
    bess_params[KEY_EXAMPLE_PRODUCT] = ui_example_product

    # CRITICAL: Always include both O&M values from UI State
    bess_params[KEY_FIXED_OM] = safe_float(
        ui_fixed_om, bess_params.get(KEY_FIXED_OM, 0)
    )
    bess_params[KEY_OM_KWHR_YR] = safe_float(
        ui_om_kwhyr, bess_params.get(KEY_OM_KWHR_YR, 0)
    )

    # Ensure the final dict is complete using the helper
    bess_params = ensure_bess_params_complete(bess_params)

    # 5. Perform Calculations
    try:
        # Perform ADVANCED Calculations
        incentive_results = calculate_incentives(bess_params, incentive_params)
        financial_metrics = calculate_financial_metrics_advanced(
            bess_params, financial_params, eaf_params, utility_params, incentive_results
        )

        # Format Results for Display
        def fmt_p(v):
            return (
                f"{v:.1%}"
                if pd.notna(v) and isinstance(v, (int, float)) and abs(v) <= 10
                else (f"{v:,.0%}" if pd.notna(v) else "N/A")
            )

        def fmt_y(v):
            return (
                "Never"
                if pd.isna(v) or v == float("inf")
                else ("< 0 yrs" if v < 0 else f"{v:.1f} yrs")
            )

        def fmt_n(v, decimals=0):
            return (
                f"{v:,.{decimals}f}"
                if pd.notna(v) and isinstance(v, (int, float))
                else "N/A"
            )

        # Summary Metrics Card
        summary_card = dbc.Card(
            [
                dbc.CardHeader("Summary Financial Metrics"),
                dbc.CardBody(
                    html.Table(
                        [
                            html.Tr(
                                [
                                    html.Td("Project NPV"),
                                    html.Td(
                                        fmt_c(financial_metrics.get("project_npv"))
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Project IRR"),
                                    html.Td(
                                        fmt_p(financial_metrics.get("project_irr"))
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Equity NPV"),
                                    html.Td(fmt_c(financial_metrics.get("equity_npv"))),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Equity IRR"),
                                    html.Td(fmt_p(financial_metrics.get("equity_irr"))),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Payback Period (Equity)"),
                                    html.Td(
                                        fmt_y(financial_metrics.get("payback_years"))
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Levelized Cost of Storage (LCOS)"),
                                    html.Td(
                                        f"{fmt_c(financial_metrics.get('lcos'))} / MWh discharged"
                                        if pd.notna(financial_metrics.get("lcos"))
                                        else "N/A"
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Avg. Debt Service Coverage Ratio (DSCR)"),
                                    html.Td(
                                        fmt_n(financial_metrics.get("avg_dscr"), 2)
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Min. Debt Service Coverage Ratio (DSCR)"),
                                    html.Td(
                                        fmt_n(financial_metrics.get("min_dscr"), 2)
                                    ),
                                ]
                            ),
                        ],
                        className="table table-sm table-striped",
                    )
                ),
            ],
            className="mb-4",
        )

        # Cost Breakdown Card
        cost_breakdown_card = dbc.Card(
            [
                dbc.CardHeader("Cost & Incentive Summary"),
                dbc.CardBody(
                    html.Table(
                        [
                            html.Tr(
                                [
                                    html.Td("Total Initial Gross Cost"),
                                    html.Td(
                                        fmt_c(
                                            financial_metrics.get("total_initial_cost")
                                        )
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Total Incentives Received"),
                                    html.Td(
                                        fmt_c(incentive_results.get("total_incentive"))
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Net Initial Cost (Before Debt)"),
                                    html.Td(
                                        fmt_c(financial_metrics.get("net_initial_cost"))
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Equity Investment Required"),
                                    html.Td(
                                        fmt_c(
                                            financial_metrics.get("equity_investment")
                                        )
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Initial Annual O&M Cost (Yr 1)"),
                                    html.Td(
                                        fmt_c(
                                            financial_metrics.get(
                                                "initial_om_cost_year1"
                                            )
                                        )
                                    ),
                                ]
                            ),
                            html.Tr(
                                [
                                    html.Td("Estimated Annual Discharge (Yr 1)"),
                                    html.Td(
                                        f"{fmt_n(financial_metrics.get('total_annual_discharge_mwh_yr1'), 0)} MWh"
                                    ),
                                ]
                            ),
                        ],
                        className="table table-sm table-striped",
                    )
                ),
            ],
            className="mb-4",
        )

        # Cash Flow Plot
        years_list = list(
            range(len(financial_metrics.get("project_cash_flows", [])))
        )  # Year 0, 1, 2...
        project_cf = financial_metrics.get("project_cash_flows", [])
        equity_cf = financial_metrics.get("equity_cash_flows", [])

        cf_fig = go.Figure()
        if project_cf:
            cf_fig.add_trace(
                go.Bar(
                    x=years_list,
                    y=project_cf,
                    name="Project Cash Flow",
                    marker_color="skyblue",
                )
            )
        if equity_cf:
            cf_fig.add_trace(
                go.Bar(
                    x=years_list,
                    y=equity_cf,
                    name="Equity Cash Flow",
                    marker_color="lightcoral",
                )
            )

        cf_fig.update_layout(
            title="Project & Equity Cash Flows Over Time",
            xaxis_title="Year",
            yaxis_title="Cash Flow ($)",
            yaxis_tickformat="$,.0f",
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            margin=dict(l=40, r=20, t=40, b=40),
            barmode="group",
        )

        cf_graph = dcc.Graph(figure=cf_fig, className="mb-4")

        # Detailed Cash Flow Table
        detailed_cf_data = financial_metrics.get("detailed_cash_flows", [])
        cashflow_table_div = html.Div("No detailed cash flow data available.")
        if detailed_cf_data:
            df_cf = pd.DataFrame(detailed_cf_data)
            # Format columns for display in the DataTable
            df_cf_display = df_cf.copy()
            for col in df_cf_display.columns:
                if col == "Year":
                    df_cf_display[col] = df_cf_display[col].apply(lambda x: fmt_n(x, 0))
                elif (
                    "Cost" in col
                    or "Savings" in col
                    or "Revenue" in col
                    or "Payment" in col
                    or "Income" in col
                    or "Taxes" in col
                    or "Cash Flow" in col
                    or "Investment" in col
                    or "Balance" in col
                ):
                    df_cf_display[col] = df_cf_display[col].apply(lambda x: fmt_c(x, 0))
                elif "Capacity (%)" in col:
                    df_cf_display[col] = df_cf_display[col].apply(
                        lambda x: f"{fmt_n(x, 1)}%"
                    )

            cashflow_table = dash_table.DataTable(
                id="cashflow-datatable",
                data=df_cf_display.to_dict("records"),
                columns=[{"name": i, "id": i} for i in df_cf_display.columns],
                page_size=10,
                sort_action="native",
                filter_action="native",
                export_format="csv",
                export_headers="display",
                style_cell={
                    "textAlign": "right",
                    "padding": "5px",
                    "fontFamily": "sans-serif",
                },
                style_header={
                    "fontWeight": "bold",
                    "backgroundColor": "#f0f0f0",
                    "textAlign": "center",
                },
                style_table={"overflowX": "auto", "minWidth": "100%"},
                style_cell_conditional=[
                    {"if": {"column_id": "Year"}, "textAlign": "center"},
                    {"if": {"column_id": "BESS Capacity (%)"}, "textAlign": "center"},
                ],
            )
            cashflow_table_div = html.Div(
                [
                    dbc.Button(
                        "Toggle Detailed Cash Flow Table",
                        id=ID_RESULTS_TABLES_TOGGLE_BTN,
                        color="secondary",
                        size="sm",
                        className="mb-3",
                    ),
                    dbc.Collapse(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5(
                                        "Detailed Annual Cash Flow", className="mb-3"
                                    ),
                                    cashflow_table,
                                ]
                            )
                        ),
                        id=ID_RESULTS_TABLES_COLLAPSE,
                        is_open=False,  # Start collapsed
                    ),
                ]
            )

        # Technology Comparison Table (using current BESS size)
        tech_comp_table = create_technology_comparison_table(
            bess_params.get(KEY_TECH, "LFP"),
            bess_params.get(KEY_CAPACITY, 0),
            bess_params.get(KEY_POWER_MAX, 0),
        )
        tech_comp_card = dbc.Card(
            [
                dbc.CardHeader("Technology Comparison (at Current Size)"),
                dbc.CardBody(tech_comp_table),
            ],
            className="mb-4",
        )

        results_output = html.Div(
            [
                html.H3("Financial Analysis Results", className="mb-4 text-center"),
                dbc.Row(
                    [
                        dbc.Col(summary_card, md=6),
                        dbc.Col(cost_breakdown_card, md=6),
                    ]
                ),
                cf_graph,
                cashflow_table_div,
                tech_comp_card,
            ]
        )

        # Store raw (unformatted) results for potential future use
        stored_data = {"financials": financial_metrics, "incentives": incentive_results}
        error_output = ""
        error_open = False

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"ERROR during calculation display: {e}\n{tb_str}")
        error_output = html.Div(
            [
                html.H5("Calculation Display Error", className="text-danger"),
                html.P("An error occurred preparing results:"),
                html.Pre(f"{type(e).__name__}: {str(e)}"),
                html.Details([html.Summary("Traceback"), html.Pre(tb_str)]),
                html.Details(
                    [
                        html.Summary("Constructed BESS Params Used"),
                        html.Pre(pprint.pformat(bess_params)),
                    ]
                ),
            ]
        )
        error_open = True
        results_output = html.Div(
            "Could not generate results display due to an internal error.",
            className="text-danger text-center",
        )
        stored_data = {}


    return results_output, stored_data, error_output, error_open
# Section 12
# --- Optimization Callback ---
@app.callback(
    [Output(ID_OPTIMIZE_OUTPUT, "children"), Output(STORE_OPTIMIZATION, "data")],
    Input(ID_OPTIMIZE_BTN, "n_clicks"),
    [
        State(STORE_EAF, "data"),
        State(STORE_UTILITY, "data"),
        State(STORE_FINANCIAL, "data"),
        State(STORE_INCENTIVE, "data"),
        State(ID_VALIDATION_ERR, "is_open"),  # Check validation status
        # Get BESS parameters directly from UI to form the BASE for optimization
        State(ID_BESS_TECH_DROPDOWN, "value"),
        State(ID_BESS_SB_BOS_COST, "value"),
        State(ID_BESS_PCS_COST, "value"),
        State(ID_BESS_EPC_COST, "value"),
        State(ID_BESS_SYS_INT_COST, "value"),
        State(ID_BESS_FIXED_OM, "value"),
        State(ID_BESS_OM_KWHR_YR, "value"),
        State(ID_BESS_RTE, "value"),
        State(ID_BESS_INSURANCE, "value"),
        State(ID_BESS_DISCONNECT_COST, "value"),
        State(ID_BESS_RECYCLING_COST, "value"),
        State(ID_BESS_CYCLE_LIFE, "value"),
        State(ID_BESS_DOD, "value"),
        State(ID_BESS_CALENDAR_LIFE, "value"),
        State(ID_BESS_EXAMPLE_PRODUCT, "children"),
    ],
    prevent_initial_call=True,
)
def display_advanced_optimization_results(
    n_clicks,
    eaf_params,
    utility_params,
    financial_params,
    incentive_params,
    validation_is_open,
    # BESS UI State values to form the base
    ui_technology,
    ui_sb_bos_cost,
    ui_pcs_cost,
    ui_epc_cost,
    ui_sys_int_cost,
    ui_fixed_om,
    ui_om_kwhyr,
    ui_rte,
    ui_insurance,
    ui_disconnect_cost,
    ui_recycling_cost,
    ui_cycle_life,
    ui_dod,
    ui_calendar_life,
    ui_example_product,
):
    """Triggers ADVANCED optimization calculation and displays results."""
    opt_output = html.Div(
        "Click 'Optimize Battery Size' to run the analysis.",
        className="text-center text-muted",
    )
    opt_stored_data = {}

    if n_clicks is None or n_clicks == 0:
        return opt_output, opt_stored_data

    if validation_is_open:
        opt_output = dbc.Alert(
            [
                html.H4(
                    "Cannot Optimize - Validation Errors Exist", className="text-danger"
                ),
                html.P("Fix errors before optimizing."),
            ],
            color="danger",
        )
        return opt_output, opt_stored_data

    if not all([eaf_params, utility_params, financial_params, incentive_params]):
        opt_output = dbc.Alert(
            "Cannot Optimize - Missing EAF/Utility/Financial/Incentive parameters.",
            color="danger",
        )
        return opt_output, opt_stored_data

    # Construct the BASE bess_params dictionary from UI State values
    # This dictionary will be copied and modified (Cap/Power) inside the optimization loop
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def safe_int(value, default=0):
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    effective_tech = (
        ui_technology
        if ui_technology and ui_technology in bess_technology_data
        else "LFP"
    )
    bess_base_params = bess_technology_data.get(effective_tech, {}).copy()

    # Update with UI state values
    bess_base_params[KEY_TECH] = effective_tech
    bess_base_params[KEY_SB_BOS_COST] = safe_float(
        ui_sb_bos_cost, bess_base_params.get(KEY_SB_BOS_COST, 0)
    )
    bess_base_params[KEY_PCS_COST] = safe_float(
        ui_pcs_cost, bess_base_params.get(KEY_PCS_COST, 0)
    )
    bess_base_params[KEY_EPC_COST] = safe_float(
        ui_epc_cost, bess_base_params.get(KEY_EPC_COST, 0)
    )
    bess_base_params[KEY_SYS_INT_COST] = safe_float(
        ui_sys_int_cost, bess_base_params.get(KEY_SYS_INT_COST, 0)
    )
    bess_base_params[KEY_RTE] = safe_float(ui_rte, bess_base_params.get(KEY_RTE, 0))
    bess_base_params[KEY_INSURANCE] = safe_float(
        ui_insurance, bess_base_params.get(KEY_INSURANCE, 0)
    )
    bess_base_params[KEY_DISCONNECT_COST] = safe_float(
        ui_disconnect_cost, bess_base_params.get(KEY_DISCONNECT_COST, 0)
    )
    bess_base_params[KEY_RECYCLING_COST] = safe_float(
        ui_recycling_cost, bess_base_params.get(KEY_RECYCLING_COST, 0)
    )
    bess_base_params[KEY_CYCLE_LIFE] = safe_int(
        ui_cycle_life, bess_base_params.get(KEY_CYCLE_LIFE, 1000)
    )
    bess_base_params[KEY_DOD] = safe_float(ui_dod, bess_base_params.get(KEY_DOD, 100))
    bess_base_params[KEY_CALENDAR_LIFE] = safe_int(
        ui_calendar_life, bess_base_params.get(KEY_CALENDAR_LIFE, 10)
    )
    bess_base_params[KEY_EXAMPLE_PRODUCT] = ui_example_product
    bess_base_params[KEY_FIXED_OM] = safe_float(
        ui_fixed_om, bess_base_params.get(KEY_FIXED_OM, 0)
    )
    bess_base_params[KEY_OM_KWHR_YR] = safe_float(
        ui_om_kwhyr, bess_base_params.get(KEY_OM_KWHR_YR, 0)
    )
    # Capacity and Power will be set inside the optimization loop
    bess_base_params[KEY_CAPACITY] = 0  # Placeholder
    bess_base_params[KEY_POWER_MAX] = 0  # Placeholder

    # Ensure the base dict is complete
    bess_base_params = ensure_bess_params_complete(bess_base_params)

    try:
        opt_results = optimize_battery_size_advanced(
            eaf_params,
            utility_params,
            financial_params,
            incentive_params,
            bess_base_params,
        )
        opt_stored_data = opt_results  # Store the raw results

        if opt_results and opt_results.get("best_capacity") is not None:
            best_metrics = opt_results.get("best_metrics", {})
            metric_key = opt_results.get("optimized_metric", "equity_irr")
            metric_name = metric_key.replace("_", " ").title()
            best_metric_val = opt_results.get(f"best_{metric_key}", float("nan"))

            # Use same formatters
            def fmt_p(v):
                return (
                    f"{v:.1%}"
                    if pd.notna(v) and isinstance(v, (int, float)) and abs(v) <= 10
                    else (f"{v:,.0%}" if pd.notna(v) else "N/A")
                )

            def fmt_y(v):
                return (
                    "Never"
                    if pd.isna(v) or v == float("inf")
                    else ("< 0 yrs" if v < 0 else f"{v:.1f} yrs")
                )

            def fmt_n(v, decimals=0):
                return (
                    f"{v:,.{decimals}f}"
                    if pd.notna(v) and isinstance(v, (int, float))
                    else "N/A"
                )

            best_summary = dbc.Card(
                [
                    dbc.CardHeader(
                        f"Optimal Size Found (Max {metric_name}) - Tech: {bess_base_params.get(KEY_TECH, 'N/A')}"
                    ),
                    dbc.CardBody(
                        html.Table(
                            [
                                html.Tr(
                                    [
                                        html.Td("Capacity (MWh)"),
                                        html.Td(fmt_n(opt_results["best_capacity"], 1)),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Power (MW)"),
                                        html.Td(fmt_n(opt_results["best_power"], 1)),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td(f"Resulting {metric_name}"),
                                        html.Td(
                                            fmt_p(best_metric_val)
                                            if "irr" in metric_key
                                            else fmt_c(best_metric_val)
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting Project IRR"),
                                        html.Td(fmt_p(best_metrics.get("project_irr"))),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting Equity IRR"),
                                        html.Td(fmt_p(best_metrics.get("equity_irr"))),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting Payback"),
                                        html.Td(
                                            fmt_y(best_metrics.get("payback_years"))
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting LCOS ($/MWh)"),
                                        html.Td(fmt_c(best_metrics.get("lcos"))),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Initial Equity Investment"),
                                        html.Td(
                                            fmt_c(best_metrics.get("equity_investment"))
                                        ),
                                    ]
                                ),
                            ],
                            className="table table-sm table-striped",
                        )
                    ),
                ],
                className="mb-4",
            )

            all_results_df = pd.DataFrame(opt_results.get("all_results", []))
            table_section = html.Div("No optimization results data.")
            if not all_results_df.empty:
                # Define display columns and rename
                display_cols = {
                    "capacity": "Capacity (MWh)",
                    "power": "Power (MW)",
                    metric_key: metric_name,  # Use the dynamic metric name
                    "project_npv": "Project NPV ($)",
                    "equity_irr": "Equity IRR (%)",
                    "payback_years": "Payback (Yrs)",
                    "lcos": "LCOS ($/MWh)",
                    "equity_investment": "Equity Invest ($)",
                }
                # Filter and rename columns that exist in the dataframe
                cols_to_display = {
                    k: v for k, v in display_cols.items() if k in all_results_df.columns
                }
                all_results_df_display = all_results_df[
                    list(cols_to_display.keys())
                ].copy()
                all_results_df_display.rename(columns=cols_to_display, inplace=True)

                # Apply formatting using the *new* column names
                if "Capacity (MWh)" in all_results_df_display.columns:
                    all_results_df_display["Capacity (MWh)"] = all_results_df_display[
                        "Capacity (MWh)"
                    ].map("{:.1f}".format)
                if "Power (MW)" in all_results_df_display.columns:
                    all_results_df_display["Power (MW)"] = all_results_df_display[
                        "Power (MW)"
                    ].map("{:.1f}".format)
                for col in ["Project NPV ($)", "LCOS ($/MWh)", "Equity Invest ($)"]:
                    if col in all_results_df_display.columns:
                        all_results_df_display[col] = all_results_df_display[col].apply(
                            fmt_c
                        )
                for col in [
                    "Equity IRR (%)",
                    metric_name,
                ]:  # Format metric based on type
                    if col in all_results_df_display.columns:
                        if "IRR" in col:
                            all_results_df_display[col] = all_results_df_display[
                                col
                            ].apply(fmt_p)
                        elif "NPV" in col:
                            all_results_df_display[col] = all_results_df_display[
                                col
                            ].apply(fmt_c)
                if "Payback (Yrs)" in all_results_df_display.columns:
                    all_results_df_display["Payback (Yrs)"] = all_results_df_display[
                        "Payback (Yrs)"
                    ].apply(fmt_y)

                all_results_table = dash_table.DataTable(
                    data=all_results_df_display.to_dict("records"),
                    columns=[
                        {"name": i, "id": i} for i in all_results_df_display.columns
                    ],
                    page_size=10,
                    sort_action="native",
                    filter_action="native",
                    style_cell={"textAlign": "right", "fontFamily": "sans-serif"},
                    style_header={"fontWeight": "bold", "textAlign": "center"},
                    style_table={"overflowX": "auto", "minWidth": "100%"},
                    style_cell_conditional=[
                        {"if": {"column_id": c}, "textAlign": "left"}
                        for c in ["Capacity (MWh)", "Power (MW)"]
                    ],
                )
                table_section = html.Div(
                    [
                        html.H4("All Tested Combinations", className="mt-4 mb-3"),
                        all_results_table,
                    ]
                )

            opt_output = html.Div(
                [
                    html.H3(
                        "Advanced Battery Sizing Optimization Results", className="mb-4"
                    ),
                    best_summary,
                    table_section,
                ]
            )
        else:
            opt_output = dbc.Alert(
                [
                    html.H4(
                        "Optimization Failed or No Viable Solution",
                        className="text-warning",
                    ),
                    html.P(
                        "Could not find an optimal battery size based on the selected criteria and parameter ranges."
                    ),
                ],
                color="warning",
            )

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"ERROR during optimization display: {e}\n{tb_str}")
        opt_output = dbc.Alert(
            [
                html.H5("Optimization Display Error", className="text-danger"),
                html.P("An error occurred during optimization:"),
                html.Pre(f"{type(e).__name__}: {str(e)}"),
                html.Details([html.Summary("Traceback"), html.Pre(tb_str)]),
            ],
            color="danger",
        )
        opt_stored_data = {}

    return opt_output, opt_stored_data


# --- Toggle results tables visibility ---
@app.callback(
    Output(ID_RESULTS_TABLES_COLLAPSE, "is_open"),
    Input(ID_RESULTS_TABLES_TOGGLE_BTN, "n_clicks"),
    State(ID_RESULTS_TABLES_COLLAPSE, "is_open"),
    prevent_initial_call=True,
)
def toggle_results_tables(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


# --- Callbacks for Save/Load Project ---
@app.callback(
    Output(ID_DOWNLOAD_PROJECT_JSON, "data"),
    Input(ID_SAVE_PROJECT_BTN, "n_clicks"),
    [
        State(STORE_EAF, "data"),
        State(STORE_BESS, "data"),
        State(STORE_UTILITY, "data"),
        State(STORE_FINANCIAL, "data"),
        State(STORE_INCENTIVE, "data"),
    ],
    prevent_initial_call=True,
)
def save_project_state(n_clicks, eaf_data, bess_data, util_data, fin_data, inc_data):
    if n_clicks is None:
        return None

    project_state = {
        "version": "1.0_refactored",  # Add versioning
        STORE_EAF: eaf_data,
        STORE_BESS: bess_data,
        STORE_UTILITY: util_data,
        STORE_FINANCIAL: fin_data,
        STORE_INCENTIVE: inc_data,
    }

    # Convert numpy types to standard python types for JSON serialization
    def convert_numpy(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        return obj

    try:
        json_string = json.dumps(project_state, default=convert_numpy, indent=4)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"battery_profitability_{timestamp}.json"
        return dict(content=json_string, filename=filename)
    except Exception as e:
        print(f"Error creating JSON for save: {e}")
        return None


@app.callback(
    [
        Output(STORE_EAF, "data", allow_duplicate=True),
        Output(STORE_BESS, "data", allow_duplicate=True),
        Output(STORE_UTILITY, "data", allow_duplicate=True),
        Output(STORE_FINANCIAL, "data", allow_duplicate=True),
        Output(STORE_INCENTIVE, "data", allow_duplicate=True),
        Output(STORE_LOADED_STATE, "data"),  # Trigger downstream updates
        Output(ID_CALCULATION_ERR, "children", allow_duplicate=True),
        Output(ID_CALCULATION_ERR, "is_open", allow_duplicate=True),
    ],
    Input(ID_LOAD_PROJECT_UPLOAD, "contents"),
    State(ID_LOAD_PROJECT_UPLOAD, "filename"),
    prevent_initial_call=True,
)
def load_project_state(contents, filename):
    if contents is None:
        return dash.no_update  # No file uploaded

    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)
    err_msg = ""
    err_open = False
    trigger_data = dash.no_update

    try:
        if filename and "json" in filename.lower():
            loaded_state = json.loads(decoded.decode("utf-8"))
            # Basic validation of loaded structure
            required_keys = [
                STORE_EAF,
                STORE_BESS,
                STORE_UTILITY,
                STORE_FINANCIAL,
                STORE_INCENTIVE,
            ]
            if all(k in loaded_state for k in required_keys):
                print(f"Successfully loaded project state from {filename}")
                # Prepare data to return
                eaf_out = loaded_state[STORE_EAF]
                bess_out = loaded_state[STORE_BESS]
                util_out = loaded_state[STORE_UTILITY]
                fin_out = loaded_state[STORE_FINANCIAL]
                inc_out = loaded_state[STORE_INCENTIVE]
                trigger_data = {
                    "loaded_timestamp": datetime.now().isoformat()
                }  # Trigger downstream UI update
                err_msg = dbc.Alert(
                    f"Successfully loaded '{filename}'", color="success", duration=4000
                )
                err_open = True
                return (
                    eaf_out,
                    bess_out,
                    util_out,
                    fin_out,
                    inc_out,
                    trigger_data,
                    err_msg,
                    err_open,
                )
            else:
                missing_keys = [k for k in required_keys if k not in loaded_state]
                print(
                    f"Error: Loaded JSON '{filename}' missing required store keys: {missing_keys}"
                )
                err_msg = dbc.Alert(
                    f"Error: File '{filename}' is missing required data sections.",
                    color="danger",
                )
                err_open = True
                return (
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    dash.no_update,
                    err_msg,
                    err_open,
                )
        else:
            print(f"Error: Uploaded file '{filename}' is not a JSON file.")
            err_msg = dbc.Alert(
                f"Error: Uploaded file '{filename}' is not a JSON file.", color="danger"
            )
            err_open = True
            return (
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                dash.no_update,
                err_msg,
                err_open,
            )
    except Exception as e:
        print(f"Error processing uploaded file '{filename}': {e}")
        traceback.print_exc()
        err_msg = dbc.Alert(
            f"Error processing file '{filename}': {str(e)}", color="danger"
        )
        err_open = True
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            err_msg,
            err_open,
        )
# Section 13
# --- Callback to Update UI Elements After Load ---
@app.callback(
    [
     # Utility Outputs
     Output(ID_UTILITY_DROPDOWN, "value", allow_duplicate=True), Output(ID_OFF_PEAK, "value", allow_duplicate=True),
     Output(ID_MID_PEAK, "value", allow_duplicate=True), Output(ID_PEAK, "value", allow_duplicate=True),
     Output(ID_DEMAND_CHARGE, "value", allow_duplicate=True), Output(ID_SEASONAL_TOGGLE, "value", allow_duplicate=True),
     Output(ID_TOU_CONTAINER, "children", allow_duplicate=True),
     # EAF Outputs
     Output(ID_EAF_SIZE, "value", allow_duplicate=True), Output(ID_EAF_COUNT, "value", allow_duplicate=True),
     Output(ID_GRID_CAP, "value", allow_duplicate=True), Output(ID_CYCLES_PER_DAY, "value", allow_duplicate=True),
     Output(ID_CYCLE_DURATION, "value", allow_duplicate=True), Output(ID_DAYS_PER_YEAR, "value", allow_duplicate=True),
     # BESS Outputs
     Output(ID_BESS_CAPACITY, "value", allow_duplicate=True), Output(ID_BESS_POWER, "value", allow_duplicate=True),
     Output(ID_BESS_TECH_DROPDOWN, "value", allow_duplicate=True), Output(ID_BESS_SB_BOS_COST, "value", allow_duplicate=True),
     Output(ID_BESS_PCS_COST, "value", allow_duplicate=True), Output(ID_BESS_EPC_COST, "value", allow_duplicate=True),
     Output(ID_BESS_SYS_INT_COST, "value", allow_duplicate=True),
     Output(ID_BESS_RTE, "value", allow_duplicate=True), Output(ID_BESS_INSURANCE, "value", allow_duplicate=True),
     Output(ID_BESS_DISCONNECT_COST, "value", allow_duplicate=True), Output(ID_BESS_RECYCLING_COST, "value", allow_duplicate=True),
     Output(ID_BESS_CYCLE_LIFE, "value", allow_duplicate=True), Output(ID_BESS_DOD, "value", allow_duplicate=True),
     Output(ID_BESS_CALENDAR_LIFE, "value", allow_duplicate=True),
     # Financial Outputs
     Output(ID_WACC, "value", allow_duplicate=True), Output(ID_LIFESPAN, "value", allow_duplicate=True),
     Output(ID_TAX_RATE, "value", allow_duplicate=True), Output(ID_INFLATION_RATE, "value", allow_duplicate=True),
     Output(ID_SALVAGE, "value", allow_duplicate=True), Output(ID_ANCILLARY_REVENUE_INPUT, "value", allow_duplicate=True),
     Output(ID_LOAN_AMOUNT_PERCENT, "value", allow_duplicate=True), Output(ID_LOAN_INTEREST_RATE, "value", allow_duplicate=True),
     Output(ID_LOAN_TERM_YEARS, "value", allow_duplicate=True), Output(ID_MACRS_SCHEDULE, "value", allow_duplicate=True),
     Output(ID_DEGRAD_RATE_CAP_YR, "value", allow_duplicate=True), Output(ID_DEGRAD_RATE_RTE_YR, "value", allow_duplicate=True),
     Output(ID_REPLACEMENT_THRESHOLD, "value", allow_duplicate=True),
     # Incentive Outputs 
     Output(ID_ITC_ENABLED, "value", allow_duplicate=True), Output(ID_ITC_PERCENT, "value", allow_duplicate=True),
     Output("ceic-enabled", "value", allow_duplicate=True), Output("ceic-percentage", "value", allow_duplicate=True),
     Output("bonus-credit-enabled", "value", allow_duplicate=True), Output("bonus-credit-percentage", "value", allow_duplicate=True),
     Output("sgip-enabled", "value", allow_duplicate=True), Output("sgip-amount", "value", allow_duplicate=True),
     Output("ess-enabled", "value", allow_duplicate=True), Output("ess-amount", "value", allow_duplicate=True),
     Output("mabi-enabled", "value", allow_duplicate=True), Output("mabi-amount", "value", allow_duplicate=True),
     Output("cs-enabled", "value", allow_duplicate=True), Output("cs-amount", "value", allow_duplicate=True),
     Output("custom-incentive-enabled", "value", allow_duplicate=True), Output("custom-incentive-type", "value", allow_duplicate=True),
     Output("custom-incentive-amount", "value", allow_duplicate=True), Output("custom-incentive-description", "value", allow_duplicate=True),
     # Add outputs for the seasonal inputs
     Output(ID_WINTER_MULTIPLIER, "value", allow_duplicate=True), Output(ID_SUMMER_MULTIPLIER, "value", allow_duplicate=True),
     Output(ID_SHOULDER_MULTIPLIER, "value", allow_duplicate=True), Output(ID_WINTER_MONTHS, "value", allow_duplicate=True),
     Output(ID_SUMMER_MONTHS, "value", allow_duplicate=True), Output(ID_SHOULDER_MONTHS, "value", allow_duplicate=True),
     # Add outputs for the Opex inputs
     Output(ID_BESS_FIXED_OM, "value", allow_duplicate=True), Output(ID_BESS_OM_KWHR_YR, "value", allow_duplicate=True),
     ],
    Input(STORE_LOADED_STATE, "data"),  # Triggered when state is loaded
    [State(STORE_EAF, "data"), State(STORE_BESS, "data"), State(STORE_UTILITY, "data"),
     State(STORE_FINANCIAL, "data"), State(STORE_INCENTIVE, "data")],
    prevent_initial_call=True,
)
def update_ui_from_loaded_state(
    load_trigger, eaf_data, bess_data, util_data, fin_data, inc_data
):
    if load_trigger is None or not all(
        [eaf_data, bess_data, util_data, fin_data, inc_data]
    ):
        # Don't update if trigger is null or any data store is missing
        return [dash.no_update] * 60  # Match number of outputs

    print("Updating UI elements from loaded state...")

    # --- Safely extract values from loaded data, using defaults as fallbacks ---

    # Utility UI
    # Find utility provider name based on loaded rates
    util_provider = "Custom Utility"  # Default
    for name, data in utility_rates.items():
        # Basic check: compare demand charge and peak rate
        if data.get(KEY_DEMAND_CHARGE) == util_data.get(KEY_DEMAND_CHARGE) and data.get(
            KEY_ENERGY_RATES, {}
        ).get("peak") == util_data.get(KEY_ENERGY_RATES, {}).get("peak"):
            util_provider = name
            break
    off_peak = util_data.get(KEY_ENERGY_RATES, {}).get(
        "off_peak", default_utility_params[KEY_ENERGY_RATES]["off_peak"]
    )
    mid_peak = util_data.get(KEY_ENERGY_RATES, {}).get(
        "mid_peak", default_utility_params[KEY_ENERGY_RATES]["mid_peak"]
    )
    peak_val = util_data.get(KEY_ENERGY_RATES, {}).get(
        "peak", default_utility_params[KEY_ENERGY_RATES]["peak"]
    )
    demand = util_data.get(KEY_DEMAND_CHARGE, default_utility_params[KEY_DEMAND_CHARGE])
    seasonal_tog = ["enabled"] if util_data.get(KEY_SEASONAL, False) else []
    tou_elements = generate_tou_ui_elements(
        util_data.get(KEY_TOU_RAW, default_utility_params[KEY_TOU_RAW])
    )

    # Seasonal inputs values
    winter_mult_ui = util_data.get(
        KEY_WINTER_MULT, default_utility_params[KEY_WINTER_MULT]
    )
    summer_mult_ui = util_data.get(
        KEY_SUMMER_MULT, default_utility_params[KEY_SUMMER_MULT]
    )
    shoulder_mult_ui = util_data.get(
        KEY_SHOULDER_MULT, default_utility_params[KEY_SHOULDER_MULT]
    )
    winter_m_ui = ",".join(
        map(
            str,
            util_data.get(KEY_WINTER_MONTHS, default_utility_params[KEY_WINTER_MONTHS]),
        )
    )
    summer_m_ui = ",".join(
        map(
            str,
            util_data.get(KEY_SUMMER_MONTHS, default_utility_params[KEY_SUMMER_MONTHS]),
        )
    )
    shoulder_m_ui = ",".join(
        map(
            str,
            util_data.get(
                KEY_SHOULDER_MONTHS, default_utility_params[KEY_SHOULDER_MONTHS]
            ),
        )
    )

    # EAF UI
    eaf_size = eaf_data.get(KEY_EAF_SIZE, nucor_mills["Custom"][KEY_EAF_SIZE])
    eaf_count = eaf_data.get("eaf_count", nucor_mills["Custom"]["eaf_count"])
    grid_cap = eaf_data.get(KEY_GRID_CAP, nucor_mills["Custom"][KEY_GRID_CAP])
    cycles_day = eaf_data.get(
        KEY_CYCLES_PER_DAY, nucor_mills["Custom"][KEY_CYCLES_PER_DAY]
    )
    cycle_dur = eaf_data.get(
        KEY_CYCLE_DURATION_INPUT,
        eaf_data.get(KEY_CYCLE_DURATION, nucor_mills["Custom"][KEY_CYCLE_DURATION]),
    )
    days_yr = eaf_data.get(KEY_DAYS_PER_YEAR, nucor_mills["Custom"][KEY_DAYS_PER_YEAR])

    # BESS UI
    bess_cap = bess_data.get(KEY_CAPACITY, default_bess_params_store[KEY_CAPACITY])
    bess_pow = bess_data.get(KEY_POWER_MAX, default_bess_params_store[KEY_POWER_MAX])
    bess_tech = bess_data.get(KEY_TECH, default_bess_params_store[KEY_TECH])
    sb_bos = bess_data.get(KEY_SB_BOS_COST, default_bess_params_store[KEY_SB_BOS_COST])
    pcs = bess_data.get(KEY_PCS_COST, default_bess_params_store[KEY_PCS_COST])
    epc = bess_data.get(KEY_EPC_COST, default_bess_params_store[KEY_EPC_COST])
    sys_int = bess_data.get(
        KEY_SYS_INT_COST, default_bess_params_store[KEY_SYS_INT_COST]
    )
    rte = bess_data.get(KEY_RTE, default_bess_params_store[KEY_RTE])
    ins = bess_data.get(KEY_INSURANCE, default_bess_params_store[KEY_INSURANCE])
    disc = bess_data.get(
        KEY_DISCONNECT_COST, default_bess_params_store[KEY_DISCONNECT_COST]
    )
    recyc = bess_data.get(
        KEY_RECYCLING_COST, default_bess_params_store[KEY_RECYCLING_COST]
    )
    cyc_life = bess_data.get(KEY_CYCLE_LIFE, default_bess_params_store[KEY_CYCLE_LIFE])
    dod = bess_data.get(KEY_DOD, default_bess_params_store[KEY_DOD])
    cal_life = bess_data.get(
        KEY_CALENDAR_LIFE, default_bess_params_store[KEY_CALENDAR_LIFE]
    )

    # Opex inputs values
    fixed_om_ui = bess_data.get(KEY_FIXED_OM, default_bess_params_store[KEY_FIXED_OM])
    om_kwhyr_ui = bess_data.get(
        KEY_OM_KWHR_YR, default_bess_params_store[KEY_OM_KWHR_YR]
    )

    # Financial UI (Convert decimals back to percentages for UI)
    wacc_ui = fin_data.get(KEY_WACC, default_financial_params[KEY_WACC]) * 100.0
    lifespan_ui = fin_data.get(KEY_LIFESPAN, default_financial_params[KEY_LIFESPAN])
    tax_ui = fin_data.get(KEY_TAX_RATE, default_financial_params[KEY_TAX_RATE]) * 100.0
    infl_ui = (
        fin_data.get(KEY_INFLATION, default_financial_params[KEY_INFLATION]) * 100.0
    )
    salv_ui = fin_data.get(KEY_SALVAGE, default_financial_params[KEY_SALVAGE]) * 100.0
    anc_rev_ui = fin_data.get(
        KEY_ANCILLARY_REVENUE, default_financial_params[KEY_ANCILLARY_REVENUE]
    )

    debt_params = fin_data.get(
        KEY_DEBT_PARAMS, default_financial_params[KEY_DEBT_PARAMS]
    )
    loan_pct_ui = debt_params.get(
        KEY_LOAN_PERCENT, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_PERCENT]
    )
    loan_int_ui = (
        debt_params.get(
            KEY_LOAN_INTEREST,
            default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_INTEREST],
        )
        * 100.0
    )
    loan_term_ui = debt_params.get(
        KEY_LOAN_TERM, default_financial_params[KEY_DEBT_PARAMS][KEY_LOAN_TERM]
    )

    deprec_params = fin_data.get(
        KEY_DEPREC_PARAMS, default_financial_params[KEY_DEPREC_PARAMS]
    )
    macrs_ui = deprec_params.get(
        KEY_MACRS_SCHEDULE,
        default_financial_params[KEY_DEPREC_PARAMS][KEY_MACRS_SCHEDULE],
    )

    degrad_params = fin_data.get(
        KEY_DEGRAD_PARAMS, default_financial_params[KEY_DEGRAD_PARAMS]
    )
    deg_cap_ui = degrad_params.get(
        KEY_DEGRAD_CAP_YR,
        default_financial_params[KEY_DEGRAD_PARAMS][KEY_DEGRAD_CAP_YR],
    )
    deg_rte_ui = degrad_params.get(
        KEY_DEGRAD_RTE_YR,
        default_financial_params[KEY_DEGRAD_PARAMS][KEY_DEGRAD_RTE_YR],
    )
    repl_thr_ui = degrad_params.get(
        KEY_REPL_THRESH, default_financial_params[KEY_DEGRAD_PARAMS][KEY_REPL_THRESH]
    )

    # Incentives UI - Helper function to create enabled list
    def create_enabled_list(value):
        return ["enabled"] if value else []

    itc_en_ui = create_enabled_list(inc_data.get("itc_enabled", False))
    itc_pct_ui = inc_data.get(
        "itc_percentage", default_incentive_params["itc_percentage"]
    )
    ceic_en_ui = create_enabled_list(inc_data.get("ceic_enabled", False))
    ceic_pct_ui = inc_data.get(
        "ceic_percentage", default_incentive_params["ceic_percentage"]
    )
    bonus_en_ui = create_enabled_list(inc_data.get("bonus_credit_enabled", False))
    bonus_pct_ui = inc_data.get(
        "bonus_credit_percentage", default_incentive_params["bonus_credit_percentage"]
    )
    sgip_en_ui = create_enabled_list(inc_data.get("sgip_enabled", False))
    sgip_amt_ui = inc_data.get("sgip_amount", default_incentive_params["sgip_amount"])
    ess_en_ui = create_enabled_list(inc_data.get("ess_enabled", False))
    ess_amt_ui = inc_data.get("ess_amount", default_incentive_params["ess_amount"])
    mabi_en_ui = create_enabled_list(inc_data.get("mabi_enabled", False))
    mabi_amt_ui = inc_data.get("mabi_amount", default_incentive_params["mabi_amount"])
    cs_en_ui = create_enabled_list(inc_data.get("cs_enabled", False))
    cs_amt_ui = inc_data.get("cs_amount", default_incentive_params["cs_amount"])
    custom_en_ui = create_enabled_list(inc_data.get("custom_incentive_enabled", False))
    custom_type_ui = inc_data.get(
        "custom_incentive_type", default_incentive_params["custom_incentive_type"]
    )
    custom_amt_ui = inc_data.get(
        "custom_incentive_amount", default_incentive_params["custom_incentive_amount"]
    )
    custom_desc_ui = inc_data.get(
        "custom_incentive_description",
        default_incentive_params["custom_incentive_description"],
    )

    # Return all values in the correct order matching the output list
    return [
        util_provider,
        off_peak,
        mid_peak,
        peak_val,
        demand,
        seasonal_tog,
        tou_elements,
        eaf_size,
        eaf_count,
        grid_cap,
        cycles_day,
        cycle_dur,
        days_yr,
        bess_cap,
        bess_pow,
        bess_tech,
        sb_bos,
        pcs,
        epc,
        sys_int,
        rte,
        ins,
        disc,
        recyc,
        cyc_life,
        dod,
        cal_life,
        wacc_ui,
        lifespan_ui,
        tax_ui,
        infl_ui,
        salv_ui,
        anc_rev_ui,
        loan_pct_ui,
        loan_int_ui,
        loan_term_ui,
        macrs_ui,
        deg_cap_ui,
        deg_rte_ui,
        repl_thr_ui,
        itc_en_ui,
        itc_pct_ui,
        ceic_en_ui,
        ceic_pct_ui,
        bonus_en_ui,
        bonus_pct_ui,
        sgip_en_ui,
        sgip_amt_ui,
        ess_en_ui,
        ess_amt_ui,
        mabi_en_ui,
        mabi_amt_ui,
        cs_en_ui,
        cs_amt_ui,
        custom_en_ui,
        custom_type_ui,
        custom_amt_ui,
        custom_desc_ui,
        winter_mult_ui,
        summer_mult_ui,
        shoulder_mult_ui,
        winter_m_ui,
        summer_m_ui,
        shoulder_m_ui,
        fixed_om_ui,
        om_kwhyr_ui,
    ]


# --- Run the App ---
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True)
