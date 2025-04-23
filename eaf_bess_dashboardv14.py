

#**I. Financial Depth & Analysis:**

#1.  **Detailed Annual Cash Flow Table:** Instead of just the final NPV/IRR, show a year-by-year breakdown in a table:
#    *   Year | Gross Savings | O&M Cost | Replacement Cost | Taxable Income | Taxes | Net Cash Flow | Cumulative Cash Flow
#    *   Make this table downloadable (CSV). This is standard for financial analysis.
#2.  **Levelized Cost of Storage (LCOS):** Calculate and display the LCOS ($/MWh discharged). This is a key metric for comparing storage project costs over their lifetime.
#    *   Formula involves discounting all costs (initial, O&M, replacement, charging - if modeled) and dividing by total discounted energy discharged over the lifespan.
#3.  **Sensitivity Analysis:** This is *critical* for financial analysts. Add a simple mechanism (or a dedicated section/tab later) to see how NPV/IRR changes when key assumptions vary:
#    *   +/- X% change in Initial Capex
#    *   +/- X% change in Annual Savings (Utility Rates)
    # *   +/- X% change in WACC
    # *   +/- X% change in Inflation Rate
#     *   +/- X% change in BESS Lifespan (Cycles/Calendar)
# 4.  **Depreciation (More Advanced):** Incorporate tax depreciation (e.g., MACRS for US projects). This impacts the tax calculation and improves accuracy but adds complexity.
# 5.  **Degradation Modeling (More Advanced):** Model battery capacity and efficiency degradation over time. This would make savings decrease realistically and potentially trigger replacement sooner. Requires more complex simulation.
# 6.  **Charging Costs (More Advanced):** Explicitly model the cost of charging the battery (e.g., during off-peak hours), considering RTE losses. This requires simulating the full 24h cycle, not just peak shaving.

# **II. Presentation & Clarity:**

# 7.  **Key Performance Indicators (KPIs) Card:** Create a dedicated, prominent card at the top of the results showing the most important metrics (NPV, IRR, Payback, LCOS).
# 8.  **Assumptions Summary:** Clearly list the key input assumptions used for the calculation (WACC, Lifespan, Inflation, Key BESS params, Utility Rates used) near the results.
# 9.  **Improved Graphing:**
#     *   Clearer titles and axis labels.
#     *   Add annotations for key events (e.g., payback point on cumulative cash flow, replacement years on cash flow bar chart).
#     *   Consider adding a plot showing the breakdown of the annual bill (Energy vs. Demand) with and without BESS.
#     *   Visualize the optimization results better (e.g., a scatter plot of NPV vs. Capacity/Power).
# 10. **Enhanced Tooltips & Explanations:** Add more tooltips explaining financial terms (NPV, IRR, LCOS) and technical parameters. Add short text explanations alongside results sections.
# 11. **Units Consistency:** Double-check all units ($/MWh, $/kWh, $, %, years) are clearly labeled and consistent.

# **III. User Experience & Features:**

# 12. **Downloadable Results:** Allow exporting the results summary, key tables (detailed cash flow, monthly billing), and potentially graphs to PDF or CSV.
# 13. **Scenario Comparison (More Advanced):** Allow users to save multiple input sets ("Scenarios") and compare their results side-by-side.
# 14. **Input Validation Feedback:** Make validation errors more specific and potentially highlight the problematic input field.

# **Implementation Plan for This Revision:**

# For the immediate rewrite, I will focus on:

# *   **Fixing the Bugs:** Correcting the replacement cost logic and the initial cost/O&M calculation errors (incorporating the V7 store logic and safe conversions).
# *   **Adding LCOS Calculation:** A valuable financial metric.
# *   **Adding Detailed Annual Cash Flow Table:** Essential for financial review, including CSV export.
# *   **Improving Results Presentation:** Adding a KPI summary, an assumptions box, and refining labels/titles.
# *   **Refining Existing Calculations:** Ensure consistency and clarity.

# More advanced features like sensitivity analysis, depreciation, degradation, charging costs, and scenario comparison would require significant additional development and are best tackled as future enhancements.

# ---

# Okay, here is the rewritten code incorporating the bug fixes and the selected improvements (LCOS, Detailed Cash Flow Table, Presentation enhancements).

# ```python
# --- START OF FILE eaf_bess_dashboard_v14_fixed_enhanced.py ---

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback_context, ALL, dash_table, ctx # Import ctx
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import json
from datetime import datetime
import calendar
import traceback  # For detailed error logging
import pprint  # For debug printing
import io # For CSV export
import base64 # For CSV export

# --- numpy_financial fallback ---
try:
    import numpy_financial as npf
except ImportError:
    print("WARNING: numpy_financial package is required for accurate financial calculations. Please install it with: pip install numpy-financial")
    # ... (DummyNPF class remains the same) ...
    class DummyNPF:
        def npv(self, rate, values):
            print("WARNING: Using simplified NPV calculation. Install numpy-financial for accurate results.")
            if rate <= -1: return float('nan')
            try: return sum(values[i] / ((1 + rate)**i) for i in range(len(values)))
            except ZeroDivisionError: return float('nan')
        def irr(self, values):
            print("WARNING: IRR calculation requires numpy-financial. Install with: pip install numpy-financial")
            if not values or values[0] >= 0: return float('nan')
            # Simplified IRR (Newton-Raphson or bisection is better)
            try:
                # Basic bisection search
                low_rate, high_rate = -0.99, 1.0 # Search range
                tolerance = 1e-6
                max_iter = 100
                for _ in range(max_iter):
                    mid_rate = (low_rate + high_rate) / 2
                    npv_mid = self.npv(mid_rate, values)
                    if abs(npv_mid) < tolerance: return mid_rate
                    if npv_mid > 0: low_rate = mid_rate
                    else: high_rate = mid_rate
                    if high_rate - low_rate < tolerance: break
                return mid_rate if abs(self.npv(mid_rate, values)) < tolerance * 10 else float('nan')
            except: return float('nan')
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
ID_SALVAGE = "salvage-value" # Kept for UI, but not primary in calcs
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
ID_DOWNLOAD_CASHFLOW_LINK = "download-cashflow-link" # For CSV download

# Dictionary Keys (Selected Examples)
KEY_TECH = "technology"
KEY_CAPACITY = "capacity" # MWh
KEY_POWER_MAX = "power_max" # MW
KEY_SB_BOS_COST = "sb_bos_cost_per_kwh" # $/kWh
KEY_PCS_COST = "pcs_cost_per_kw" # $/kW
KEY_EPC_COST = "epc_cost_per_kwh" # $/kWh
KEY_SYS_INT_COST = "sys_integration_cost_per_kwh" # $/kWh
KEY_FIXED_OM = "fixed_om_per_kw_yr" # $/kW/yr
KEY_OM_KWHR_YR = "om_cost_per_kwh_yr" # $/kWh/yr
KEY_RTE = "rte_percent" # %
KEY_INSURANCE = "insurance_percent_yr" # %/yr
KEY_DISCONNECT_COST = "disconnect_cost_per_kwh" # $/kWh
KEY_RECYCLING_COST = "recycling_cost_per_kwh" # $/kWh
KEY_CYCLE_LIFE = "cycle_life" # cycles
KEY_DOD = "dod_percent" # %
KEY_CALENDAR_LIFE = "calendar_life" # years
KEY_EXAMPLE_PRODUCT = "example_product"
KEY_WACC = "wacc" # decimal
KEY_LIFESPAN = "project_lifespan" # years
KEY_TAX_RATE = "tax_rate" # decimal
KEY_INFLATION = "inflation_rate" # decimal
KEY_SALVAGE = "salvage_value" # decimal (less used now)
KEY_EAF_SIZE = "eaf_size" # tons
KEY_GRID_CAP = "grid_cap" # MW
KEY_CYCLES_PER_DAY = "cycles_per_day"
KEY_DAYS_PER_YEAR = "days_per_year"
KEY_CYCLE_DURATION_INPUT = "cycle_duration_input" # User input value (minutes)
KEY_CYCLE_DURATION = "cycle_duration" # Base value from mill data (minutes)
KEY_ENERGY_RATES = "energy_rates" # dict: {off_peak: $/MWh, ...}
KEY_DEMAND_CHARGE = "demand_charge" # $/kW/month
KEY_TOU_RAW = "tou_periods_raw" # list of tuples: [(start_hr, end_hr, rate_type), ...]
KEY_TOU_FILLED = "tou_periods_filled" # list of tuples covering 24h
KEY_SEASONAL = "seasonal_rates" # boolean
KEY_WINTER_MONTHS = "winter_months" # list of int
KEY_SUMMER_MONTHS = "summer_months" # list of int
KEY_SHOULDER_MONTHS = "shoulder_months" # list of int
KEY_WINTER_MULT = "winter_multiplier" # float
KEY_SUMMER_MULT = "summer_multiplier" # float
KEY_SHOULDER_MULT = "shoulder_multiplier" # float
# ... (add other keys as needed) ...


# --- Initialize the Dash app with Bootstrap themes & Font Awesome ---
app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)
server = app.server
app.title = "Battery Profitability Tool"

# --- Default Parameters (Utility, EAF, Financial) ---
# ... (default_utility_params, default_financial_params, default_incentive_params remain the same) ...
default_utility_params = {
    KEY_ENERGY_RATES: {"off_peak": 50, "mid_peak": 100, "peak": 150}, # $/MWh
    KEY_DEMAND_CHARGE: 10, # $/kW/month
    KEY_TOU_RAW: [(0.0, 8.0, 'off_peak'), (8.0, 10.0, 'peak'), (10.0, 16.0, 'mid_peak'), (16.0, 20.0, 'peak'), (20.0, 24.0, 'off_peak')],
    KEY_TOU_FILLED: [(0.0, 8.0, 'off_peak'), (8.0, 10.0, 'peak'), (10.0, 16.0, 'mid_peak'), (16.0, 20.0, 'peak'), (20.0, 24.0, 'off_peak')],
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
    KEY_SALVAGE: 0.1, # Less critical now with decommissioning costs
}
default_incentive_params = {
    "itc_enabled": False, "itc_percentage": 30,
    "ceic_enabled": False, "ceic_percentage": 30,
    "bonus_credit_enabled": False, "bonus_credit_percentage": 10,
    "sgip_enabled": False, "sgip_amount": 400, # $/kWh
    "ess_enabled": False, "ess_amount": 280, # $/kWh
    "mabi_enabled": False, "mabi_amount": 250, # $/kWh
    "cs_enabled": False, "cs_amount": 225, # $/kWh
    "custom_incentive_enabled": False, "custom_incentive_type": "per_kwh",
    "custom_incentive_amount": 100, "custom_incentive_description": "Custom incentive",
}

# --- BESS Technology Data ---
# ... (bess_technology_data remains the same) ...
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
        KEY_DISCONNECT_COST: 2, KEY_RECYCLING_COST: -2, # Negative recycling value
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
        KEY_OM_KWHR_YR: 2, # Specific O&M format $/kWh/yr
        KEY_RTE: 98, KEY_INSURANCE: 0.1,
        KEY_DISCONNECT_COST: 0.5, KEY_RECYCLING_COST: 1.0,
        KEY_CYCLE_LIFE: 100000, KEY_DOD: 100, KEY_CALENDAR_LIFE: 30,
    },
}

# --- Default BESS Parameters Store Structure ---
default_bess_params_store = {
    KEY_TECH: "LFP",
    KEY_CAPACITY: 40, # MWh
    KEY_POWER_MAX: 20, # MW
    **bess_technology_data["LFP"] # Populate with LFP details
}

# --- Nucor Mill Data ---
# ... (nucor_mills data remains the same) ...
nucor_mills = {
    "West Virginia": {"location": "Apple Grove, WV", "type": "Sheet", "eaf_count": 2, "eaf_type": "DC", "eaf_manufacturer": "SMS", KEY_EAF_SIZE: 190, KEY_CYCLES_PER_DAY: 26, "tons_per_year": 3000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Appalachian Power", KEY_GRID_CAP: 50},
    "Auburn": {"location": "Auburn, NY", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Unknown", KEY_EAF_SIZE: 60, KEY_CYCLES_PER_DAY: 28, "tons_per_year": 510000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "New York State Electric & Gas", KEY_GRID_CAP: 25},
    "Birmingham": {"location": "Birmingham, AL", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Unknown", KEY_EAF_SIZE: 52, KEY_CYCLES_PER_DAY: 20, "tons_per_year": 310000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Alabama Power", KEY_GRID_CAP: 20},
    "Arkansas": {"location": "Blytheville, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "Demag", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 28, "tons_per_year": 2500000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 38, "utility": "Entergy Arkansas", KEY_GRID_CAP: 45},
    "Kankakee": {"location": "Bourbonnais, IL", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 73, KEY_CYCLES_PER_DAY: 39, "tons_per_year": 850000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "ComEd", KEY_GRID_CAP: 30},
    "Brandenburg": {"location": "Brandenburg, KY", "type": "Sheet", "eaf_count": 1, "eaf_type": "DC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 27, "tons_per_year": 1200000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "LG&E KU", KEY_GRID_CAP: 45},
    "Hertford": {"location": "Cofield, NC", "type": "Plate", "eaf_count": 1, "eaf_type": "DC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 30, "tons_per_year": 1350000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Dominion Energy", KEY_GRID_CAP: 45},
    "Crawfordsville": {"location": "Crawfordsville, IN", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "Brown-Boveri", KEY_EAF_SIZE: 118, KEY_CYCLES_PER_DAY: 27, "tons_per_year": 1890000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Duke Energy", KEY_GRID_CAP: 40},
    "Darlington": {"location": "Darlington, SC", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 110, KEY_CYCLES_PER_DAY: 30, "tons_per_year": 980000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Duke Energy", KEY_GRID_CAP: 40},
    "Decatur": {"location": "Decatur, AL", "type": "Sheet", "eaf_count": 2, "eaf_type": "DC", "eaf_manufacturer": "NKK-SE", KEY_EAF_SIZE: 165, KEY_CYCLES_PER_DAY: 20, "tons_per_year": 2000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Alabama Power", KEY_GRID_CAP: 48},
    "Gallatin": {"location": "Ghent, KY", "type": "Sheet", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "NKK-SE, Danieli", KEY_EAF_SIZE: 175, KEY_CYCLES_PER_DAY: 27, "tons_per_year": 2800000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Kentucky Utilities", KEY_GRID_CAP: 53},
    "Hickman": {"location": "Hickman, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 22, "tons_per_year": 2000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Mississippi County Electric Cooperative", KEY_GRID_CAP: 45},
    "Berkeley": {"location": "Huger, SC", "type": "Sheet/Beam Mill", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 154, KEY_CYCLES_PER_DAY: 26, "tons_per_year": 2430000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Santee Cooper", KEY_GRID_CAP: 46},
    "Texas": {"location": "Jewett, TX", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "SMS Concast", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 33, "tons_per_year": 1000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Oncor Electric Delivery", KEY_GRID_CAP: 30},
    "Kingman": {"location": "Kingman, AZ", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 21, "tons_per_year": 630000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "UniSource Energy Services", KEY_GRID_CAP: 30},
    "Marion": {"location": "Marion, OH", "type": "Bar Mill/Sign Pos", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "?", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 40, "tons_per_year": 1200000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "AEP Ohio", KEY_GRID_CAP: 30},
    "Nebraska": {"location": "Norfolk, NE", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 95, KEY_CYCLES_PER_DAY: 35, "tons_per_year": 1000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Nebraska Public Power District", KEY_GRID_CAP: 29},
    "Utah": {"location": "Plymouth, UT", "type": "Bar", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "Fuchs", KEY_EAF_SIZE: 51, KEY_CYCLES_PER_DAY: 42, "tons_per_year": 1290000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Rocky Mountain Power", KEY_GRID_CAP: 15},
    "Seattle": {"location": "Seattle, WA", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "Fuchs", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 29, "tons_per_year": 855000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Seattle City Light", KEY_GRID_CAP: 30},
    "Sedalia": {"location": "Sedalia, MO", "type": "Bar", "eaf_count": 1, "eaf_type": "?", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 40, KEY_CYCLES_PER_DAY: 39, "tons_per_year": 470000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Evergy", KEY_GRID_CAP: 12},
    "Tuscaloosa": {"location": "Tuscaloosa, AL", "type": "Plate", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "MAN GHH", KEY_EAF_SIZE: 122, KEY_CYCLES_PER_DAY: 17, "tons_per_year": 610000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Alabama Power", KEY_GRID_CAP: 37},
    "Florida": {"location": "Frostproof, FL", "type": "?", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Danieli", KEY_EAF_SIZE: 40, KEY_CYCLES_PER_DAY: 38, "tons_per_year": 450000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Duke Energy Florida", KEY_GRID_CAP: 12},
    "Jackson": {"location": "Flowood, MS", "type": "Bar", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "?", KEY_EAF_SIZE: 50, KEY_CYCLES_PER_DAY: 33, "tons_per_year": 490000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Entergy Mississippi (Assumed)", KEY_GRID_CAP: 15},
    "Nucor-Yamato": {"location": "Blytheville, AR", "type": "Structural (implied)", "eaf_count": 2, "eaf_type": "?", "eaf_manufacturer": "?", KEY_EAF_SIZE: 150, KEY_CYCLES_PER_DAY: 25, "tons_per_year": 2500000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Mississippi County Electric Cooperative", KEY_GRID_CAP: 45},
    "Custom": {"location": "Custom Location", "type": "Custom", "eaf_count": 1, "eaf_type": "AC", "eaf_manufacturer": "Custom", KEY_EAF_SIZE: 100, KEY_CYCLES_PER_DAY: 24, "tons_per_year": 1000000, KEY_DAYS_PER_YEAR: 300, KEY_CYCLE_DURATION: 36, "utility": "Custom Utility", KEY_GRID_CAP: 35},
}

# --- Utility Rate Data ---
# ... (utility_rates data remains the same) ...
utility_rates = {
    "Appalachian Power": {KEY_ENERGY_RATES: {"off_peak": 45, "mid_peak": 90, "peak": 135}, KEY_DEMAND_CHARGE: 12, "tou_periods": [(0, 7, 'off_peak'), (7, 11, 'peak'), (11, 16, 'mid_peak'), (16, 20, 'peak'), (20, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.3, KEY_SHOULDER_MULT: 1.1},
    "New York State Electric & Gas": {KEY_ENERGY_RATES: {"off_peak": 60, "mid_peak": 110, "peak": 180}, KEY_DEMAND_CHARGE: 15, "tou_periods": [(0, 6, 'off_peak'), (6, 10, 'peak'), (10, 17, 'mid_peak'), (17, 21, 'peak'), (21, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8], KEY_SHOULDER_MONTHS: [4, 5, 9, 10], KEY_WINTER_MULT: 1.2, KEY_SUMMER_MULT: 1.5, KEY_SHOULDER_MULT: 1.3},
    "Alabama Power": {KEY_ENERGY_RATES: {"off_peak": 40, "mid_peak": 80, "peak": 120}, KEY_DEMAND_CHARGE: 10, "tou_periods": [(0, 8, 'off_peak'), (8, 11, 'peak'), (11, 15, 'mid_peak'), (15, 19, 'peak'), (19, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10, 11], KEY_WINTER_MULT: 0.9, KEY_SUMMER_MULT: 1.4, KEY_SHOULDER_MULT: 1.0},
    "Entergy Arkansas": {KEY_ENERGY_RATES: {"off_peak": 42, "mid_peak": 85, "peak": 130}, KEY_DEMAND_CHARGE: 11, "tou_periods": [(0, 7, 'off_peak'), (7, 10, 'peak'), (10, 16, 'mid_peak'), (16, 19, 'peak'), (19, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 0.9, KEY_SUMMER_MULT: 1.3, KEY_SHOULDER_MULT: 1.0},
    "ComEd": {KEY_ENERGY_RATES: {"off_peak": 48, "mid_peak": 95, "peak": 140}, KEY_DEMAND_CHARGE: 13, "tou_periods": [(0, 6, 'off_peak'), (6, 10, 'peak'), (10, 17, 'mid_peak'), (17, 21, 'peak'), (21, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8], KEY_SHOULDER_MONTHS: [4, 5, 9, 10], KEY_WINTER_MULT: 1.1, KEY_SUMMER_MULT: 1.6, KEY_SHOULDER_MULT: 1.2},
    "LG&E KU": {KEY_ENERGY_RATES: {"off_peak": 44, "mid_peak": 88, "peak": 125}, KEY_DEMAND_CHARGE: 12.5, "tou_periods": [(0, 7, 'off_peak'), (7, 11, 'peak'), (11, 17, 'mid_peak'), (17, 21, 'peak'), (21, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.35, KEY_SHOULDER_MULT: 1.1},
    "Dominion Energy": {KEY_ENERGY_RATES: {"off_peak": 47, "mid_peak": 94, "peak": 138}, KEY_DEMAND_CHARGE: 13.5, "tou_periods": [(0, 6, 'off_peak'), (6, 11, 'peak'), (11, 16, 'mid_peak'), (16, 20, 'peak'), (20, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [12, 1, 2, 3], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [4, 5, 10, 11], KEY_WINTER_MULT: 1.05, KEY_SUMMER_MULT: 1.45, KEY_SHOULDER_MULT: 1.15},
    "Duke Energy": {KEY_ENERGY_RATES: {"off_peak": 46, "mid_peak": 92, "peak": 135}, KEY_DEMAND_CHARGE: 14, "tou_periods": [(0, 7, 'off_peak'), (7, 10, 'peak'), (10, 16, 'mid_peak'), (16, 20, 'peak'), (20, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [3, 4, 5, 10], KEY_WINTER_MULT: 0.95, KEY_SUMMER_MULT: 1.4, KEY_SHOULDER_MULT: 1.1},
    "Kentucky Utilities": {},
    "Mississippi County Electric Cooperative": {KEY_ENERGY_RATES: {"off_peak": 32.72, "mid_peak": 32.72, "peak": 32.72}, KEY_DEMAND_CHARGE: 12.28, "tou_periods": [(0, 24, 'off_peak')], KEY_SEASONAL: False, KEY_WINTER_MONTHS: default_utility_params[KEY_WINTER_MONTHS], KEY_SUMMER_MONTHS: default_utility_params[KEY_SUMMER_MONTHS], KEY_SHOULDER_MONTHS: default_utility_params[KEY_SHOULDER_MONTHS], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.0, KEY_SHOULDER_MULT: 1.0},
    "Santee Cooper": {KEY_ENERGY_RATES: {"off_peak": 37.50, "mid_peak": 37.50, "peak": 57.50}, KEY_DEMAND_CHARGE: 19.26, "tou_periods": [(0, 13, 'off_peak'), (13, 22, 'peak'), (22, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [1, 2, 3, 4, 5, 9, 10, 11, 12], KEY_SUMMER_MONTHS: [6, 7, 8], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.0, KEY_SHOULDER_MULT: 1.0},
    "Oncor Electric Delivery": {},
    "UniSource Energy Services": {KEY_ENERGY_RATES: {"off_peak": 52.5, "mid_peak": 52.5, "peak": 77.5}, KEY_DEMAND_CHARGE: 16.5, "tou_periods": [(0, 6, 'off_peak'), (6, 10, 'peak'), (10, 17, 'off_peak'), (17, 21, 'peak'), (21, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [11, 12, 1, 2, 3, 4], KEY_SUMMER_MONTHS: [5, 6, 7, 8, 9, 10], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.85, KEY_SUMMER_MULT: 1.15, KEY_SHOULDER_MULT: 1.0},
    "AEP Ohio": {},
    "Nebraska Public Power District": {KEY_ENERGY_RATES: {"off_peak": 19.3, "mid_peak": 19.3, "peak": 34.4}, KEY_DEMAND_CHARGE: 19.0, "tou_periods": default_utility_params[KEY_TOU_FILLED], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.9, KEY_SUMMER_MULT: 1.1, KEY_SHOULDER_MULT: 1.0},
    "Rocky Mountain Power": {KEY_ENERGY_RATES: {"off_peak": 24.7, "mid_peak": 24.7, "peak": 48.5}, KEY_DEMAND_CHARGE: 15.79, "tou_periods": [(0, 6, 'off_peak'), (6, 9, 'peak'), (9, 15, 'off_peak'), (15, 22, 'peak'), (22, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.95, KEY_SUMMER_MULT: 1.05, KEY_SHOULDER_MULT: 1.0},
    "Seattle City Light": {KEY_ENERGY_RATES: {"off_peak": 55.30, "mid_peak": 55.30, "peak": 110.70}, KEY_DEMAND_CHARGE: 5.13, "tou_periods": [(0, 6, 'off_peak'), (6, 22, 'peak'), (22, 24, 'off_peak')], KEY_SEASONAL: False, KEY_WINTER_MONTHS: default_utility_params[KEY_WINTER_MONTHS], KEY_SUMMER_MONTHS: default_utility_params[KEY_SUMMER_MONTHS], KEY_SHOULDER_MONTHS: default_utility_params[KEY_SHOULDER_MONTHS], KEY_WINTER_MULT: 1.0, KEY_SUMMER_MULT: 1.0, KEY_SHOULDER_MULT: 1.0},
    "Evergy": {KEY_ENERGY_RATES: {"off_peak": 32.59, "mid_peak": 37.19, "peak": 53.91}, KEY_DEMAND_CHARGE: 9.69, "tou_periods": [(0, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.69, KEY_SUMMER_MULT: 1.31, KEY_SHOULDER_MULT: 1.0}, # Note: Rates adjusted based on multipliers
    "Duke Energy Florida": {},
    "Entergy Mississippi (Assumed)": {KEY_ENERGY_RATES: {"off_peak": 41.0, "mid_peak": 41.0, "peak": 67.0}, KEY_DEMAND_CHARGE: 16.75, "tou_periods": [(0, 6, 'off_peak'), (6, 10, 'peak'), (10, 12, 'off_peak'), (12, 20, 'peak'), (20, 24, 'off_peak')], KEY_SEASONAL: True, KEY_WINTER_MONTHS: [10, 11, 12, 1, 2, 3, 4, 5], KEY_SUMMER_MONTHS: [6, 7, 8, 9], KEY_SHOULDER_MONTHS: [], KEY_WINTER_MULT: 0.84, KEY_SUMMER_MULT: 1.16, KEY_SHOULDER_MULT: 1.0},
    "Custom Utility": default_utility_params,
}
# Fill placeholder utilities
placeholder_utilities = ["Kentucky Utilities", "Oncor Electric Delivery", "AEP Ohio", "Duke Energy Florida"]
for util_key in placeholder_utilities:
    if util_key in utility_rates:
        utility_rates[util_key] = utility_rates["Custom Utility"].copy()


# --- Helper Functions ---
# ... (fill_tou_gaps, get_month_season_multiplier remain the same) ...
def fill_tou_gaps(periods):
    """Fills gaps in a list of TOU periods with 'off_peak'."""
    if not periods: return [(0.0, 24.0, 'off_peak')]
    clean_periods = []
    # Validate and clean input periods
    for period in periods:
        try:
            if len(period) == 3:
                start, end, rate = float(period[0]), float(period[1]), str(period[2])
                if 0 <= start < end <= 24: clean_periods.append((start, end, rate))
                else: print(f"Warning: Skipping invalid TOU period data: {period}")
            else: print(f"Warning: Skipping malformed TOU period data: {period}")
        except (TypeError, ValueError, IndexError):
            print(f"Warning: Skipping invalid TOU period data: {period}")
            continue
    clean_periods.sort(key=lambda x: x[0])
    # Check for overlaps (optional warning)
    for i in range(len(clean_periods) - 1):
        if clean_periods[i][1] > clean_periods[i+1][0]:
            print(f"Warning: Overlapping TOU periods detected between {clean_periods[i]} and {clean_periods[i+1]}.")
    # Fill gaps
    filled_periods = []
    current_time = 0.0
    for start, end, rate in clean_periods:
        if start > current_time: filled_periods.append((current_time, start, 'off_peak')) # Fill gap before
        filled_periods.append((start, end, rate))
        current_time = end
    if current_time < 24.0: filled_periods.append((current_time, 24.0, 'off_peak')) # Fill gap after
    if not filled_periods: filled_periods.append((0.0, 24.0, 'off_peak')) # Handle empty case
    return filled_periods

def get_month_season_multiplier(month, seasonal_data):
    """Gets the rate multiplier for a given month based on seasonal settings."""
    if not seasonal_data.get(KEY_SEASONAL, False): return 1.0
    if month in seasonal_data.get(KEY_WINTER_MONTHS, []): return seasonal_data.get(KEY_WINTER_MULT, 1.0)
    elif month in seasonal_data.get(KEY_SUMMER_MONTHS, []): return seasonal_data.get(KEY_SUMMER_MULT, 1.0)
    elif month in seasonal_data.get(KEY_SHOULDER_MONTHS, []): return seasonal_data.get(KEY_SHOULDER_MULT, 1.0)
    else:
        print(f"Warning: Month {month} not found in any defined season. Using multiplier 1.0.")
        return 1.0

def calculate_eaf_profile(time_minutes, eaf_size=100, cycle_duration=36):
    """Generates a representative EAF power profile for a single cycle."""
    if cycle_duration <= 0: return np.zeros_like(time_minutes)
    eaf_power = np.zeros_like(time_minutes)
    scale = (eaf_size / 100)**0.6 if eaf_size > 0 else 0
    ref_duration = 28.0
    bore_in_end_frac = 3 / ref_duration
    main_melting_end_frac = 17 / ref_duration
    melting_end_frac = 20 / ref_duration
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
    """Calculates grid and BESS power contributions based on EAF demand and limits."""
    grid_power = np.zeros_like(eaf_power)
    bess_power = np.zeros_like(eaf_power)
    # --- Safe Conversion ---
    try: grid_cap_val = 0.0 if grid_cap is None else float(grid_cap)
    except: grid_cap_val = 0.0
    try: bess_power_max_val = 0.0 if bess_power_max is None else float(bess_power_max)
    except: bess_power_max_val = 0.0
    grid_cap_val = max(0.0, grid_cap_val)
    bess_power_max_val = max(0.0, bess_power_max_val)
    # --- Calculation ---
    for i, p_eaf in enumerate(eaf_power):
        p_eaf = max(0.0, p_eaf) # Ensure non-negative EAF power
        if p_eaf > grid_cap_val:
            discharge_needed = p_eaf - grid_cap_val
            actual_discharge = min(discharge_needed, bess_power_max_val)
            bess_power[i] = actual_discharge # Positive = discharge
            grid_power[i] = p_eaf - actual_discharge
        else:
            grid_power[i] = p_eaf
            bess_power[i] = 0.0
    return grid_power, bess_power

# --- Billing Calculation Functions ---
# ... (create_monthly_bill_with_bess, create_monthly_bill_without_bess remain the same) ...
def create_monthly_bill_with_bess(eaf_params, bess_params, utility_params, days_in_month, month_number):
    """Calculates estimated monthly utility bill WITH BESS peak shaving."""
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)
    energy_rates = {r: rate * seasonal_mult for r, rate in utility_params.get(KEY_ENERGY_RATES, {}).items()} # $/MWh
    demand_charge = utility_params.get(KEY_DEMAND_CHARGE, 0) * seasonal_mult # $/kW
    filled_tou_periods = utility_params.get(KEY_TOU_FILLED, [(0.0, 24.0, 'off_peak')])
    eaf_size = eaf_params.get(KEY_EAF_SIZE, 100)
    cycle_duration_min = eaf_params.get(KEY_CYCLE_DURATION_INPUT, eaf_params.get(KEY_CYCLE_DURATION, 36))
    cycle_duration_min = max(1.0, float(cycle_duration_min)) if cycle_duration_min is not None else 36.0 # Ensure positive float
    time_step_min = cycle_duration_min / 200.0
    time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min) # MW
    grid_cap = eaf_params.get(KEY_GRID_CAP, 50) # MW
    bess_power_max = bess_params.get(KEY_POWER_MAX, 20) # MW
    grid_power_cycle, bess_power_cycle = calculate_grid_bess_power(eaf_power_cycle, grid_cap, bess_power_max) # MW
    peak_demand_kw = np.max(grid_power_cycle) * 1000.0 if len(grid_power_cycle) > 0 else 0.0 # kW
    bess_energy_cycle_discharged = np.sum(bess_power_cycle[bess_power_cycle > 0]) * (time_step_min / 60.0) # MWh (Only positive discharge)
    grid_energy_cycle = np.sum(grid_power_cycle) * (time_step_min / 60.0) # MWh
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}
    total_energy_cost = 0.0
    total_grid_energy_month = 0.0
    cycles_per_day = eaf_params.get(KEY_CYCLES_PER_DAY, 24)
    cycles_per_day = max(0, int(cycles_per_day)) if cycles_per_day is not None else 0
    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start
            period_fraction = period_hours / 24.0
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month # MWh
            period_cost = energy_in_period_month * energy_rates[period] # MWh * $/MWh = $
            tou_energy_costs[period] += period_cost
            total_energy_cost += period_cost
            total_grid_energy_month += energy_in_period_month
        else: print(f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict.")
    demand_cost = peak_demand_kw * demand_charge # kW * $/kW = $
    total_bill = total_energy_cost + demand_cost
    return {
        "energy_cost": total_energy_cost, "demand_cost": demand_cost, "total_bill": total_bill,
        "peak_demand_kw": peak_demand_kw, "energy_consumed_mwh": total_grid_energy_month,
        "tou_breakdown": tou_energy_costs, "bess_discharged_per_cycle_mwh": bess_energy_cycle_discharged,
        "bess_discharged_total_mwh": bess_energy_cycle_discharged * cycles_per_day * days_in_month # Add total monthly discharge
    }

def create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month_number):
    """Calculates estimated monthly utility bill WITHOUT BESS."""
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)
    energy_rates = {r: rate * seasonal_mult for r, rate in utility_params.get(KEY_ENERGY_RATES, {}).items()}
    demand_charge = utility_params.get(KEY_DEMAND_CHARGE, 0) * seasonal_mult
    filled_tou_periods = utility_params.get(KEY_TOU_FILLED, [(0.0, 24.0, 'off_peak')])
    eaf_size = eaf_params.get(KEY_EAF_SIZE, 100)
    cycle_duration_min = eaf_params.get(KEY_CYCLE_DURATION_INPUT, eaf_params.get(KEY_CYCLE_DURATION, 36))
    cycle_duration_min = max(1.0, float(cycle_duration_min)) if cycle_duration_min is not None else 36.0
    time_step_min = cycle_duration_min / 200.0
    time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min) # MW
    grid_power_cycle = eaf_power_cycle # Grid takes full load
    peak_demand_kw = np.max(grid_power_cycle) * 1000.0 if len(grid_power_cycle) > 0 else 0.0 # kW
    grid_energy_cycle = np.sum(grid_power_cycle) * (time_step_min / 60.0) # MWh
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}
    total_energy_cost = 0.0
    total_grid_energy_month = 0.0
    cycles_per_day = eaf_params.get(KEY_CYCLES_PER_DAY, 24)
    cycles_per_day = max(0, int(cycles_per_day)) if cycles_per_day is not None else 0
    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start
            period_fraction = period_hours / 24.0
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month
            period_cost = energy_in_period_month * energy_rates[period]
            tou_energy_costs[period] += period_cost
            total_energy_cost += period_cost
            total_grid_energy_month += energy_in_period_month
        else: print(f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict.")
    demand_cost = peak_demand_kw * demand_charge
    total_bill = total_energy_cost + demand_cost
    return {
        "energy_cost": total_energy_cost, "demand_cost": demand_cost, "total_bill": total_bill,
        "peak_demand_kw": peak_demand_kw, "energy_consumed_mwh": total_grid_energy_month,
        "tou_breakdown": tou_energy_costs,
    }

def calculate_annual_billings(eaf_params, bess_params, utility_params):
    """Calculates annual bills and savings by summing monthly results."""
    monthly_bills_with_bess = []
    monthly_bills_without_bess = []
    monthly_savings = []
    total_annual_discharge_mwh = 0.0 # Added for LCOS

    year = datetime.now().year # Use current year
    if KEY_TOU_FILLED not in utility_params or not utility_params[KEY_TOU_FILLED]:
        raw_periods = utility_params.get(KEY_TOU_RAW, default_utility_params[KEY_TOU_RAW])
        utility_params[KEY_TOU_FILLED] = fill_tou_gaps(raw_periods)
        print("Warning: Filled TOU periods were missing, generated them.")

    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]
        bill_with_bess = create_monthly_bill_with_bess(eaf_params, bess_params, utility_params, days_in_month, month)
        bill_without_bess = create_monthly_bill_without_bess(eaf_params, utility_params, days_in_month, month)
        savings = bill_without_bess["total_bill"] - bill_with_bess["total_bill"]
        monthly_bills_with_bess.append(bill_with_bess)
        monthly_bills_without_bess.append(bill_without_bess)
        monthly_savings.append(savings)
        total_annual_discharge_mwh += bill_with_bess.get("bess_discharged_total_mwh", 0.0) # Sum monthly discharge

    annual_bill_with_bess = sum(bill["total_bill"] for bill in monthly_bills_with_bess)
    annual_bill_without_bess = sum(bill["total_bill"] for bill in monthly_bills_without_bess)
    annual_savings = sum(monthly_savings)

    return {
        "monthly_bills_with_bess": monthly_bills_with_bess,
        "monthly_bills_without_bess": monthly_bills_without_bess,
        "monthly_savings": monthly_savings,
        "annual_bill_with_bess": annual_bill_with_bess,
        "annual_bill_without_bess": annual_bill_without_bess,
        "annual_savings": annual_savings,
        "total_annual_discharge_mwh": total_annual_discharge_mwh, # Added for LCOS
    }

# --- Refactored Cost Calculation Helper ---
def calculate_initial_bess_cost(bess_params):
    """Calculates the initial gross capital cost of the BESS."""
    # --- Safe Conversion ---
    try: capacity_mwh = 0.0 if bess_params.get(KEY_CAPACITY) is None else float(bess_params.get(KEY_CAPACITY, 0))
    except: capacity_mwh = 0.0
    try: power_mw = 0.0 if bess_params.get(KEY_POWER_MAX) is None else float(bess_params.get(KEY_POWER_MAX, 0))
    except: power_mw = 0.0
    capacity_mwh = max(0.0, capacity_mwh)
    power_mw = max(0.0, power_mw)
    # --- Calculation ---
    capacity_kwh = capacity_mwh * 1000.0
    power_kw = power_mw * 1000.0
    sb_bos_cost = bess_params.get(KEY_SB_BOS_COST, 0) * capacity_kwh
    pcs_cost = bess_params.get(KEY_PCS_COST, 0) * power_kw
    epc_cost = bess_params.get(KEY_EPC_COST, 0) * capacity_kwh
    sys_int_cost = bess_params.get(KEY_SYS_INT_COST, 0) * capacity_kwh
    total_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost
    # --- Debug Print ---
    # print(f"DEBUG COST: Cap_kWh={capacity_kwh}, Pow_kW={power_kw}")
    # print(f"DEBUG COST: SB+BOS={sb_bos_cost:.0f}, PCS={pcs_cost:.0f}, EPC={epc_cost:.0f}, SysInt={sys_int_cost:.0f}, Total={total_cost:.0f}")
    # --- End Debug ---
    return total_cost

# --- Incentive Calculation Function ---
# ... (calculate_incentives remains largely the same, relies on calculate_initial_bess_cost) ...
def calculate_incentives(bess_params, incentive_params):
    """Calculate total incentives based on selected programs and BESS cost."""
    total_incentive = 0.0
    incentive_breakdown = {}
    # Calculate Initial BESS Cost using helper
    total_cost = calculate_initial_bess_cost(bess_params)
    # --- Safe Conversion for Capacity ---
    try: capacity_mwh = 0.0 if bess_params.get(KEY_CAPACITY) is None else float(bess_params.get(KEY_CAPACITY, 0))
    except: capacity_mwh = 0.0
    capacity_mwh = max(0.0, capacity_mwh)
    capacity_kwh = capacity_mwh * 1000.0
    # --- Get Incentive Params ---
    def get_incentive_param(key, default): return incentive_params.get(key, default)
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
        if custom_type == "per_kwh": custom_amount = capacity_kwh * custom_rate
        elif custom_type == "percentage": custom_amount = total_cost * (custom_rate / 100.0)
    # Apply rules (e.g., ITC/CEIC exclusivity)
    applied_federal_base = 0.0
    federal_base_desc = ""
    if itc_enabled and ceic_enabled:
        if itc_amount >= ceic_amount: applied_federal_base, federal_base_desc = itc_amount, "Investment Tax Credit (ITC)"
        else: applied_federal_base, federal_base_desc = ceic_amount, "Clean Electricity Investment Credit (CEIC)"
    elif itc_enabled: applied_federal_base, federal_base_desc = itc_amount, "Investment Tax Credit (ITC)"
    elif ceic_enabled: applied_federal_base, federal_base_desc = ceic_amount, "Clean Electricity Investment Credit (CEIC)"
    # Sum up applied incentives
    if applied_federal_base > 0: total_incentive += applied_federal_base; incentive_breakdown[federal_base_desc] = applied_federal_base
    if bonus_amount > 0: total_incentive += bonus_amount; incentive_breakdown["Bonus Credits"] = bonus_amount
    if sgip_amount > 0: total_incentive += sgip_amount; incentive_breakdown["CA Self-Generation Incentive Program"] = sgip_amount
    if ess_amount > 0: total_incentive += ess_amount; incentive_breakdown["CT Energy Storage Solutions"] = ess_amount
    if mabi_amount > 0: total_incentive += mabi_amount; incentive_breakdown["NY Market Acceleration Bridge Incentive"] = mabi_amount
    if cs_amount > 0: total_incentive += cs_amount; incentive_breakdown["MA Connected Solutions"] = cs_amount
    if custom_amount > 0: total_incentive += custom_amount; incentive_breakdown[custom_desc] = custom_amount
    return {"total_incentive": total_incentive, "breakdown": incentive_breakdown, "calculated_initial_cost": total_cost}


# --- Financial Metrics Calculation (FIXED & ENHANCED) ---
def calculate_financial_metrics(bess_params, financial_params, eaf_params, annual_savings, total_annual_discharge_mwh, incentives_results):
    """Calculate NPV, IRR, payback period, LCOS, etc. using detailed BESS parameters."""
    detailed_cash_flows = [] # For detailed table
    try:
        # --- Get Parameters & Perform Safe Conversions ---
        technology = bess_params.get(KEY_TECH, "LFP")
        print(f"\n--- DEBUG calculate_financial_metrics ---")
        print(f"Technology: {technology}")
        # print("BESS Params Received:")
        # pprint.pprint(bess_params)

        # Capacity / Power
        try:
            raw_capacity_mwh = bess_params.get(KEY_CAPACITY, 0)
            raw_power_mw = bess_params.get(KEY_POWER_MAX, 0)
            capacity_mwh = 0.0 if raw_capacity_mwh is None else float(raw_capacity_mwh)
            power_mw = 0.0 if raw_power_mw is None else float(raw_power_mw)
        except (ValueError, TypeError) as conv_err:
            print(f"ERROR FINANCE CONV: {conv_err}. Raw: Cap={raw_capacity_mwh}, Pow={raw_power_mw}")
            capacity_mwh = 0.0
            power_mw = 0.0
        capacity_mwh = max(0.0, capacity_mwh)
        power_mw = max(0.0, power_mw)
        capacity_kwh = capacity_mwh * 1000.0
        power_kw = power_mw * 1000.0
        print(f"DEBUG FINANCE: Using capacity_kwh = {capacity_kwh:.2f}, power_kw = {power_kw:.2f}")

        # Opex params
        fixed_om_per_kw_yr = bess_params.get(KEY_FIXED_OM, 0.0) # Default to 0.0 if key missing
        om_cost_per_kwh_yr = bess_params.get(KEY_OM_KWHR_YR, 0.0) # Default to 0.0 if key missing
        insurance_percent_yr = bess_params.get(KEY_INSURANCE, 0.0)
        fixed_om_per_kw_yr = 0.0 if fixed_om_per_kw_yr is None else float(fixed_om_per_kw_yr)
        om_cost_per_kwh_yr = 0.0 if om_cost_per_kwh_yr is None else float(om_cost_per_kwh_yr)
        insurance_percent_yr = 0.0 if insurance_percent_yr is None else float(insurance_percent_yr)
        print(f"DEBUG FINANCE: Opex Inputs: Fixed={fixed_om_per_kw_yr}, kWhr={om_cost_per_kwh_yr}, Ins%={insurance_percent_yr}")


        # Decommissioning params
        disconnect_cost_per_kwh = bess_params.get(KEY_DISCONNECT_COST, 0.0)
        recycling_cost_per_kwh = bess_params.get(KEY_RECYCLING_COST, 0.0)
        disconnect_cost_per_kwh = 0.0 if disconnect_cost_per_kwh is None else float(disconnect_cost_per_kwh)
        recycling_cost_per_kwh = 0.0 if recycling_cost_per_kwh is None else float(recycling_cost_per_kwh)

        # Performance params
        cycle_life = bess_params.get(KEY_CYCLE_LIFE, 5000)
        calendar_life = bess_params.get(KEY_CALENDAR_LIFE, 15)
        cycle_life = 1 if cycle_life is None or float(cycle_life) <= 0 else float(cycle_life) # Ensure positive
        calendar_life = 1 if calendar_life is None or float(calendar_life) <= 0 else float(calendar_life) # Ensure positive

        # Financial Parameters
        years = int(financial_params.get(KEY_LIFESPAN, 30))
        wacc = financial_params.get(KEY_WACC, 0.131)
        inflation_rate = financial_params.get(KEY_INFLATION, 0.024)
        tax_rate = financial_params.get(KEY_TAX_RATE, 0.2009)
        years = max(1, int(years)) if years is not None else 30
        wacc = 0.0 if wacc is None else float(wacc)
        inflation_rate = 0.0 if inflation_rate is None else float(inflation_rate)
        tax_rate = 0.0 if tax_rate is None else float(tax_rate)

        # EAF Parameters for battery life
        days_per_year = eaf_params.get(KEY_DAYS_PER_YEAR, 300)
        cycles_per_day = eaf_params.get(KEY_CYCLES_PER_DAY, 24)
        days_per_year = max(1, int(days_per_year)) if days_per_year is not None else 300
        cycles_per_day = max(1, int(cycles_per_day)) if cycles_per_day is not None else 24

        # --- Initial Calculations ---
        total_initial_cost = calculate_initial_bess_cost(bess_params) # Uses safe conversions inside
        print(f"DEBUG FINANCE: Initial Cost Calculation Result = ${total_initial_cost:,.2f}")

        total_incentive = incentives_results.get("total_incentive", 0.0)
        net_initial_cost = total_initial_cost - total_incentive
        if net_initial_cost < 0: print("Warning: Total incentives exceed calculated initial BESS cost.")

        # Calculate Annual O&M Cost (Year 1)
        om_base_cost = 0.0
        # Determine which O&M key is relevant for the technology
        intended_om_is_kwhyr = KEY_OM_KWHR_YR in bess_params # Check if the key exists in the params dict passed
        if intended_om_is_kwhyr and om_cost_per_kwh_yr > 0:
            om_base_cost = om_cost_per_kwh_yr * capacity_kwh
            print(f"DEBUG FINANCE: Using O&M $/kWh/yr ({om_cost_per_kwh_yr}) * capacity ({capacity_kwh}) = {om_base_cost}")
        elif not intended_om_is_kwhyr and fixed_om_per_kw_yr > 0:
            om_base_cost = fixed_om_per_kw_yr * power_kw
            print(f"DEBUG FINANCE: Using Fixed O&M $/kW/yr ({fixed_om_per_kw_yr}) * power ({power_kw}) = {om_base_cost}")
        else:
             # Fallback if primary key is missing or zero, but the other exists and is non-zero
             if fixed_om_per_kw_yr > 0:
                 om_base_cost = fixed_om_per_kw_yr * power_kw
                 print(f"DEBUG FINANCE: Fallback O&M: Using Fixed O&M $/kW/yr ({fixed_om_per_kw_yr}) * power ({power_kw}) = {om_base_cost}")
             elif om_cost_per_kwh_yr > 0:
                 om_base_cost = om_cost_per_kwh_yr * capacity_kwh
                 print(f"DEBUG FINANCE: Fallback O&M: Using O&M $/kWh/yr ({om_cost_per_kwh_yr}) * capacity ({capacity_kwh}) = {om_base_cost}")
             else:
                 print(f"Warning: No non-zero O&M cost defined or retrieved for technology {technology}")

        insurance_cost = (insurance_percent_yr / 100.0) * total_initial_cost
        total_initial_om_cost = om_base_cost + insurance_cost
        print(f"DEBUG FINANCE: Base O&M=${om_base_cost:,.2f}, Insurance=${insurance_cost:,.2f}, Total Initial O&M=${total_initial_om_cost:,.2f}")

        # --- Battery Life & Replacement Calculation ---
        cycles_per_year_equiv = cycles_per_day * days_per_year
        battery_life_years_cycles = (cycle_life / cycles_per_year_equiv) if cycles_per_year_equiv > 0 else float('inf')
        battery_replacement_interval = min(calendar_life, battery_life_years_cycles)
        if battery_replacement_interval <= 0 or pd.isna(battery_replacement_interval):
            battery_replacement_interval = float('inf')
            print("Warning: Calculated battery replacement interval is zero or invalid. No replacements will be scheduled.")
        print(f"DEBUG FINANCE: Battery Life: Calendar={calendar_life:.1f} yrs, Cycle Equivalent={battery_life_years_cycles:.1f} yrs. -> Replacement Interval={battery_replacement_interval:.1f} yrs")

        # --- Cash Flow Calculation Loop ---
        cash_flows = [-net_initial_cost] # Net cash flow list for NPV/IRR
        discounted_costs = [total_initial_cost] # Gross costs list for LCOS (Year 0 = initial cost)
        discounted_discharge = [0.0] # Discharge list for LCOS (Year 0 = 0)

        # Add Year 0 to detailed table
        detailed_cash_flows.append({
            "Year": 0, "Gross Savings": 0, "O&M Cost": 0, "Replacement Cost": 0,
            "Decommissioning Cost": 0, "Taxable Income": 0, "Taxes": 0,
            "Incentives": total_incentive, "Net Cash Flow": -net_initial_cost,
            "Cumulative Cash Flow": -net_initial_cost
        })

        next_replacement_year = battery_replacement_interval # Initialize first replacement time

        for year in range(1, years + 1):
            # Inflated Savings and O&M Costs for year t
            inflation_factor = (1 + inflation_rate) ** (year - 1)
            savings_t = annual_savings * inflation_factor
            o_m_cost_t = total_initial_om_cost * inflation_factor

            # Recurring Replacement Cost Logic (REVISED)
            replacement_cost_year_gross = 0.0
            if battery_replacement_interval != float('inf') and year >= next_replacement_year:
                inflated_replacement_cost = total_initial_cost * inflation_factor
                replacement_cost_year_gross = inflated_replacement_cost
                print(f"DEBUG FINANCE: Battery replacement cost ${replacement_cost_year_gross:,.0f} applied in year {year} (Interval: {battery_replacement_interval:.1f} yrs, Next due: {next_replacement_year:.1f})")
                next_replacement_year += battery_replacement_interval

            # Decommissioning Costs (Applied ONLY in the final year)
            decommissioning_cost_gross = 0.0
            if year == years:
                decomm_cost_base = (disconnect_cost_per_kwh + recycling_cost_per_kwh) * capacity_kwh
                decommissioning_cost_gross = decomm_cost_base * inflation_factor
                print(f"DEBUG FINANCE: Decommissioning cost ${decommissioning_cost_gross:,.0f} applied in year {year}")

            # EBT (Earnings Before Tax) - Note: Incentives are typically not taxed as income here, they reduce basis.
            # Depreciation is not modeled, so EBT is simplified.
            ebt = savings_t - o_m_cost_t - replacement_cost_year_gross - decommissioning_cost_gross
            taxes = max(0, ebt * tax_rate) # Tax only positive EBT

            # Net Cash Flow for NPV/IRR
            net_cash_flow = savings_t - o_m_cost_t - replacement_cost_year_gross - decommissioning_cost_gross - taxes
            cash_flows.append(net_cash_flow)

            # --- For LCOS ---
            # Sum of gross costs in this year (O&M + Replacement + Decomm)
            total_gross_costs_t = o_m_cost_t + replacement_cost_year_gross + decommissioning_cost_gross
            discounted_costs.append(total_gross_costs_t / ((1 + wacc) ** year))
            # Assume annual discharge is constant for simplicity (could be degraded)
            annual_discharge_t = total_annual_discharge_mwh # MWh
            discounted_discharge.append(annual_discharge_t / ((1 + wacc) ** year))

            # --- For Detailed Table ---
            detailed_cash_flows.append({
                "Year": year,
                "Gross Savings": savings_t,
                "O&M Cost": o_m_cost_t,
                "Replacement Cost": replacement_cost_year_gross,
                "Decommissioning Cost": decommissioning_cost_gross,
                "Taxable Income": ebt,
                "Taxes": taxes,
                "Incentives": 0, # Only in Year 0
                "Net Cash Flow": net_cash_flow,
                "Cumulative Cash Flow": sum(cash_flows) # Calculate cumulative up to current year
            })


        # --- Calculate Financial Metrics ---
        npv_val = float('nan')
        irr_val = float('nan')
        try:
            if wacc > -1: npv_val = npf.npv(wacc, cash_flows)
            else: print("Warning: WACC <= -1, cannot calculate NPV.")
        except Exception as e: print(f"Error calculating NPV: {e}")

        try:
            # Check if IRR calculation is feasible
            if cash_flows and len(cash_flows) > 1 and cash_flows[0] < 0 and any(cf > 0 for cf in cash_flows[1:]):
                irr_val = npf.irr(cash_flows)
                if irr_val is None or np.isnan(irr_val) or np.isinf(irr_val): irr_val = float('nan')
            else: irr_val = float('nan') # Not feasible
        except Exception as e:
            print(f"Error calculating IRR: {e}")
            irr_val = float('nan')

        # --- Payback Period Calculation (Simple) ---
        cumulative_cash_flow = 0.0
        payback_years = float('inf')
        if cash_flows[0] >= 0: payback_years = 0.0
        else:
            cumulative_cash_flow = cash_flows[0]
            for year_pbk in range(1, len(cash_flows)):
                current_year_cf = cash_flows[year_pbk]
                if current_year_cf is None: current_year_cf = 0.0
                if cumulative_cash_flow + current_year_cf >= 0:
                    fraction_needed = abs(cumulative_cash_flow) / current_year_cf if current_year_cf > 0 else 0.0
                    payback_years = (year_pbk - 1) + fraction_needed
                    break
                cumulative_cash_flow += current_year_cf

        # --- LCOS Calculation ---
        lcos = float('nan')
        total_discounted_costs = sum(discounted_costs)
        total_discounted_discharge_mwh = sum(discounted_discharge)
        if total_discounted_discharge_mwh > 0:
            lcos = total_discounted_costs / total_discounted_discharge_mwh # $/MWh
        print(f"DEBUG FINANCE: LCOS Calc: Total Discounted Costs=${total_discounted_costs:,.0f}, Total Discounted Discharge={total_discounted_discharge_mwh:.0f} MWh")


        print(f"--- End calculate_financial_metrics ---\n")
        return {
            "npv": npv_val, "irr": irr_val, "payback_years": payback_years, "lcos": lcos,
            "cash_flows": cash_flows, # Summary cash flows for plots
            "detailed_cash_flows": detailed_cash_flows, # Detailed for table
            "net_initial_cost": net_initial_cost, "total_initial_cost": total_initial_cost,
            "battery_life_years": battery_replacement_interval,
            "annual_savings_year1": annual_savings,
            "initial_om_cost_year1": total_initial_om_cost,
            "total_annual_discharge_mwh": total_annual_discharge_mwh, # Pass this through
        }

    except Exception as e:
        print(f"Error in financial metrics calculation: {e}")
        traceback.print_exc()
        # Return default structure on error
        return {
            "npv": float('nan'), "irr": float('nan'), "payback_years": float('inf'), "lcos": float('nan'),
            "cash_flows": [0] * (int(financial_params.get(KEY_LIFESPAN, 30)) + 1),
            "detailed_cash_flows": [],
            "net_initial_cost": 0, "total_initial_cost": 0,
            "battery_life_years": 0, "annual_savings_year1": 0,
            "initial_om_cost_year1": 0, "total_annual_discharge_mwh": 0,
        }


# --- Optimization Function ---
# ... (optimize_battery_size remains largely the same, but needs to pass total_annual_discharge_mwh to calculate_financial_metrics) ...
def optimize_battery_size(eaf_params, utility_params, financial_params, incentive_params, bess_base_params):
    """Find optimal battery size (Capacity MWh, Power MW) for best ROI using NPV as metric."""
    technology = bess_base_params.get(KEY_TECH, "LFP")
    print(f"DEBUG OPTIMIZE: Using base technology: {technology}")
    # Define search space
    capacity_options = np.linspace(5, 100, 10) # MWh
    power_options = np.linspace(2, 50, 10) # MW
    best_npv = -float('inf')
    best_capacity = None
    best_power = None
    best_metrics = None
    optimization_results = []
    print(f"Starting optimization: {len(capacity_options)} capacities, {len(power_options)} powers...")
    count = 0
    total_combinations = len(capacity_options) * len(power_options)

    for capacity in capacity_options:
        for power in power_options:
            count += 1
            print(f"  Testing {count}/{total_combinations}: Cap={capacity:.1f} MWh, Pow={power:.1f} MW")
            c_rate = power / capacity if capacity > 0 else float('inf')
            if not (0.2 <= c_rate <= 2.5): # Example C-Rate constraint
                print(f"    Skipping C-rate {c_rate:.2f} (out of range 0.2-2.5)")
                continue

            test_bess_params = bess_base_params.copy()
            test_bess_params[KEY_CAPACITY] = capacity
            test_bess_params[KEY_POWER_MAX] = power

            try:
                billing_results = calculate_annual_billings(eaf_params, test_bess_params, utility_params)
                annual_savings = billing_results["annual_savings"]
                total_annual_discharge = billing_results["total_annual_discharge_mwh"] # Get discharge
                incentive_results = calculate_incentives(test_bess_params, incentive_params)
                # Pass discharge to metrics function
                metrics = calculate_financial_metrics(test_bess_params, financial_params, eaf_params, annual_savings, total_annual_discharge, incentive_results)

                current_result = {
                    "capacity": capacity, "power": power,
                    "npv": metrics.get("npv", float('nan')),
                    "irr": metrics.get("irr", float('nan')),
                    "payback_years": metrics.get("payback_years", float('inf')),
                    "lcos": metrics.get("lcos", float('nan')),
                    "annual_savings": annual_savings,
                    "net_initial_cost": metrics.get("net_initial_cost", 0),
                }
                optimization_results.append(current_result)

                if pd.notna(metrics.get("npv")) and metrics["npv"] > best_npv:
                    best_npv = metrics["npv"]
                    best_capacity = capacity
                    best_power = power
                    best_metrics = metrics # Store full metrics
                    print(f"    *** New best NPV found: ${best_npv:,.0f} ***")

            except Exception as e:
                print(f"    Error during optimization step (Cap={capacity:.1f}, Pow={power:.1f}): {e}")
                optimization_results.append({"capacity": capacity, "power": power, "npv": float('nan'), "error": str(e)})

    print("Optimization finished.")
    return {
        "best_capacity": best_capacity, "best_power": best_power, "best_npv": best_npv,
        "best_metrics": best_metrics, "all_results": optimization_results,
    }


# --- Technology Comparison Table (FIXED) ---
def create_technology_comparison_table(current_tech, capacity_mwh, power_mw):
    """Create a comparison table of different battery technologies based on current size."""
    def fmt_c(v): return f"${v:,.0f}" if pd.notna(v) and abs(v) < 1e15 else "N/A"
    techs_to_compare = list(bess_technology_data.keys())
    if current_tech not in techs_to_compare and current_tech: techs_to_compare.append(current_tech)
    comp_data = []
    # --- Safe Conversion ---
    try: safe_capacity_mwh = 0.0 if capacity_mwh is None else float(capacity_mwh)
    except: safe_capacity_mwh = 0.0
    try: safe_power_mw = 0.0 if power_mw is None else float(power_mw)
    except: safe_power_mw = 0.0
    safe_capacity_mwh = max(0.0, safe_capacity_mwh)
    safe_power_mw = max(0.0, safe_power_mw)
    capacity_kwh = safe_capacity_mwh * 1000.0
    power_kw = safe_power_mw * 1000.0
    # --- End Safe Conversion ---
    # print(f"DEBUG TABLE: Using capacity_kwh={capacity_kwh}, power_kw={power_kw} for comparison")

    for tech in techs_to_compare:
        if tech not in bess_technology_data: continue
        tech_data = bess_technology_data[tech]
        try:
            sb_bos_cost = tech_data.get(KEY_SB_BOS_COST, 0) * capacity_kwh
            pcs_cost = tech_data.get(KEY_PCS_COST, 0) * power_kw
            epc_cost = tech_data.get(KEY_EPC_COST, 0) * capacity_kwh
            sys_int_cost = tech_data.get(KEY_SYS_INT_COST, 0) * capacity_kwh
            total_cost = sb_bos_cost + pcs_cost + epc_cost + sys_int_cost
            # Calculate annual O&M cost
            annual_om = 0.0
            if KEY_OM_KWHR_YR in tech_data:
                annual_om = tech_data[KEY_OM_KWHR_YR] * capacity_kwh
            elif KEY_FIXED_OM in tech_data:
                annual_om = tech_data.get(KEY_FIXED_OM, 0) * power_kw
            # Unit costs
            energy_cost_per_kwh = tech_data.get(KEY_SB_BOS_COST, 0) + tech_data.get(KEY_EPC_COST, 0) + tech_data.get(KEY_SYS_INT_COST, 0)
            power_cost_per_kw = tech_data.get(KEY_PCS_COST, 0)
            # Performance
            cycle_life = tech_data.get(KEY_CYCLE_LIFE, 0)
            calendar_life = tech_data.get(KEY_CALENDAR_LIFE, 0)
            rte = tech_data.get(KEY_RTE, 0)
        except Exception as e:
            print(f"Error calculating comparison row for {tech}: {e}")
            total_cost, annual_om, energy_cost_per_kwh, power_cost_per_kw = 0, 0, 0, 0
            cycle_life, calendar_life, rte = 0, 0, 0

        row = {
            'Technology': tech + (' (Current)' if tech == current_tech else ''),
            'Cycle Life': f"{cycle_life:,}",
            'Calendar Life (yrs)': f"{calendar_life:.1f}",
            'RTE (%)': f"{rte:.1f}",
            'Capital Cost': fmt_c(total_cost),
            'Annual O&M (Yr 1)': fmt_c(annual_om), # Clarified label
            'Unit Energy Cost ($/kWh)': f"${energy_cost_per_kwh:.0f}",
            'Unit Power Cost ($/kW)': f"${power_cost_per_kw:.0f}"
        }
        comp_data.append(row)

    if not comp_data: return html.Div("No technology data available for comparison.")
    comparison_table = dash_table.DataTable(
        data=comp_data,
        columns=[{"name": i, "id": i} for i in comp_data[0].keys()],
        style_cell={'textAlign': 'center', 'padding': '5px'},
        style_header={'fontWeight': 'bold', 'backgroundColor': '#f0f0f0', 'textAlign': 'center'},
        style_cell_conditional=[
            {'if': {'column_id': 'Technology'}, 'textAlign': 'left', 'fontWeight': 'bold'},
            {'if': {'filter_query': '{Technology} contains "Current"'}, 'backgroundColor': '#e6f7ff'}
        ],
        style_table={'overflowX': 'auto'}
    )
    return comparison_table


# --- Helper function to create input groups for BESS parameters with Tooltips ---
# ... (create_bess_input_group remains the same) ...
def create_bess_input_group(label, input_id, value, unit, tooltip_text=None, type="number", step=None, min_val=0, style=None):
    """Creates a standard row for a BESS parameter input with label, input, unit, optional tooltip, and optional style."""
    label_content = [label]
    if tooltip_text:
        tooltip_id = f"{input_id}-tooltip"
        label_content.extend([" ", html.I(className="fas fa-info-circle", id=tooltip_id, style={"cursor": "pointer", "color": "#6c757d"}), dbc.Tooltip(tooltip_text, target=tooltip_id, placement="right")])
    row_style = style if style is not None else {}
    return dbc.Row([
            dbc.Label(label_content, html_for=input_id, width=6),
            dbc.Col(dcc.Input(id=input_id, type=type, value=value, className="form-control form-control-sm", step=step, min=min_val), width=4),
            dbc.Col(html.Span(unit, className="input-group-text input-group-text-sm"), width=2),
        ], className="mb-2 align-items-center", style=row_style)


# --- Main Layout Definition ---
# ... (Layout structure remains largely the same, results tab will be populated differently) ...
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
                            html.Div([
                                html.Label("Utility Provider:", className="form-label"),
                                dcc.Dropdown(id=ID_UTILITY_DROPDOWN, options=[{"label": utility, "value": utility} for utility in utility_rates.keys()], value="Custom Utility", clearable=False, className="form-select mb-3"),
                            ], className="mb-3"),
                            html.Div([html.Label("Off-Peak Rate ($/MWh):", className="form-label"), dcc.Input(id=ID_OFF_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["off_peak"], min=0, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Mid-Peak Rate ($/MWh):", className="form-label"), dcc.Input(id=ID_MID_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["mid_peak"], min=0, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Peak Rate ($/MWh):", className="form-label"), dcc.Input(id=ID_PEAK, type="number", value=default_utility_params[KEY_ENERGY_RATES]["peak"], min=0, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Demand Charge ($/kW/month):", className="form-label"), dcc.Input(id=ID_DEMAND_CHARGE, type="number", value=default_utility_params[KEY_DEMAND_CHARGE], min=0, className="form-control")], className="mb-2"),
                            dbc.Checklist(id=ID_SEASONAL_TOGGLE, options=[{"label": "Enable Seasonal Rate Variations", "value": "enabled"}], value=(["enabled"] if default_utility_params[KEY_SEASONAL] else []), switch=True, className="mb-3"),
                            html.Div(id=ID_SEASONAL_CONTAINER, className="mb-3 border p-2 rounded", style={'display': 'none'}),
                            html.H5("Time-of-Use Periods", className="mb-2"),
                            html.P("Define periods covering 24 hours. Gaps will be filled with Off-Peak.", className="small text-muted"),
                            html.Div(id=ID_TOU_CONTAINER), # Populated by callback
                            dbc.Button("Add TOU Period", id=ID_ADD_TOU_BTN, n_clicks=0, size="sm", outline=True, color="success", className="mt-2"),
                        ]),
                        dbc.Card(className="p-3", children=[ # EAF Card
                            html.H4("EAF Parameters", className="mb-3"),
                            html.Div([html.Label("EAF Size (tons):", className="form-label"), dcc.Input(id=ID_EAF_SIZE, type="number", value=nucor_mills["Custom"][KEY_EAF_SIZE], min=1, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Number of EAFs:", className="form-label"), dcc.Input(id=ID_EAF_COUNT, type="number", value=nucor_mills["Custom"]["eaf_count"], min=1, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Grid Power Limit (MW):", className="form-label"), dcc.Input(id=ID_GRID_CAP, type="number", value=nucor_mills["Custom"][KEY_GRID_CAP], min=1, className="form-control")], className="mb-2"),
                            html.Div([html.Label("EAF Cycles per Day:", className="form-label"), dcc.Input(id=ID_CYCLES_PER_DAY, type="number", value=nucor_mills["Custom"][KEY_CYCLES_PER_DAY], min=1, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Avg. Cycle Duration (minutes):", className="form-label"), dcc.Input(id=ID_CYCLE_DURATION, type="number", value=nucor_mills["Custom"][KEY_CYCLE_DURATION], min=1, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Operating Days per Year:", className="form-label"), dcc.Input(id=ID_DAYS_PER_YEAR, type="number", value=nucor_mills["Custom"][KEY_DAYS_PER_YEAR], min=1, max=366, className="form-control")], className="mb-2"),
                        ]),
                    ]), # End Left Column
                    # Right Column: BESS & Financial
                    dbc.Col(md=6, children=[
                        dbc.Card(className="p-3 mb-4", children=[ # BESS Card
                            html.H4("BESS Parameters", className="mb-3"),
                            create_bess_input_group("Total Energy Capacity:", ID_BESS_CAPACITY, default_bess_params_store[KEY_CAPACITY], "MWh", min_val=0.1, tooltip_text="Total energy the BESS can store."),
                            create_bess_input_group("Total Power Rating:", ID_BESS_POWER, default_bess_params_store[KEY_POWER_MAX], "MW", min_val=0.1, tooltip_text="Maximum rate of charge/discharge."),
                            html.Div(id=ID_BESS_C_RATE_DISPLAY, className="mt-2 mb-2 text-muted small"), # C-Rate Display
                            html.Hr(),
                            html.Div([
                                dbc.Label("Select BESS Technology:", html_for=ID_BESS_TECH_DROPDOWN),
                                dcc.Dropdown(id=ID_BESS_TECH_DROPDOWN, options=[{"label": tech, "value": tech} for tech in bess_technology_data.keys()], value=default_bess_params_store[KEY_TECH], clearable=False, className="mb-2"),
                                html.P(id=ID_BESS_EXAMPLE_PRODUCT, className="small text-muted fst-italic"),
                            ], className="mb-3"),
                            html.Hr(),
                            dbc.Card([dbc.CardHeader("Capex (Unit Costs)"), dbc.CardBody([
                                create_bess_input_group("SB + BOS Cost:", ID_BESS_SB_BOS_COST, default_bess_params_store[KEY_SB_BOS_COST], "$/kWh", tooltip_text="Storage Block (Cells, Modules, Racks) + Balance of System (HVAC, Fire Suppression, etc.) cost per kWh."),
                                create_bess_input_group("PCS Cost:", ID_BESS_PCS_COST, default_bess_params_store[KEY_PCS_COST], "$/kW", tooltip_text="Power Conversion System (Inverters, Transformers) cost per kW."),
                                create_bess_input_group("System Integration:", ID_BESS_SYS_INT_COST, default_bess_params_store[KEY_SYS_INT_COST], "$/kWh", tooltip_text="Engineering, Software, Commissioning cost per kWh."),
                                create_bess_input_group("EPC Cost:", ID_BESS_EPC_COST, default_bess_params_store[KEY_EPC_COST], "$/kWh", tooltip_text="Engineering, Procurement, Construction (Installation Labor, Site Prep) cost per kWh."),
                            ])], className="mb-3"),
                            dbc.Card([dbc.CardHeader("Opex"), dbc.CardBody([
                                html.Div(id=ID_BESS_OPEX_CONTAINER), # Populated by callback
                                create_bess_input_group("Round Trip Efficiency:", ID_BESS_RTE, default_bess_params_store[KEY_RTE], "%", min_val=1, tooltip_text="AC-to-AC efficiency for a full charge/discharge cycle."),
                                create_bess_input_group("Insurance Rate:", ID_BESS_INSURANCE, default_bess_params_store[KEY_INSURANCE], "%/yr", step=0.01, tooltip_text="Annual insurance cost as a percentage of initial capital cost."),
                            ])], className="mb-3"),
                            dbc.Card([dbc.CardHeader("Decommissioning"), dbc.CardBody([
                                create_bess_input_group("Disconnect/Removal:", ID_BESS_DISCONNECT_COST, default_bess_params_store[KEY_DISCONNECT_COST], "$/kWh", min_val=None, tooltip_text="Cost to disconnect and remove the system at end-of-life."),
                                create_bess_input_group("Recycling/Disposal:", ID_BESS_RECYCLING_COST, default_bess_params_store[KEY_RECYCLING_COST], "$/kWh", min_val=None, tooltip_text="Net cost of recycling or disposing of components (can be negative if valuable materials)."),
                            ])], className="mb-3"),
                            dbc.Card([dbc.CardHeader("Performance"), dbc.CardBody([
                                create_bess_input_group("Cycle Life:", ID_BESS_CYCLE_LIFE, default_bess_params_store[KEY_CYCLE_LIFE], "cycles", min_val=100, tooltip_text="Number of full charge/discharge cycles until end-of-life (e.g., 80% capacity retention)."),
                                create_bess_input_group("Depth of Discharge:", ID_BESS_DOD, default_bess_params_store[KEY_DOD], "%", min_val=1, tooltip_text="Recommended maximum percentage of capacity to discharge per cycle."),
                                create_bess_input_group("Calendar Life:", ID_BESS_CALENDAR_LIFE, default_bess_params_store[KEY_CALENDAR_LIFE], "years", min_val=1, tooltip_text="Expected lifespan based on time, regardless of cycles."),
                            ])]),
                        ]), # End BESS Card
                        dbc.Card(className="p-3", children=[ # Financial Card
                            html.H4("Financial Parameters", className="mb-3"),
                            html.Div([html.Label("WACC (%):", className="form-label"), dcc.Input(id=ID_WACC, type="number", value=round(default_financial_params[KEY_WACC]*100, 1), min=0, max=100, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Project Lifespan (years):", className="form-label"), dcc.Input(id=ID_LIFESPAN, type="number", value=default_financial_params[KEY_LIFESPAN], min=1, max=50, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Tax Rate (%):", className="form-label"), dcc.Input(id=ID_TAX_RATE, type="number", value=default_financial_params[KEY_TAX_RATE]*100, min=0, max=100, className="form-control")], className="mb-2"),
                            html.Div([html.Label("Inflation Rate (%):", className="form-label"), dcc.Input(id=ID_INFLATION_RATE, type="number", value=default_financial_params[KEY_INFLATION]*100, min=-5, max=100, className="form-control")], className="mb-2"),
                            html.Div([
                                html.Label("Salvage Value (% of initial BESS cost):", className="form-label"),
                                dcc.Input(id=ID_SALVAGE, type="number", value=default_financial_params[KEY_SALVAGE]*100, min=0, max=100, className="form-control"),
                                html.P("Note: End-of-life value primarily driven by Decommissioning costs.", className="small text-muted"),
                            ], className="mb-2"),
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
                dbc.Row([
                    dbc.Col(md=6, children=[ # Federal
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
                    dbc.Col(md=6, children=[ # State & Custom
                        dbc.Card(className="p-3 mb-4", children=[ # State
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
                        dbc.Card(className="p-3", children=[ # Custom
                            html.H4("Custom Incentive", className="mb-3"),
                            dbc.Checklist(id="custom-incentive-enabled", options=[{"label": " Enable Custom Incentive", "value": "enabled"}], value=(["enabled"] if default_incentive_params["custom_incentive_enabled"] else []), className="form-check mb-2"),
                            html.Div([dbc.Label("Incentive Type:", html_for="custom-incentive-type", size="sm"), dcc.RadioItems(id="custom-incentive-type", options=[{"label": " $/kWh", "value": "per_kwh"}, {"label": " % of Cost", "value": "percentage"}], value=default_incentive_params["custom_incentive_type"], inline=True, className="form-check")], className="mb-2 ms-4"),
                            html.Div([dbc.Label("Incentive Amount:", html_for="custom-incentive-amount", size="sm"), dcc.Input(id="custom-incentive-amount", type="number", value=default_incentive_params["custom_incentive_amount"], min=0, className="form-control form-control-sm")], className="mb-2 ms-4"),
                            html.Div([dbc.Label("Description:", html_for="custom-incentive-description", size="sm"), dcc.Input(id="custom-incentive-description", type="text", value=default_incentive_params["custom_incentive_description"], className="form-control form-control-sm")], className="mb-2 ms-4"),
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
                dcc.Loading(id="loading-results", type="circle", children=[
                    html.Div(id=ID_RESULTS_OUTPUT, className="mt-4") # Populated by callback
                ])
            ])
        ]), # End Tab 4

        # Optimization Tab
        dbc.Tab(label="5. Battery Sizing Tool", tab_id="tab-optimization", children=[
             dbc.Container(children=[
                dcc.Loading(id="loading-optimization", type="circle", children=[
                    html.Div(id=ID_OPTIMIZE_OUTPUT, className="mt-4") # Populated by callback
                ])
            ])
        ]), # End Tab 5
    ]), # End Tabs
]) # End Main Container


# --- Callbacks ---

# Tab Navigation
# ... (navigate_tabs remains the same) ...
@app.callback(
    Output(ID_MAIN_TABS, "active_tab"),
    [Input(ID_CONTINUE_PARAMS_BTN, "n_clicks"), Input(ID_CONTINUE_INCENTIVES_BTN, "n_clicks")],
    prevent_initial_call=True,
)
def navigate_tabs(n_params, n_incentives):
    triggered_id = ctx.triggered_id
    if not triggered_id: return dash.no_update
    if triggered_id == ID_CONTINUE_PARAMS_BTN: return "tab-params"
    elif triggered_id == ID_CONTINUE_INCENTIVES_BTN: return "tab-incentives"
    else: return dash.no_update

# EAF Store Update
# ... (update_eaf_params_store remains the same) ...
@app.callback(
    Output(STORE_EAF, "data"),
    [Input(ID_EAF_SIZE, "value"), Input(ID_EAF_COUNT, "value"), Input(ID_GRID_CAP, "value"),
     Input(ID_CYCLES_PER_DAY, "value"), Input(ID_CYCLE_DURATION, "value"), Input(ID_DAYS_PER_YEAR, "value"),
     Input(ID_MILL_DROPDOWN, "value")],
    State(STORE_EAF, "data"),
)
def update_eaf_params_store(size, count, grid_cap, cycles, duration, days, selected_mill, existing_data):
    triggered_id = ctx.triggered_id if ctx.triggered_id else "unknown"
    output_data = existing_data.copy() if existing_data and isinstance(existing_data, dict) else nucor_mills["Custom"].copy()
    if KEY_CYCLE_DURATION_INPUT not in output_data: output_data[KEY_CYCLE_DURATION_INPUT] = output_data.get(KEY_CYCLE_DURATION, 0)

    if triggered_id == ID_MILL_DROPDOWN:
        output_data = nucor_mills.get(selected_mill, nucor_mills["Custom"]).copy()
        output_data[KEY_CYCLE_DURATION_INPUT] = output_data.get(KEY_CYCLE_DURATION, 0)
    else:
        if size is not None: output_data[KEY_EAF_SIZE] = size
        if count is not None: output_data["eaf_count"] = count
        if grid_cap is not None: output_data[KEY_GRID_CAP] = grid_cap
        if cycles is not None: output_data[KEY_CYCLES_PER_DAY] = cycles
        if duration is not None:
            output_data[KEY_CYCLE_DURATION] = duration # Store the value shown in UI
            output_data[KEY_CYCLE_DURATION_INPUT] = duration # Track user input explicitly
        if days is not None: output_data[KEY_DAYS_PER_YEAR] = days

    # Ensure cycle duration used in calculations is valid (prioritize user input)
    try: input_duration = float(output_data.get(KEY_CYCLE_DURATION_INPUT, 0))
    except: input_duration = 0.0
    try: base_duration = float(output_data.get(KEY_CYCLE_DURATION, 0)) # Base from mill or previous input
    except: base_duration = 0.0

    if input_duration > 0: output_data[KEY_CYCLE_DURATION] = input_duration # Use valid user input
    elif base_duration > 0: output_data[KEY_CYCLE_DURATION] = base_duration # Fallback to base
    else: output_data[KEY_CYCLE_DURATION] = 36.0 # Ultimate fallback

    return output_data


# Financial Store Update
# ... (update_financial_params_store remains the same) ...
@app.callback(
    Output(STORE_FINANCIAL, "data"),
    [Input(ID_WACC, "value"), Input(ID_LIFESPAN, "value"), Input(ID_TAX_RATE, "value"),
     Input(ID_INFLATION_RATE, "value"), Input(ID_SALVAGE, "value")],
)
def update_financial_params_store(wacc, lifespan, tax, inflation, salvage):
    return {
        KEY_WACC: wacc / 100.0 if wacc is not None else default_financial_params[KEY_WACC],
        KEY_LIFESPAN: lifespan,
        KEY_TAX_RATE: tax / 100.0 if tax is not None else default_financial_params[KEY_TAX_RATE],
        KEY_INFLATION: inflation / 100.0 if inflation is not None else default_financial_params[KEY_INFLATION],
        KEY_SALVAGE: salvage / 100.0 if salvage is not None else default_financial_params[KEY_SALVAGE],
    }

# Incentive Store Update
# ... (update_incentive_params_store remains the same) ...
@app.callback(
    Output(STORE_INCENTIVE, "data"),
    [Input(ID_ITC_ENABLED, "value"), Input(ID_ITC_PERCENT, "value"), Input("ceic-enabled", "value"), Input("ceic-percentage", "value"),
     Input("bonus-credit-enabled", "value"), Input("bonus-credit-percentage", "value"), Input("sgip-enabled", "value"), Input("sgip-amount", "value"),
     Input("ess-enabled", "value"), Input("ess-amount", "value"), Input("mabi-enabled", "value"), Input("mabi-amount", "value"),
     Input("cs-enabled", "value"), Input("cs-amount", "value"), Input("custom-incentive-enabled", "value"), Input("custom-incentive-type", "value"),
     Input("custom-incentive-amount", "value"), Input("custom-incentive-description", "value")],
)
def update_incentive_params_store(itc_en, itc_pct, ceic_en, ceic_pct, bonus_en, bonus_pct, sgip_en, sgip_amt, ess_en, ess_amt, mabi_en, mabi_amt, cs_en, cs_amt, custom_en, custom_type, custom_amt, custom_desc):
    return {
        "itc_enabled": "enabled" in itc_en, "itc_percentage": itc_pct,
        "ceic_enabled": "enabled" in ceic_en, "ceic_percentage": ceic_pct,
        "bonus_credit_enabled": "enabled" in bonus_en, "bonus_credit_percentage": bonus_pct,
        "sgip_enabled": "enabled" in sgip_en, "sgip_amount": sgip_amt,
        "ess_enabled": "enabled" in ess_en, "ess_amount": ess_amt,
        "mabi_enabled": "enabled" in mabi_en, "mabi_amount": mabi_amt,
        "cs_enabled": "enabled" in cs_en, "cs_amount": cs_amt,
        "custom_incentive_enabled": "enabled" in custom_en, "custom_incentive_type": custom_type,
        "custom_incentive_amount": custom_amt, "custom_incentive_description": custom_desc,
    }

# Utility Store Update
# ... (update_utility_params_store remains the same) ...
@app.callback(
    Output(STORE_UTILITY, "data"),
    [Input(ID_UTILITY_DROPDOWN, "value"), Input(ID_OFF_PEAK, "value"), Input(ID_MID_PEAK, "value"), Input(ID_PEAK, "value"),
     Input(ID_DEMAND_CHARGE, "value"), Input(ID_SEASONAL_TOGGLE, "value"), Input("winter-multiplier", "value"),
     Input("summer-multiplier", "value"), Input("shoulder-multiplier", "value"), Input("winter-months", "value"),
     Input("summer-months", "value"), Input("shoulder-months", "value"), Input({"type": "tou-start", "index": ALL}, "value"),
     Input({"type": "tou-end", "index": ALL}, "value"), Input({"type": "tou-rate", "index": ALL}, "value")],
    State(STORE_UTILITY, "data"),
)
def update_utility_params_store(utility_provider, off_peak_rate, mid_peak_rate, peak_rate, demand_charge, seasonal_toggle_value, winter_mult, summer_mult, shoulder_mult, winter_months_str, summer_months_str, shoulder_months_str, tou_starts, tou_ends, tou_rates, existing_data):
    triggered_id = ctx.triggered_id
    params = {}
    if isinstance(triggered_id, str) and triggered_id == ID_UTILITY_DROPDOWN:
        params = utility_rates.get(utility_provider, default_utility_params).copy()
        params[KEY_TOU_RAW] = params.get("tou_periods", default_utility_params[KEY_TOU_RAW])
    elif existing_data: params = existing_data.copy()
    else: params = default_utility_params.copy()

    params[KEY_ENERGY_RATES] = {"off_peak": off_peak_rate, "mid_peak": mid_peak_rate, "peak": peak_rate}
    params[KEY_DEMAND_CHARGE] = demand_charge
    is_seasonal_enabled = seasonal_toggle_value and "enabled" in seasonal_toggle_value
    params[KEY_SEASONAL] = is_seasonal_enabled

    def parse_months(month_str, default_list):
        if not isinstance(month_str, str): return default_list
        try:
            parsed = [int(m.strip()) for m in month_str.split(',') if m.strip() and 1 <= int(m.strip()) <= 12]
            return parsed if parsed else default_list
        except ValueError: return default_list

    if is_seasonal_enabled:
        params[KEY_WINTER_MONTHS] = parse_months(winter_months_str, default_utility_params[KEY_WINTER_MONTHS])
        params[KEY_SUMMER_MONTHS] = parse_months(summer_months_str, default_utility_params[KEY_SUMMER_MONTHS])
        params[KEY_SHOULDER_MONTHS] = parse_months(shoulder_months_str, default_utility_params[KEY_SHOULDER_MONTHS])
        params[KEY_WINTER_MULT] = winter_mult if winter_mult is not None else default_utility_params[KEY_WINTER_MULT]
        params[KEY_SUMMER_MULT] = summer_mult if summer_mult is not None else default_utility_params[KEY_SUMMER_MULT]
        params[KEY_SHOULDER_MULT] = shoulder_mult if shoulder_mult is not None else default_utility_params[KEY_SHOULDER_MULT]
    else: # Reset to defaults if toggle off
        params[KEY_WINTER_MONTHS] = default_utility_params[KEY_WINTER_MONTHS]
        params[KEY_SUMMER_MONTHS] = default_utility_params[KEY_SUMMER_MONTHS]
        params[KEY_SHOULDER_MONTHS] = default_utility_params[KEY_SHOULDER_MONTHS]
        params[KEY_WINTER_MULT] = default_utility_params[KEY_WINTER_MULT]
        params[KEY_SUMMER_MULT] = default_utility_params[KEY_SUMMER_MULT]
        params[KEY_SHOULDER_MULT] = default_utility_params[KEY_SHOULDER_MULT]

    if isinstance(triggered_id, str) and triggered_id == ID_UTILITY_DROPDOWN:
        raw_tou_periods = params.get(KEY_TOU_RAW, default_utility_params[KEY_TOU_RAW])
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
        params[KEY_TOU_RAW] = raw_tou_periods

    params[KEY_TOU_FILLED] = fill_tou_gaps(params.get(KEY_TOU_RAW, []))
    # pprint.pprint(params) # Optional debug print
    return params


# Mill Info Card Update
# ... (update_mill_info remains the same) ...
@app.callback(
    Output(ID_MILL_INFO_CARD, "children"),
    Input(ID_MILL_DROPDOWN, "value")
)
def update_mill_info(selected_mill):
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]
        selected_mill = "Custom"
        card_header_class = "card-header bg-secondary text-white"
    else:
        mill_data = nucor_mills[selected_mill]
        card_header_class = "card-header bg-primary text-white"
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
        ]),
    ])
    return info_card

# Update Params from Mill Selection
# ... (update_params_from_mill remains the same) ...
@app.callback(
    [Output(ID_UTILITY_DROPDOWN, "value"), Output(ID_OFF_PEAK, "value"), Output(ID_MID_PEAK, "value"), Output(ID_PEAK, "value"),
     Output(ID_DEMAND_CHARGE, "value"), Output(ID_SEASONAL_TOGGLE, "value"), Output(ID_EAF_SIZE, "value"), Output(ID_EAF_COUNT, "value"),
     Output(ID_GRID_CAP, "value"), Output(ID_CYCLES_PER_DAY, "value"), Output(ID_CYCLE_DURATION, "value"), Output(ID_DAYS_PER_YEAR, "value"),
     Output(ID_TOU_CONTAINER, "children", allow_duplicate=True)],
    Input(ID_MILL_DROPDOWN, "value"),
    prevent_initial_call=True,
)
def update_params_from_mill(selected_mill):
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]; utility_provider = "Custom Utility"
        utility_data = utility_rates.get(utility_provider, default_utility_params)
    else:
        mill_data = nucor_mills[selected_mill]
        utility_provider = mill_data.get("utility", "Custom Utility")
        if utility_provider not in utility_rates:
            utility_data = utility_rates["Custom Utility"]; utility_provider = "Custom Utility"
        else: utility_data = utility_rates[utility_provider]
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
    tou_periods_for_ui = utility_data.get("tou_periods", default_utility_params[KEY_TOU_RAW])
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)
    return [utility_provider, off_peak, mid_peak, peak, demand, seasonal_enabled, eaf_size, eaf_count, grid_cap, cycles, duration, days, tou_elements_ui]

# Update Rates from Provider Dropdown (Manual Override)
# ... (update_rates_from_provider_manual remains the same) ...
@app.callback(
    [Output(ID_OFF_PEAK, "value", allow_duplicate=True), Output(ID_MID_PEAK, "value", allow_duplicate=True), Output(ID_PEAK, "value", allow_duplicate=True),
     Output(ID_DEMAND_CHARGE, "value", allow_duplicate=True), Output(ID_SEASONAL_TOGGLE, "value", allow_duplicate=True),
     Output(ID_TOU_CONTAINER, "children", allow_duplicate=True)],
    Input(ID_UTILITY_DROPDOWN, "value"),
    prevent_initial_call=True,
)
def update_rates_from_provider_manual(selected_utility):
    if not ctx.triggered_id or ctx.triggered_id != ID_UTILITY_DROPDOWN: return dash.no_update
    utility_data = utility_rates.get(selected_utility, utility_rates["Custom Utility"])
    off_peak = utility_data.get(KEY_ENERGY_RATES, {}).get("off_peak", default_utility_params[KEY_ENERGY_RATES]["off_peak"])
    mid_peak = utility_data.get(KEY_ENERGY_RATES, {}).get("mid_peak", default_utility_params[KEY_ENERGY_RATES]["mid_peak"])
    peak = utility_data.get(KEY_ENERGY_RATES, {}).get("peak", default_utility_params[KEY_ENERGY_RATES]["peak"])
    demand = utility_data.get(KEY_DEMAND_CHARGE, default_utility_params[KEY_DEMAND_CHARGE])
    seasonal_enabled = ["enabled"] if utility_data.get(KEY_SEASONAL, default_utility_params[KEY_SEASONAL]) else []
    tou_periods_for_ui = utility_data.get("tou_periods", default_utility_params[KEY_TOU_RAW])
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)
    return off_peak, mid_peak, peak, demand, seasonal_enabled, tou_elements_ui

# Seasonal Rates UI Toggle
# ... (update_seasonal_rates_ui remains the same) ...
@app.callback(
    [Output(ID_SEASONAL_CONTAINER, "children"), Output(ID_SEASONAL_CONTAINER, "style")],
    [Input(ID_SEASONAL_TOGGLE, "value"), Input(ID_UTILITY_DROPDOWN, "value")],
)
def update_seasonal_rates_ui(toggle_value, selected_utility):
    is_enabled = toggle_value and "enabled" in toggle_value
    display_style = {"display": "block", "border": "1px solid #ccc", "padding": "10px", "border-radius": "5px", "background-color": "#f9f9f9"} if is_enabled else {"display": "none"}
    utility_data_source = utility_rates.get(selected_utility, default_utility_params)
    winter_mult = utility_data_source.get(KEY_WINTER_MULT, default_utility_params[KEY_WINTER_MULT])
    summer_mult = utility_data_source.get(KEY_SUMMER_MULT, default_utility_params[KEY_SUMMER_MULT])
    shoulder_mult = utility_data_source.get(KEY_SHOULDER_MULT, default_utility_params[KEY_SHOULDER_MULT])
    winter_m = ",".join(map(str, utility_data_source.get(KEY_WINTER_MONTHS, default_utility_params[KEY_WINTER_MONTHS])))
    summer_m = ",".join(map(str, utility_data_source.get(KEY_SUMMER_MONTHS, default_utility_params[KEY_SUMMER_MONTHS])))
    shoulder_m = ",".join(map(str, utility_data_source.get(KEY_SHOULDER_MONTHS, default_utility_params[KEY_SHOULDER_MONTHS])))
    seasonal_ui = html.Div([
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
    return seasonal_ui, display_style

# TOU UI Management Helper
# ... (generate_tou_ui_elements remains the same) ...
def generate_tou_ui_elements(tou_periods_list):
    tou_elements = []
    if not tou_periods_list: tou_periods_list = [(0.0, 24.0, "off_peak")]
    for i, period_data in enumerate(tou_periods_list):
        if isinstance(period_data, (list, tuple)) and len(period_data) == 3: start, end, rate_type = period_data
        else: start, end, rate_type = (0.0, 0.0, "off_peak")
        tou_row = html.Div([
            html.Div([
                html.Div(dcc.Input(id={"type": "tou-start", "index": i}, type="number", min=0, max=24, step=0.1, value=start, className="form-control form-control-sm", placeholder="Start Hr (0-24)"), className="col-3"),
                html.Div(dcc.Input(id={"type": "tou-end", "index": i}, type="number", min=0, max=24, step=0.1, value=end, className="form-control form-control-sm", placeholder="End Hr (0-24)"), className="col-3"),
                html.Div(dcc.Dropdown(id={"type": "tou-rate", "index": i}, options=[{"label": "Off-Peak", "value": "off_peak"}, {"label": "Mid-Peak", "value": "mid_peak"}, {"label": "Peak", "value": "peak"}], value=rate_type, clearable=False, className="form-select form-select-sm"), className="col-4"),
                html.Div(dbc.Button("×", id={"type": "remove-tou", "index": i}, color="danger", size="sm", title="Remove Period", style={"lineHeight": "1"}, disabled=len(tou_periods_list) <= 1), className="col-2 d-flex align-items-center justify-content-center"),
            ], className="row g-1 mb-1 align-items-center"),
        ], id=f"tou-row-{i}", className="tou-period-row")
        tou_elements.append(tou_row)
    return tou_elements

# TOU UI Add/Remove Callback
# ... (modify_tou_rows remains the same) ...
@app.callback(
    Output(ID_TOU_CONTAINER, "children", allow_duplicate=True),
    [Input(ID_ADD_TOU_BTN, "n_clicks"), Input({"type": "remove-tou", "index": ALL}, "n_clicks")],
    State(ID_TOU_CONTAINER, "children"),
    prevent_initial_call=True,
)
def modify_tou_rows(add_clicks, remove_clicks_list, current_rows):
    triggered_input = ctx.triggered_id
    if not triggered_input: return dash.no_update
    new_rows = current_rows[:] if current_rows else []
    if triggered_input == ID_ADD_TOU_BTN:
        new_index = len(new_rows)
        default_start = 0.0
        if new_rows:
            try: default_start = current_rows[-1]["props"]["children"][0]["props"]["children"][1]["props"]["children"]["props"].get("value", 0.0)
            except: pass
        new_row_elements = generate_tou_ui_elements([(default_start, default_start, "off_peak")])
        new_row_div = new_row_elements[0]
        new_row_div.id = f"tou-row-{new_index}"
        for col in new_row_div.children[0].children:
            if hasattr(col.children, "id") and isinstance(col.children.id, dict): col.children.id["index"] = new_index
        new_rows.append(new_row_div)
    elif isinstance(triggered_input, dict) and triggered_input.get("type") == "remove-tou":
        if len(new_rows) > 1:
            clicked_index = triggered_input["index"]
            row_to_remove_id = f"tou-row-{clicked_index}"
            new_rows = [row for row in new_rows if row.get("props", {}).get("id") != row_to_remove_id]
        else: print("Cannot remove the last TOU period row.")
    num_rows = len(new_rows)
    for i, row in enumerate(new_rows):
        try: row["props"]["children"][0]["props"]["children"][-1]["props"]["children"]["props"]["disabled"] = num_rows <= 1
        except: print(f"Warning: Could not find or update remove button state for row {i}")
    return new_rows

# Input Validation
# ... (validate_inputs remains the same) ...
@app.callback(
    [Output(ID_VALIDATION_ERR, "children"), Output(ID_VALIDATION_ERR, "is_open"),
     Output(ID_CALCULATION_ERR, "is_open", allow_duplicate=True)],
    [Input(ID_CALC_BTN, "n_clicks"), Input(ID_OPTIMIZE_BTN, "n_clicks"),
     Input(STORE_UTILITY, "data"), Input(STORE_EAF, "data"), Input(STORE_BESS, "data"), Input(STORE_FINANCIAL, "data")],
    prevent_initial_call=True,
)
def validate_inputs(calc_clicks, opt_clicks, utility_params, eaf_params, bess_params, fin_params):
    triggered_id = ctx.triggered_id if ctx.triggered_id else "initial_load_or_unknown"
    is_calc_attempt = triggered_id in [ID_CALC_BTN, ID_OPTIMIZE_BTN]
    if not is_calc_attempt: return "", False, False
    errors = []
    # Utility Validation
    if not utility_params: errors.append("Utility parameters are missing.")
    else:
        rates = utility_params.get(KEY_ENERGY_RATES, {})
        if rates.get("off_peak", -1) < 0: errors.append("Off-Peak Rate cannot be negative.")
        if rates.get("mid_peak", -1) < 0: errors.append("Mid-Peak Rate cannot be negative.")
        if rates.get("peak", -1) < 0: errors.append("Peak Rate cannot be negative.")
        if utility_params.get(KEY_DEMAND_CHARGE, -1) < 0: errors.append("Demand Charge cannot be negative.")
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
        if bess_params.get(KEY_CYCLE_LIFE, 0) <= 0: errors.append("BESS Cycle Life must be positive.")
        if not (0 < bess_params.get(KEY_DOD, 0) <= 100): errors.append("BESS DoD must be between 0% and 100%.")
        if bess_params.get(KEY_CALENDAR_LIFE, 0) <= 0: errors.append("BESS Calendar Life must be positive.")
    # Financial Validation
    if not fin_params: errors.append("Financial parameters are missing.")
    else:
        if not (0 <= fin_params.get(KEY_WACC, -1) <= 1): errors.append("WACC must be between 0% and 100%.")
        if fin_params.get(KEY_LIFESPAN, 0) <= 0: errors.append("Project Lifespan must be positive.")
        if not (0 <= fin_params.get(KEY_TAX_RATE, -1) <= 1): errors.append("Tax Rate must be between 0% and 100%.")
        if fin_params.get(KEY_INFLATION, None) is None: errors.append("Inflation Rate is missing.")
        if not (0 <= fin_params.get(KEY_SALVAGE, -1) <= 1): errors.append("Salvage Value must be between 0% and 100%.")

    output_elements = []
    is_open = False
    calc_error_open = False
    if errors:
        output_elements.append(html.H5("Validation Errors:", className="text-danger"))
        output_elements.append(html.Ul([html.Li(e) for e in errors]))
        is_open = True
        calc_error_open = False # Hide calculation error if validation fails
    return output_elements, is_open, calc_error_open

# For C-Rate Display Update
# ... (update_c_rate_display remains the same) ...
@app.callback(
    Output(ID_BESS_C_RATE_DISPLAY, "children"),
    [Input(ID_BESS_CAPACITY, "value"), Input(ID_BESS_POWER, "value")]
)
def update_c_rate_display(capacity, power):
    try:
        if capacity is not None and power is not None and float(capacity) > 0:
            c_rate = float(power) / float(capacity)
            return f"Calculated C-Rate: {c_rate:.2f} h⁻¹"
        elif capacity is not None and capacity == 0 and power is not None and power > 0:
             return "C-Rate: Infinite (Capacity is zero)"
        else: return ""
    except: return ""

# BESS Inputs Update on Technology Dropdown Change
# ... (update_bess_inputs_from_technology remains the same) ...
@app.callback(
    [Output(ID_BESS_EXAMPLE_PRODUCT, "children"), Output(ID_BESS_SB_BOS_COST, "value"), Output(ID_BESS_PCS_COST, "value"),
     Output(ID_BESS_EPC_COST, "value"), Output(ID_BESS_SYS_INT_COST, "value"), Output(ID_BESS_OPEX_CONTAINER, "children"),
     Output(ID_BESS_RTE, "value"), Output(ID_BESS_INSURANCE, "value"), Output(ID_BESS_DISCONNECT_COST, "value"),
     Output(ID_BESS_RECYCLING_COST, "value"), Output(ID_BESS_CYCLE_LIFE, "value"), Output(ID_BESS_DOD, "value"),
     Output(ID_BESS_CALENDAR_LIFE, "value")],
    Input(ID_BESS_TECH_DROPDOWN, "value"),
    prevent_initial_call=True,
)
def update_bess_inputs_from_technology(selected_technology):
    if not selected_technology or selected_technology not in bess_technology_data: selected_technology = "LFP"
    tech_data = bess_technology_data[selected_technology]
    show_om_kwhyr = KEY_OM_KWHR_YR in tech_data
    style_fixed_om = {"display": "none"} if show_om_kwhyr else {"display": "flex"}
    style_om_kwhyr = {"display": "flex"} if show_om_kwhyr else {"display": "none"}
    fixed_om_input_group = create_bess_input_group("Fixed O&M:", ID_BESS_FIXED_OM, tech_data.get(KEY_FIXED_OM, 0), "$/kW/yr", tooltip_text="Annual Fixed Operation & Maintenance cost per kW of power capacity (common for Li-ion, Flow).", style=style_fixed_om)
    om_kwhyr_input_group = create_bess_input_group("O&M Cost:", ID_BESS_OM_KWHR_YR, tech_data.get(KEY_OM_KWHR_YR, 0), "$/kWh/yr", tooltip_text="Annual Operation & Maintenance cost per kWh of energy capacity (e.g., for Supercapacitors).", style=style_om_kwhyr)
    opex_container_children = [fixed_om_input_group, om_kwhyr_input_group]
    return (
        tech_data.get(KEY_EXAMPLE_PRODUCT, "N/A"), tech_data.get(KEY_SB_BOS_COST, 0), tech_data.get(KEY_PCS_COST, 0),
        tech_data.get(KEY_EPC_COST, 0), tech_data.get(KEY_SYS_INT_COST, 0), opex_container_children,
        tech_data.get(KEY_RTE, 0), tech_data.get(KEY_INSURANCE, 0), tech_data.get(KEY_DISCONNECT_COST, 0),
        tech_data.get(KEY_RECYCLING_COST, 0), tech_data.get(KEY_CYCLE_LIFE, 0), tech_data.get(KEY_DOD, 0),
        tech_data.get(KEY_CALENDAR_LIFE, 0),
    )

# BESS Store Update (Using V7 Logic - State-based Update)
@app.callback(
    Output(STORE_BESS, "data"),
    [Input(ID_BESS_CAPACITY, "value"), Input(ID_BESS_POWER, "value"), Input(ID_BESS_TECH_DROPDOWN, "value"),
     Input(ID_BESS_SB_BOS_COST, "value"), Input(ID_BESS_PCS_COST, "value"), Input(ID_BESS_EPC_COST, "value"),
     Input(ID_BESS_SYS_INT_COST, "value"), Input(ID_BESS_FIXED_OM, "value"), Input(ID_BESS_OM_KWHR_YR, "value"),
     Input(ID_BESS_RTE, "value"), Input(ID_BESS_INSURANCE, "value"), Input(ID_BESS_DISCONNECT_COST, "value"),
     Input(ID_BESS_RECYCLING_COST, "value"), Input(ID_BESS_CYCLE_LIFE, "value"), Input(ID_BESS_DOD, "value"),
     Input(ID_BESS_CALENDAR_LIFE, "value")],
    State(STORE_BESS, "data"),
    prevent_initial_call=True,
)
def update_bess_params_store(capacity, power, technology, sb_bos_cost, pcs_cost, epc_cost, sys_int_cost, fixed_om, om_kwhyr, rte, insurance, disconnect_cost, recycling_cost, cycle_life, dod, calendar_life, existing_data):
    if not ctx.triggered_id: return dash.no_update
    triggered_prop_id = ctx.triggered[0]["prop_id"]
    triggered_id_base = triggered_prop_id.split(".")[0]
    if '{' in triggered_id_base: triggered_id_base = json.loads(triggered_id_base)['type']

    # print(f"\n--- DEBUG update_bess_params_store (V7) --- Triggered by: {triggered_id_base}") # Optional debug
    store_data = existing_data.copy() if existing_data and isinstance(existing_data, dict) else default_bess_params_store.copy()

    if triggered_id_base == ID_BESS_TECH_DROPDOWN:
        selected_technology = technology
        if selected_technology not in bess_technology_data: selected_technology = "LFP"
        tech_defaults = bess_technology_data[selected_technology].copy()
        store_data.update(tech_defaults)
        store_data[KEY_TECH] = selected_technology
        # Preserve user's capacity/power
        store_data[KEY_CAPACITY] = capacity
        store_data[KEY_POWER_MAX] = power
    elif triggered_id_base == ID_BESS_CAPACITY: store_data[KEY_CAPACITY] = capacity
    elif triggered_id_base == ID_BESS_POWER: store_data[KEY_POWER_MAX] = power
    elif triggered_id_base == ID_BESS_SB_BOS_COST: store_data[KEY_SB_BOS_COST] = sb_bos_cost
    elif triggered_id_base == ID_BESS_PCS_COST: store_data[KEY_PCS_COST] = pcs_cost
    elif triggered_id_base == ID_BESS_EPC_COST: store_data[KEY_EPC_COST] = epc_cost
    elif triggered_id_base == ID_BESS_SYS_INT_COST: store_data[KEY_SYS_INT_COST] = sys_int_cost
    elif triggered_id_base == ID_BESS_RTE: store_data[KEY_RTE] = rte
    elif triggered_id_base == ID_BESS_INSURANCE: store_data[KEY_INSURANCE] = insurance
    elif triggered_id_base == ID_BESS_DISCONNECT_COST: store_data[KEY_DISCONNECT_COST] = disconnect_cost
    elif triggered_id_base == ID_BESS_RECYCLING_COST: store_data[KEY_RECYCLING_COST] = recycling_cost
    elif triggered_id_base == ID_BESS_CYCLE_LIFE: store_data[KEY_CYCLE_LIFE] = cycle_life
    elif triggered_id_base == ID_BESS_DOD: store_data[KEY_DOD] = dod
    elif triggered_id_base == ID_BESS_CALENDAR_LIFE: store_data[KEY_CALENDAR_LIFE] = calendar_life
    # Handle O&M based on intended type for the *current* tech in store
    current_tech_in_store = store_data.get(KEY_TECH, "LFP")
    intended_om_is_kwhyr = KEY_OM_KWHR_YR in bess_technology_data.get(current_tech_in_store, {})
    if triggered_id_base == ID_BESS_FIXED_OM:
        if not intended_om_is_kwhyr:
            store_data[KEY_FIXED_OM] = fixed_om
            if KEY_OM_KWHR_YR in store_data: del store_data[KEY_OM_KWHR_YR]
    elif triggered_id_base == ID_BESS_OM_KWHR_YR:
        if intended_om_is_kwhyr:
            store_data[KEY_OM_KWHR_YR] = om_kwhyr
            if KEY_FIXED_OM in store_data: del store_data[KEY_FIXED_OM]

    # print("FINAL Stored BESS Params:"); pprint.pprint(store_data) # Optional debug
    return store_data


# --- Main Calculation Callback (REVISED OUTPUT) ---
@app.callback(
    [Output(ID_RESULTS_OUTPUT, "children"), Output(STORE_RESULTS, "data"),
     Output(ID_CALCULATION_ERR, "children"), Output(ID_CALCULATION_ERR, "is_open")],
    Input(ID_CALC_BTN, "n_clicks"),
    [State(STORE_EAF, "data"), State(STORE_BESS, "data"), State(STORE_UTILITY, "data"),
     State(STORE_FINANCIAL, "data"), State(STORE_INCENTIVE, "data"), State(ID_VALIDATION_ERR, "children")],
    prevent_initial_call=True,
)
def display_calculation_results(n_clicks, eaf_params, bess_params, utility_params, financial_params, incentive_params, validation_errors):
    """Triggers calculations and displays results with enhanced layout."""
    results_output = html.Div("Click 'Calculate Results' to generate the analysis.", className="text-center text-muted")
    stored_data = {}
    error_output = ""
    error_open = False

    if n_clicks == 0: return results_output, stored_data, error_output, error_open
    if validation_errors:
        error_output = html.Div([html.H5("Cannot Calculate - Validation Errors Exist", className="text-danger"), html.P("Please fix the errors listed above before calculating.")])
        error_open = True
        return results_output, stored_data, error_output, error_open
    if not all([eaf_params, bess_params, utility_params, financial_params, incentive_params]):
        error_output = html.Div([html.H5("Internal Error", className="text-danger"), html.P("Could not retrieve all required parameters.")])
        error_open = True
        return results_output, stored_data, error_output, error_open

    try:
        current_technology = bess_params.get(KEY_TECH, "LFP")
        print(f"DEBUG: Starting calculation for technology: {current_technology}")

        # --- Perform Calculations ---
        billing_results = calculate_annual_billings(eaf_params, bess_params, utility_params)
        incentive_results = calculate_incentives(bess_params, incentive_params)
        # Pass total annual discharge for LCOS calculation
        financial_metrics = calculate_financial_metrics(
            bess_params, financial_params, eaf_params,
            billing_results["annual_savings"],
            billing_results["total_annual_discharge_mwh"], # Pass discharge here
            incentive_results
        )

        # Store results
        stored_data = {
            "billing": billing_results, "incentives": incentive_results, "financials": financial_metrics,
            "inputs": {"eaf": eaf_params, "bess": bess_params, "utility": utility_params, "financial": financial_params, "incentive": incentive_params}
        }

        # --- Generate Plotting Data ---
        # ... (plotting data generation remains the same) ...
        plot_data_calculated = False; plot_error_message = ""
        time_plot, eaf_power_plot, grid_power_plot, bess_power_plot = [], [], [], []
        max_y_plot = 60
        try:
            plot_cycle_duration_min = eaf_params.get(KEY_CYCLE_DURATION_INPUT, 36)
            plot_cycle_duration_min = max(1, float(plot_cycle_duration_min)) if plot_cycle_duration_min is not None else 36.0
            time_plot = np.linspace(0, plot_cycle_duration_min, 200)
            eaf_power_plot = calculate_eaf_profile(time_plot, eaf_params.get(KEY_EAF_SIZE, 100), plot_cycle_duration_min)
            grid_power_plot, bess_power_plot = calculate_grid_bess_power(eaf_power_plot, eaf_params.get(KEY_GRID_CAP, 35), bess_params.get(KEY_POWER_MAX, 20))
            plot_data_calculated = True
            max_y_plot = max(np.max(eaf_power_plot) if len(eaf_power_plot) > 0 else 0, eaf_params.get(KEY_GRID_CAP, 35)) * 1.15
            max_y_plot = max(10, max_y_plot)
        except Exception as plot_err:
            plot_error_message = f"Error generating single cycle plot data: {plot_err}"
            print(plot_error_message)


        # --- Formatting Helpers ---
        def fmt_c(v, decimals=0): return f"${v:,.{decimals}f}" if pd.notna(v) and isinstance(v, (int, float)) else "N/A"
        def fmt_p(v): return f"{v:.1%}" if pd.notna(v) and isinstance(v, (int, float)) and abs(v) <= 5 else (f"{'+' if v > 0 else ''}>500%" if pd.notna(v) and abs(v) > 5 else "N/A")
        def fmt_y(v): return "Never" if pd.isna(v) or v == float('inf') else ("< 0 (Immediate)" if v < 0 else f"{v:.1f} yrs")
        def fmt_n(v, decimals=0): return f"{v:,.{decimals}f}" if pd.notna(v) and isinstance(v, (int, float)) else "N/A"

        # --- Create Results Components ---

        # KPI Cards
        kpi_card_style = {"textAlign": "center", "padding": "10px"}
        kpi_label_style = {"fontSize": "0.9em", "color": "grey"}
        kpi_value_style = {"fontSize": "1.5em", "fontWeight": "bold"}

        kpi_cards = dbc.Row([
            dbc.Col(dbc.Card([html.Div("NPV", style=kpi_label_style), html.Div(fmt_c(financial_metrics.get("npv")), style=kpi_value_style)], style=kpi_card_style), md=3),
            dbc.Col(dbc.Card([html.Div("IRR", style=kpi_label_style), html.Div(fmt_p(financial_metrics.get("irr")), style=kpi_value_style)], style=kpi_card_style), md=3),
            dbc.Col(dbc.Card([html.Div("Payback", style=kpi_label_style), html.Div(fmt_y(financial_metrics.get("payback_years")), style=kpi_value_style)], style=kpi_card_style), md=3),
            dbc.Col(dbc.Card([html.Div("LCOS ($/MWh)", style=kpi_label_style), html.Div(fmt_c(financial_metrics.get("lcos")), style=kpi_value_style)], style=kpi_card_style), md=3),
        ], className="mb-4")

        # Assumptions Box
        assumptions_box = dbc.Card([
            dbc.CardHeader("Key Assumptions for Calculation"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(f"BESS Tech: {bess_params.get(KEY_TECH, 'N/A')}", md=4),
                    dbc.Col(f"Capacity: {fmt_n(bess_params.get(KEY_CAPACITY), 1)} MWh", md=4),
                    dbc.Col(f"Power: {fmt_n(bess_params.get(KEY_POWER_MAX), 1)} MW", md=4),
                ]),
                dbc.Row([
                    dbc.Col(f"WACC: {fmt_p(financial_params.get(KEY_WACC))}", md=3),
                    dbc.Col(f"Inflation: {fmt_p(financial_params.get(KEY_INFLATION))}", md=3),
                    dbc.Col(f"Tax Rate: {fmt_p(financial_params.get(KEY_TAX_RATE))}", md=3),
                    dbc.Col(f"Project Life: {fmt_n(financial_params.get(KEY_LIFESPAN))} yrs", md=3),
                ]),
                 dbc.Row([
                    dbc.Col(f"Grid Cap: {fmt_n(eaf_params.get(KEY_GRID_CAP))} MW", md=4),
                    dbc.Col(f"Cycles/Day: {fmt_n(eaf_params.get(KEY_CYCLES_PER_DAY))}", md=4),
                    dbc.Col(f"Days/Year: {fmt_n(eaf_params.get(KEY_DAYS_PER_YEAR))}", md=4),
                ]),
            ])
        ], className="mb-4", color="light")

        # Annual Costs & Savings Card (Simplified)
        savings_card = dbc.Card([
            dbc.CardHeader("Annual Costs & Savings (Year 1 Estimates)"),
            dbc.CardBody(html.Table([
                html.Tr([html.Td("Baseline Bill (No BESS)"), html.Td(fmt_c(billing_results.get("annual_bill_without_bess")))]),
                html.Tr([html.Td("Projected Bill (With BESS)"), html.Td(fmt_c(billing_results.get("annual_bill_with_bess")))]),
                html.Tr([html.Td("Gross Annual Utility Savings"), html.Td(html.Strong(fmt_c(billing_results.get("annual_savings"))))]),
                html.Tr([html.Td("Annual O&M Cost"), html.Td(html.Strong(fmt_c(financial_metrics.get("initial_om_cost_year1")), className="text-danger"))]),
                # Replacement cost shown in detailed cash flow now
                html.Tr([html.Td("Net Annual Benefit (Savings - O&M)"), html.Td(html.Strong(fmt_c(billing_results.get("annual_savings", 0) - financial_metrics.get("initial_om_cost_year1", 0))))]),
            ], className="table table-sm")),
        ], className="mb-4")

        # Incentives Card
        inc_items = [html.Tr([html.Td(desc), html.Td(fmt_c(amount))]) for desc, amount in incentive_results.get("breakdown", {}).items()]
        inc_items.append(html.Tr([html.Td(html.Strong("Total Incentives")), html.Td(html.Strong(fmt_c(incentive_results.get("total_incentive"))))]))
        incentives_card = dbc.Card([
            dbc.CardHeader("Incentives Applied"),
            dbc.CardBody(html.Table(inc_items, className="table table-sm")),
        ], className="mb-4")

        # Technology comparison table
        tech_comparison = create_technology_comparison_table(current_technology, bess_params.get(KEY_CAPACITY, 0), bess_params.get(KEY_POWER_MAX, 0))

        # Monthly Billing Table
        # ... (monthly table generation remains the same) ...
        months = [calendar.month_abbr[i] for i in range(1, 13)]
        df_monthly = pd.DataFrame({
            "Month": months,
            "Bill Without BESS": [b.get("total_bill", 0) for b in billing_results.get("monthly_bills_without_bess", [])],
            "Bill With BESS": [b.get("total_bill", 0) for b in billing_results.get("monthly_bills_with_bess", [])],
            "Savings": billing_results.get("monthly_savings", []),
            "Peak Demand w/o BESS (kW)": [b.get("peak_demand_kw", 0) for b in billing_results.get("monthly_bills_without_bess", [])],
            "Peak Demand w/ BESS (kW)": [b.get("peak_demand_kw", 0) for b in billing_results.get("monthly_bills_with_bess", [])],
        })
        for col in ["Bill Without BESS", "Bill With BESS", "Savings"]: df_monthly[col] = df_monthly[col].apply(fmt_c)
        for col in ["Peak Demand w/o BESS (kW)", "Peak Demand w/ BESS (kW)"]: df_monthly[col] = df_monthly[col].apply(lambda x: fmt_n(x))
        monthly_table = dash_table.DataTable(
            data=df_monthly.to_dict("records"), columns=[{"name": i, "id": i} for i in df_monthly.columns],
            style_cell={'textAlign': 'right', 'padding': '5px'}, style_header={'fontWeight': 'bold', 'textAlign': 'center'},
            style_data={'border': '1px solid grey'}, style_table={'overflowX': 'auto', 'minWidth': '100%'},
            style_cell_conditional=[{'if': {'column_id': 'Month'}, 'textAlign': 'left'}],
        )

        # Detailed Cash Flow Table
        df_detailed_cf = pd.DataFrame(financial_metrics.get("detailed_cash_flows", []))
        detailed_cf_table = html.Div("Detailed cash flow data not available.")
        if not df_detailed_cf.empty:
            # Format columns
            for col in df_detailed_cf.columns:
                if col != 'Year': df_detailed_cf[col] = df_detailed_cf[col].apply(fmt_c)
            detailed_cf_table = dash_table.DataTable(
                id='detailed-cashflow-table',
                columns=[{"name": i, "id": i} for i in df_detailed_cf.columns],
                data=df_detailed_cf.to_dict('records'),
                page_size=10,
                sort_action="native",
                style_cell={'textAlign': 'right', 'padding': '5px'},
                style_header={'fontWeight': 'bold', 'textAlign': 'center'},
                style_data={'border': '1px solid grey'},
                style_table={'overflowX': 'auto', 'minWidth': '100%'},
                style_cell_conditional=[{'if': {'column_id': 'Year'}, 'textAlign': 'center'}],
            )

        # --- Graphs ---
        # Cash Flow Bar Chart (with replacement cost annotation)
        years_cf = list(range(int(financial_params.get(KEY_LIFESPAN, 30)) + 1))
        cash_flows_data = financial_metrics.get("cash_flows", [])
        if len(cash_flows_data) != len(years_cf): # Ensure length matches
             cash_flows_data = cash_flows_data[:len(years_cf)] + [0] * (len(years_cf) - len(cash_flows_data))

        fig_cashflow = go.Figure(go.Bar(x=years_cf, y=cash_flows_data, name="After-Tax Cash Flow", marker_color=['red' if cf < 0 else 'green' for cf in cash_flows_data]))
        # Add annotations for replacements
        repl_interval = financial_metrics.get("battery_life_years", float('inf'))
        if repl_interval != float('inf'):
            repl_year = repl_interval
            while repl_year <= years:
                year_int = int(np.floor(repl_year)) # Get integer year
                if year_int < len(cash_flows_data):
                     fig_cashflow.add_annotation(x=year_int, y=cash_flows_data[year_int], text="Repl", showarrow=True, arrowhead=4, ax=0, ay=-25, font=dict(color="blue", size=10))
                repl_year += repl_interval

        fig_cashflow.update_layout(title="Project After-Tax Cash Flows (Annual)", xaxis_title="Year", yaxis_title="Cash Flow ($)", yaxis_tickformat="$,.0f", plot_bgcolor="white", margin=dict(l=40, r=20, t=40, b=30))

        # Cumulative Cash Flow Line Chart (with payback annotation)
        cumulative_cash_flows = np.cumsum(cash_flows_data)
        fig_cumulative_cashflow = go.Figure(go.Scatter(x=years_cf, y=cumulative_cash_flows, mode='lines+markers', name='Cumulative Cash Flow', line=dict(color='purple')))
        fig_cumulative_cashflow.add_hline(y=0, line_width=1, line_dash="dash", line_color="black")
        # Add payback annotation
        payback = financial_metrics.get("payback_years", float('inf'))
        if payback != float('inf') and payback <= years:
             fig_cumulative_cashflow.add_vline(x=payback, line_width=1, line_dash="dot", line_color="orange")
             fig_cumulative_cashflow.add_annotation(x=payback, y=0, text=f"Payback: {payback:.1f} yrs", showarrow=True, arrowhead=2, ax=20, ay=-40, font=dict(color="orange"))
        fig_cumulative_cashflow.update_layout(title="Cumulative After-Tax Cash Flow", xaxis_title="Year", yaxis_title="Cumulative Cash Flow ($)", yaxis_tickformat="$,.0f", plot_bgcolor="white", margin=dict(l=40, r=20, t=40, b=30))

        # Single Cycle Power Profile
        # ... (figure generation remains the same) ...
        fig_single_cycle = go.Figure()
        if plot_data_calculated:
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=eaf_power_plot, mode='lines', name='EAF Power Demand', line=dict(color='blue', width=2)))
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=grid_power_plot, mode='lines', name='Grid Power Supply', line=dict(color='green', width=2)))
            fig_single_cycle.add_trace(go.Scatter(x=time_plot, y=bess_power_plot, mode='lines', name='BESS Power Output', line=dict(color='red', width=2), fill='tozeroy'))
            grid_cap_val = eaf_params.get(KEY_GRID_CAP, 35)
            fig_single_cycle.add_shape(type="line", x0=0, y0=grid_cap_val, x1=plot_cycle_duration_min, y1=grid_cap_val, line=dict(color="black", width=2, dash="dash"), name="Grid Cap")
            fig_single_cycle.add_annotation(x=plot_cycle_duration_min * 0.9, y=grid_cap_val + max_y_plot * 0.03, text=f"Grid Cap ({grid_cap_val} MW)", showarrow=False, font=dict(color="black", size=10))
        else: fig_single_cycle.update_layout(xaxis={"visible": False}, yaxis={"visible": False}, annotations=[{"text": "Error generating plot data", "xref": "paper", "yref": "paper", "showarrow": False, "font": {"size": 16}}])
        fig_single_cycle.update_layout(
            title=f'Simulated EAF Cycle Profile ({eaf_params.get(KEY_EAF_SIZE, "N/A")}-ton)',
            xaxis_title=f"Time in Cycle (minutes, Duration: {plot_cycle_duration_min:.1f} min)", yaxis_title="Power (MW)",
            yaxis_range=[0, max_y_plot], showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_white", margin=dict(l=40, r=20, t=50, b=40)
        )

        # --- Assemble Results Output ---
        results_output = html.Div([
            html.H3("Calculation Results", className="mb-4"),
            kpi_cards,
            assumptions_box,
            dbc.Row([
                dbc.Col(savings_card, md=6),
                dbc.Col(incentives_card, md=6),
            ]),
            html.H4("Technology Comparison (at current size)", className="mt-4 mb-3"),
            tech_comparison,
            html.H4("Monthly Billing Breakdown", className="mt-4 mb-3"),
            monthly_table,
            html.H4("Detailed Annual Cash Flow", className="mt-4 mb-3"),
            dbc.Button("Download Cash Flow (CSV)", id="btn-download-cashflow", color="secondary", size="sm", className="mb-2"),
            dcc.Download(id="download-cashflow-csv"), # Add download component
            detailed_cf_table,
            html.H4("Single Cycle Power Profile", className="mt-4 mb-3"),
            dcc.Graph(figure=fig_single_cycle),
            html.H4("Cash Flow Analysis", className="mt-4 mb-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig_cashflow), md=6),
                dbc.Col(dcc.Graph(figure=fig_cumulative_cashflow), md=6),
            ]),
        ])
        error_output = ""
        error_open = False # Clear any previous calculation errors

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"ERROR during calculation display: {e}\n{tb_str}")
        error_output = html.Div([
            html.H5("Calculation Display Error", className="text-danger"),
            html.P("An error occurred while preparing the results display:"),
            html.Pre(f"{type(e).__name__}: {str(e)}"),
            html.Details([html.Summary("Click for technical details (Traceback)"), html.Pre(tb_str)]),
            html.Details([html.Summary("BESS Parameters at time of error:"), html.Pre(pprint.pformat(bess_params))]),
        ])
        error_open = True
        results_output = html.Div("Could not generate results display due to an error.", className="text-center text-danger")
        stored_data = {}

    return results_output, stored_data, error_output, error_open


# --- Optimization Callback ---
# ... (display_optimization_results remains largely the same, but uses updated formatters and includes LCOS) ...
@app.callback(
    [Output(ID_OPTIMIZE_OUTPUT, "children"), Output(STORE_OPTIMIZATION, "data")],
    Input(ID_OPTIMIZE_BTN, "n_clicks"),
    [State(STORE_EAF, "data"), State(STORE_BESS, "data"), State(STORE_UTILITY, "data"),
     State(STORE_FINANCIAL, "data"), State(STORE_INCENTIVE, "data"), State(ID_VALIDATION_ERR, "children")],
    prevent_initial_call=True,
)
def display_optimization_results(n_clicks, eaf_params, bess_base_params, utility_params, financial_params, incentive_params, validation_errors):
    opt_output = html.Div("Click 'Optimize Battery Size' to run the analysis.", className="text-center text-muted")
    opt_stored_data = {}
    if n_clicks == 0: return opt_output, opt_stored_data
    if validation_errors:
        opt_output = dbc.Alert([html.H4("Cannot Optimize - Validation Errors Exist", className="text-danger"), html.P("Please fix the errors listed in the Parameters/Incentives tabs before optimizing.")], color="danger")
        return opt_output, opt_stored_data
    if not all([eaf_params, bess_base_params, utility_params, financial_params, incentive_params]):
        opt_output = dbc.Alert("Cannot Optimize - Missing one or more parameter sets.", color="danger")
        return opt_output, opt_stored_data

    try:
        print("Starting Optimization Callback...")
        opt_results = optimize_battery_size(eaf_params, utility_params, financial_params, incentive_params, bess_base_params)
        opt_stored_data = opt_results
        print("Optimization Function Finished.")

        if opt_results and opt_results.get("best_capacity") is not None:
            best_metrics = opt_results.get("best_metrics", {})
            # Use same formatters as main results
            def fmt_c(v, decimals=0): return f"${v:,.{decimals}f}" if pd.notna(v) and isinstance(v, (int, float)) else "N/A"
            def fmt_p(v): return f"{v:.1%}" if pd.notna(v) and isinstance(v, (int, float)) and abs(v) <= 5 else (f"{'+' if v > 0 else ''}>500%" if pd.notna(v) and abs(v) > 5 else "N/A")
            def fmt_y(v): return "Never" if pd.isna(v) or v == float('inf') else ("< 0 yrs" if v < 0 else f"{v:.1f} yrs")
            def fmt_n(v, decimals=0): return f"{v:,.{decimals}f}" if pd.notna(v) and isinstance(v, (int, float)) else "N/A"

            best_summary = dbc.Card([
                dbc.CardHeader(f"Optimal Size Found (Max NPV) - Tech: {bess_base_params.get(KEY_TECH, 'N/A')}"),
                dbc.CardBody(html.Table([
                    html.Tr([html.Td("Capacity (MWh)"), html.Td(fmt_n(opt_results['best_capacity'], 1))]),
                    html.Tr([html.Td("Power (MW)"), html.Td(fmt_n(opt_results['best_power'], 1))]),
                    html.Tr([html.Td("Resulting NPV"), html.Td(fmt_c(opt_results["best_npv"]))]),
                    html.Tr([html.Td("Resulting IRR"), html.Td(fmt_p(best_metrics.get("irr")))]),
                    html.Tr([html.Td("Resulting Payback"), html.Td(fmt_y(best_metrics.get("payback_years")))]),
                    html.Tr([html.Td("Resulting LCOS ($/MWh)"), html.Td(fmt_c(best_metrics.get("lcos")))]), # Added LCOS
                    html.Tr([html.Td("Annual Savings (Year 1)"), html.Td(fmt_c(best_metrics.get("annual_savings_year1")))]),
                    html.Tr([html.Td("Net Initial Cost"), html.Td(fmt_c(best_metrics.get("net_initial_cost")))]),
                ], className="table table-sm")),
            ], className="mb-4")

            all_results_df = pd.DataFrame(opt_results.get("all_results", []))
            table_section = html.Div("No optimization results data to display in table.")
            if not all_results_df.empty:
                display_cols = {
                    "capacity": "Capacity (MWh)", "power": "Power (MW)", "npv": "NPV ($)", "irr": "IRR (%)",
                    "payback_years": "Payback (Yrs)", "lcos": "LCOS ($/MWh)", # Added LCOS
                    "annual_savings": "Savings ($/Yr)", "net_initial_cost": "Net Cost ($)"
                }
                all_results_df = all_results_df[[k for k in display_cols if k in all_results_df.columns]].copy()
                all_results_df.rename(columns=display_cols, inplace=True)
                for col in ["Capacity (MWh)", "Power (MW)"]: all_results_df[col] = all_results_df[col].map("{:.1f}".format)
                for col in ["NPV ($)", "LCOS ($/MWh)", "Savings ($/Yr)", "Net Cost ($)"]: all_results_df[col] = all_results_df[col].apply(fmt_c)
                all_results_df["IRR (%)"] = all_results_df["IRR (%)"].apply(fmt_p)
                all_results_df["Payback (Yrs)"] = all_results_df["Payback (Yrs)"].apply(fmt_y)
                all_results_table = dash_table.DataTable(
                    data=all_results_df.to_dict("records"), columns=[{"name": i, "id": i} for i in all_results_df.columns],
                    page_size=10, sort_action="native", filter_action="native", style_cell={'textAlign': 'right'},
                    style_header={'fontWeight': 'bold', 'textAlign': 'center'}, style_table={'overflowX': 'auto', 'minWidth': '100%'},
                    style_cell_conditional=[{'if': {'column_id': c}, 'textAlign': 'left'} for c in ["Capacity (MWh)", "Power (MW)"]],
                )
                table_section = html.Div([html.H4("All Tested Combinations", className="mt-4 mb-3"), all_results_table])

            opt_output = html.Div([html.H3("Battery Sizing Optimization Results", className="mb-4"), best_summary, table_section])
        else:
            opt_output = dbc.Alert([html.H4("Optimization Failed or No Viable Solution", className="text-warning"), html.P("Could not find an optimal battery size with the given parameters."), # Simplified message
            ], color="warning")

    except Exception as e:
        tb_str = traceback.format_exc()
        print(f"ERROR during optimization display: {e}\n{tb_str}")
        opt_output = dbc.Alert([html.H5("Optimization Display Error", className="text-danger"), html.P("An error occurred during the optimization display process:"), html.Pre(f"{type(e).__name__}: {str(e)}"), html.Details([html.Summary("Click for technical details"), html.Pre(tb_str)])], color="danger")
        opt_stored_data = {}

    return opt_output, opt_stored_data


# --- Callback for CSV Download ---
@app.callback(
    Output("download-cashflow-csv", "data"),
    Input("btn-download-cashflow", "n_clicks"),
    State(STORE_RESULTS, "data"),
    prevent_initial_call=True,
)
def download_cashflow_csv(n_clicks, stored_results):
    if n_clicks is None or not stored_results or "financials" not in stored_results or "detailed_cash_flows" not in stored_results["financials"]:
        return None

    detailed_cf_data = stored_results["financials"]["detailed_cash_flows"]
    if not detailed_cf_data:
        return None

    df = pd.DataFrame(detailed_cf_data)
    # Make Year the index for cleaner CSV (optional)
    # df.set_index('Year', inplace=True)

    # Create CSV string
    csv_string = df.to_csv(index=False, encoding='utf-8')

    # Prepare download
    return dcc.send_data_frame(df.to_csv, "detailed_cash_flow.csv", index=False)


# --- Run the App ---
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=True) # Keep debug=True for development

# --- END OF FILE ---


#**Summary of Key Changes:**

#1.  **Replacement Cost Fix:** The `calculate_financial_metrics` function now uses `next_replacement_year` tracking instead of the unreliable modulo operator for applying replacement costs. Annotations are added to the cash flow bar chart to indicate replacement years.
#2.  **Initial Cost / O&M Fix:**
#    *   Robust safe conversion blocks for capacity/power are implemented in `calculate_initial_bess_cost`, `calculate_financial_metrics`, and `create_technology_comparison_table` to prevent errors if `None` or invalid values are encountered.
#    *   Added extensive `DEBUG FINANCE` print statements (commented out by default in the final code but useful for tracing) within `calculate_financial_metrics` to verify intermediate values like `capacity_kwh`, `power_kw`, `total_initial_cost`, and `total_initial_om_cost`.
#    *   The O&M cost calculation logic within `calculate_financial_metrics` now more explicitly checks which O&M key (`KEY_OM_KWHR_YR` or `KEY_FIXED_OM`) is present and non-zero in the `bess_params` dictionary to determine the correct calculation method.
#3.  **LCOS Calculation:** Added Levelized Cost of Storage calculation within `calculate_financial_metrics` and display it in the results. This required tracking annual discharge from the billing calculations.
#4.  **Detailed Cash Flow Table:**
#    *   `calculate_financial_metrics` now generates a `detailed_cash_flows` list of dictionaries containing year-by-year components.
#    *   The `display_calculation_results` callback creates a `dash_table.DataTable` from this data.
#    *   Added a "Download Cash Flow (CSV)" button and callback (`download_cashflow_csv`) using `dcc.Download` and `dcc.send_data_frame`.
#5.  **Results Presentation:**
#    *   Added a `kpi_cards` row at the top of the results tab for NPV, IRR, Payback, and LCOS.
#    *   Added an `assumptions_box` summarizing key inputs used for the calculation.
#   *   Refined formatting helpers (`fmt_c`, `fmt_p`, `fmt_y`, `fmt_n`) for clearer display.
#    *   Improved graph titles and added annotations for payback and replacements.
#    *   Slightly reorganized the layout of the results tab for better flow.
#
#This revised code should address the calculation errors and provide a more professional and informative output suitable for financial analysis. Remember to test thoroughly with different inputs and technologies.
