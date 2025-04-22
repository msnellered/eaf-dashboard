import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL, dash_table
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import json
from datetime import datetime
import calendar
import traceback  # For detailed error logging

# Improved numpy_financial fallback
try:
    import numpy_financial as npf
except ImportError:
    print(
        "WARNING: numpy_financial package is required for accurate financial calculations."
        " Please install it with: pip install numpy-financial"
    )

    # Better fallback implementation
    class DummyNPF:
        def npv(self, rate, values):
            print(
                "WARNING: Using simplified NPV calculation. Install numpy-financial for accurate results."
            )
            # Ensure rate is not -1 which causes division by zero
            if rate <= -1:
                return float("nan")
            try:
                return sum(values[i] / ((1 + rate) ** i) for i in range(len(values)))
            except ZeroDivisionError:
                return float("nan")

        def irr(self, values):
            print(
                "WARNING: IRR calculation requires numpy-financial. Install with: pip install numpy-financial"
            )
            # Try a basic iterative approach for IRR if numpy-financial is missing
            if (
                not values or values[0] >= 0
            ):  # IRR can't be calculated if first value is non-negative or list is empty
                return float("nan")

            # Simple bisection method
            r_low, r_high = -0.99, 1.0
            max_iter = 100
            tolerance = 1e-6  # Use a tolerance for convergence

            for _ in range(max_iter):
                r_mid = (r_low + r_high) / 2
                if abs(r_high - r_low) < tolerance:  # Check interval size
                    return r_mid

                # Calculate NPV at mid-point, handle potential division by zero
                try:
                    npv_mid = sum(
                        values[i] / ((1 + r_mid) ** i) for i in range(len(values))
                    )
                except ZeroDivisionError:
                    npv_mid = (
                        float("inf") if values[0] < 0 else float("-inf")
                    )  # Adjust based on initial investment

                if abs(npv_mid) < tolerance:  # Convergence threshold
                    return r_mid

                # Adjust bounds based on NPV sign
                # If npv_mid has the same sign as the initial cash flow (negative),
                # the IRR must be higher.
                if npv_mid < 0:
                    r_low = r_mid
                else:
                    r_high = r_mid

            return float("nan")  # Failed to converge

    npf = DummyNPF()

# Initialize the Dash app (this creates the web server)
app = dash.Dash(
    __name__,
    external_stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css"
    ],
    suppress_callback_exceptions=True,
)
server = app.server

app.title = "Battery Profitability Tool"

# --- Default Parameters ---
# These will be used as fallbacks and for the custom option

# Default utility parameters
default_utility_params = {
    "energy_rates": {"off_peak": 50, "mid_peak": 100, "peak": 150},
    "demand_charge": 10,
    "tou_periods_raw": [ # Raw definition
        (0.0, 8.0, "off_peak"), # Use floats for consistency
        (8.0, 10.0, "peak"),
        (10.0, 16.0, "mid_peak"),
        (16.0, 20.0, "peak"),
        (20.0, 24.0, "off_peak"),
    ],
    # --- Manually define the default filled periods ---
    "tou_periods_filled": [
        (0.0, 8.0, "off_peak"),
        (8.0, 10.0, "peak"),
        (10.0, 16.0, "mid_peak"),
        (16.0, 20.0, "peak"),
        (20.0, 24.0, "off_peak"),
     ],
    # --- End definition ---
    "seasonal_rates": False,
    "winter_months": [11, 12, 1, 2, 3],
    "summer_months": [6, 7, 8, 9],
    "shoulder_months": [4, 5, 10],
    "winter_multiplier": 1.0,
    "summer_multiplier": 1.2,
    "shoulder_multiplier": 1.1,
}

# --- ENSURE NO LINE AFTER THIS DICTIONARY TRIES TO CALL fill_tou_gaps() ---
# Pre-fill the default filled periods
# default_utility_params["tou_periods_filled"] = fill_tou_gaps(
# default_utility_params["tou_periods_raw"]


# Default BESS parameters
default_bess_params = {
    "capacity": 40,  # MWh
    "power_max": 20,  # MW
    "rte": 0.98,  # 98% round-trip efficiency
    "cycle_life": 5000,  # cycles
    "cost_per_kwh": 350,  # $/kWh
    "om_cost_per_kwh_year": 15,  # $/kWh/year
}

# Default financial parameters
# Source for Nucor-specific defaults below: User provided, attributed to 2024 Nucor 10k
default_financial_params = {
    "wacc": 0.131,           # 13.1% Weighted Average Cost of Capital (Updated)
    # "interest_rate": 0.04,   # Removed - Handled within WACC
    # "debt_fraction": 0.5,    # Removed - Handled within WACC
    "project_lifespan": 30,  # 30 years (Updated)
    "tax_rate": 0.2009,      # 20.09% Effective Tax Rate (Updated)
    "inflation_rate": 0.024, # 2.4% Inflation Rate (Updated)
    "salvage_value": 0.1,    # 10% of BESS cost at end (Original default)
}

# New incentive parameters
default_incentive_params = {
    # Federal incentives
    "itc_enabled": False,
    "itc_percentage": 30,  # Investment Tax Credit percentage
    "ceic_enabled": False,
    "ceic_percentage": 30,  # Clean Electricity Investment Credit percentage
    "bonus_credit_enabled": False,
    "bonus_credit_percentage": 10,  # Additional percentage for qualifying projects
    # State incentives
    "sgip_enabled": False,  # California Self-Generation Incentive Program
    "sgip_amount": 400,  # $/kWh
    "ess_enabled": False,  # Connecticut Energy Storage Solutions
    "ess_amount": 280,  # $/kWh
    "mabi_enabled": False,  # NY Market Acceleration Bridge Incentive
    "mabi_amount": 250,  # $/kWh
    "cs_enabled": False,  # Massachusetts Connected Solutions
    "cs_amount": 225,  # $/kWh
    # Custom incentive
    "custom_incentive_enabled": False,
    "custom_incentive_type": "per_kwh",  # "per_kwh" or "percentage"
    "custom_incentive_amount": 100,  # $/kWh or percentage
    "custom_incentive_description": "Custom incentive",
}
# --- Nucor Mill Data ---
nucor_mills = {
    "West Virginia": {
        "location": "Apple Grove, WV",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "DC",
        "eaf_manufacturer": "SMS",
        "eaf_size": 190,
        "cycles_per_day": 26,
        "tons_per_year": 3000000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Appalachian Power",
        "grid_cap": 50,
    },
    "Auburn": {
        "location": "Auburn, NY",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Unknown",
        "eaf_size": 60,
        "cycles_per_day": 28,
        "tons_per_year": 510000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "New York State Electric & Gas",
        "grid_cap": 25,
    },
    "Birmingham": {
        "location": "Birmingham, AL",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Unknown",
        "eaf_size": 52,
        "cycles_per_day": 20,
        "tons_per_year": 310000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Alabama Power",
        "grid_cap": 20,
    },
    "Arkansas": {
        "location": "Blytheville, AR",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "Demag",
        "eaf_size": 150,
        "cycles_per_day": 28,
        "tons_per_year": 2500000,
        "days_per_year": 300,
        "cycle_duration": 38,
        "utility": "Entergy Arkansas",
        "grid_cap": 45,
    },
    "Kankakee": {
        "location": "Bourbonnais, IL",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Danieli",
        "eaf_size": 73,
        "cycles_per_day": 39,
        "tons_per_year": 850000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "ComEd",
        "grid_cap": 30,
    },
    "Brandenburg": {
        "location": "Brandenburg, KY",
        "type": "Sheet",
        "eaf_count": 1,
        "eaf_type": "DC",
        "eaf_manufacturer": "Danieli",
        "eaf_size": 150,
        "cycles_per_day": 27,
        "tons_per_year": 1200000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "LG&E KU",
        "grid_cap": 45,
    },
    "Hertford": {
        "location": "Cofield, NC",
        "type": "Plate",
        "eaf_count": 1,
        "eaf_type": "DC",
        "eaf_manufacturer": "MAN GHH",
        "eaf_size": 150,
        "cycles_per_day": 30,
        "tons_per_year": 1350000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Dominion Energy",
        "grid_cap": 45,
    },
    "Crawfordsville": {
        "location": "Crawfordsville, IN",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "Brown-Boveri",
        "eaf_size": 118,
        "cycles_per_day": 27,
        "tons_per_year": 1890000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Duke Energy",
        "grid_cap": 40,
    },
    "Darlington": {
        "location": "Darlington, SC",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "MAN GHH",
        "eaf_size": 110,
        "cycles_per_day": 30,
        "tons_per_year": 980000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Duke Energy",
        "grid_cap": 40,
    },
    "Decatur": {
        "location": "Decatur, AL",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "DC",
        "eaf_manufacturer": "NKK-SE",
        "eaf_size": 165,
        "cycles_per_day": 20,
        "tons_per_year": 2000000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Alabama Power",
        "grid_cap": 48,
    },
    # --- Start Additions based on PDF Data ---
        "Gallatin": {
            "location": "Ghent, KY", "type": "Sheet", "eaf_count": 2, "eaf_type": "?", # EAF Type not specified clearly
            "eaf_manufacturer": "NKK-SE, Danieli", "eaf_size": 175, "cycles_per_day": 27, "tons_per_year": 2800000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Kentucky Utilities", "grid_cap": 53, # Est: 175 * 0.3
        },
        "Hickman": {
            "location": "Hickman, AR", "type": "Sheet", "eaf_count": 2, "eaf_type": "AC",
            "eaf_manufacturer": "MAN GHH", "eaf_size": 150, "cycles_per_day": 22, "tons_per_year": 2000000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Mississippi County Electric Cooperative", "grid_cap": 45, # Est: 150 * 0.3
        },
        "Berkeley": {
            "location": "Huger, SC", "type": "Sheet/Beam Mill", "eaf_count": 2, "eaf_type": "?",
            "eaf_manufacturer": "MAN GHH", "eaf_size": 154, "cycles_per_day": 26, "tons_per_year": 2430000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Santee Cooper", "grid_cap": 46, # Est: 154 * 0.3
        },
        "Texas": {
            "location": "Jewett, TX", "type": "Bar", "eaf_count": 1, "eaf_type": "AC",
            "eaf_manufacturer": "SMS Concast", "eaf_size": 100, "cycles_per_day": 33, "tons_per_year": 1000000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Oncor Electric Delivery", "grid_cap": 30, # Est: 100 * 0.3
        },
        "Kingman": {
            "location": "Kingman, AZ", "type": "Bar", "eaf_count": 1, "eaf_type": "AC",
            "eaf_manufacturer": "Danieli", "eaf_size": 100, "cycles_per_day": 21, "tons_per_year": 630000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "UniSource Energy Services", "grid_cap": 30, # Est: 100 * 0.3
        },
        # Lexington data missing utility info in PDFs provided
        # "Lexington": {
        #     "location": "Lexington, NC", "type": "Rebar", "eaf_count": 1, "eaf_type": "?",
        #     "eaf_manufacturer": "?", "eaf_size": 50, "cycles_per_day": 29, "tons_per_year": 430000,
        #     "days_per_year": 300, "cycle_duration": 36, "utility": "Duke Energy Carolinas (Assumed in PDF)", "grid_cap": 15, # Est: 50 * 0.3
        # },
        "Marion": {
            "location": "Marion, OH", "type": "Bar Mill/Sign Pos", "eaf_count": 1, "eaf_type": "?",
            "eaf_manufacturer": "?", "eaf_size": 100, "cycles_per_day": 40, "tons_per_year": 1200000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "AEP Ohio", "grid_cap": 30, # Est: 100 * 0.3
        },
        "Nebraska": {
            "location": "Norfolk, NE", "type": "Bar", "eaf_count": 1, "eaf_type": "?",
            "eaf_manufacturer": "MAN GHH", "eaf_size": 95, "cycles_per_day": 35, "tons_per_year": 1000000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Nebraska Public Power District", "grid_cap": 29, # Est: 95 * 0.3
        },
        "Utah": {
            "location": "Plymouth, UT", "type": "Bar", "eaf_count": 2, "eaf_type": "?",
            "eaf_manufacturer": "Fuchs", "eaf_size": 51, "cycles_per_day": 42, "tons_per_year": 1290000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Rocky Mountain Power", "grid_cap": 15, # Est: 51 * 0.3
        },
        "Seattle": {
            "location": "Seattle, WA", "type": "Bar", "eaf_count": 1, "eaf_type": "?",
            "eaf_manufacturer": "Fuchs", "eaf_size": 100, "cycles_per_day": 29, "tons_per_year": 855000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Seattle City Light", "grid_cap": 30, # Est: 100 * 0.3
        },
        "Sedalia": {
            "location": "Sedalia, MO", "type": "Bar", "eaf_count": 1, "eaf_type": "?",
            "eaf_manufacturer": "Danieli", "eaf_size": 40, "cycles_per_day": 39, "tons_per_year": 470000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Evergy", "grid_cap": 12, # Est: 40 * 0.3
        },
        "Tuscaloosa": {
            "location": "Tuscaloosa, AL", "type": "Plate", "eaf_count": 1, "eaf_type": "AC",
            "eaf_manufacturer": "MAN GHH", "eaf_size": 122, "cycles_per_day": 17, "tons_per_year": 610000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Alabama Power", "grid_cap": 37, # Est: 122 * 0.3
        },
        # Connecticut data missing utility confirmation in PDFs
        # "Connecticut": {
        #     "location": "Wallingford, CT", "type": "Wire Rod/Rebar", "eaf_count": 1, "eaf_type": "?",
        #     "eaf_manufacturer": "?", "eaf_size": 30, "cycles_per_day": 27, "tons_per_year": 240000,
        #     "days_per_year": 300, "cycle_duration": 36, "utility": "Eversource Energy (Assumed)", "grid_cap": 9, # Est: 30 * 0.3
        # },
        "Florida": {
            "location": "Frostproof, FL", "type": "?", "eaf_count": 1, "eaf_type": "AC",
            "eaf_manufacturer": "Danieli", "eaf_size": 40, "cycles_per_day": 38, "tons_per_year": 450000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Duke Energy Florida", "grid_cap": 12, # Est: 40 * 0.3
        },
        "Jackson": {
            "location": "Flowood, MS", "type": "Bar", "eaf_count": 1, "eaf_type": "AC",
            "eaf_manufacturer": "?", "eaf_size": 50, "cycles_per_day": 33, "tons_per_year": 490000,
            "days_per_year": 300, "cycle_duration": 36, "utility": "Entergy Mississippi (Assumed)", "grid_cap": 15, # Est: 50 * 0.3
        },
        # Memphis data missing utility confirmation in PDFs
        # "Memphis": {
        #     "location": "Memphis, TN", "type": "Bar", "eaf_count": 1, "eaf_type": "AC",
        #     "eaf_manufacturer": "?", "eaf_size": 94, "cycles_per_day": 28, "tons_per_year": 800000,
        #     "days_per_year": 300, "cycle_duration": 36, "utility": "Memphis Light, Gas and Water (MLGW) (Assumed)", "grid_cap": 28, # Est: 94 * 0.3
        # },
        "Nucor-Yamato": { # Using Nucor-Yamato as key
            "location": "Blytheville, AR", "type": "Structural (implied)", "eaf_count": 2, "eaf_type": "?", # EAF pdf missing details for NYS
            "eaf_manufacturer": "?", "eaf_size": 150, "cycles_per_day": 25, "tons_per_year": 2500000, # Estimate based on capacity
            "days_per_year": 300, "cycle_duration": 36, "utility": "Mississippi County Electric Cooperative", "grid_cap": 45, # Est: 150 * 0.3
        },
        # --- End Additions ---
    "Custom": {
        "location": "Custom Location",
        "type": "Custom",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Custom",
        "eaf_size": 100,
        "cycles_per_day": 24,
        "tons_per_year": 1000000,
        "days_per_year": 300,
        "cycle_duration": 36,
        "utility": "Custom Utility",
        "grid_cap": 35,
    },
}

# --- Utility Rate Data ---
utility_rates = {
    "Appalachian Power": {
        "energy_rates": {"off_peak": 45, "mid_peak": 90, "peak": 135},
        "demand_charge": 12,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 11, "peak"),
            (11, 16, "mid_peak"),
            (16, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [11, 12, 1, 2],
        "summer_months": [6, 7, 8, 9],
        "shoulder_months": [3, 4, 5, 10],
        "winter_multiplier": 1.0,
        "summer_multiplier": 1.3,
        "shoulder_multiplier": 1.1,
    },
    "New York State Electric & Gas": {
        "energy_rates": {"off_peak": 60, "mid_peak": 110, "peak": 180},
        "demand_charge": 15,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 10, "peak"),
            (10, 17, "mid_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [11, 12, 1, 2, 3],
        "summer_months": [6, 7, 8],
        "shoulder_months": [4, 5, 9, 10],
        "winter_multiplier": 1.2,
        "summer_multiplier": 1.5,
        "shoulder_multiplier": 1.3,
    },
    "Alabama Power": {
        "energy_rates": {"off_peak": 40, "mid_peak": 80, "peak": 120},
        "demand_charge": 10,
        "tou_periods": [
            (0, 8, "off_peak"),
            (8, 11, "peak"),
            (11, 15, "mid_peak"),
            (15, 19, "peak"),
            (19, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [12, 1, 2],
        "summer_months": [6, 7, 8, 9],
        "shoulder_months": [3, 4, 5, 10, 11],
        "winter_multiplier": 0.9,
        "summer_multiplier": 1.4,
        "shoulder_multiplier": 1.0,
    },
    "Entergy Arkansas": {
        "energy_rates": {"off_peak": 42, "mid_peak": 85, "peak": 130},
        "demand_charge": 11,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 10, "peak"),
            (10, 16, "mid_peak"),
            (16, 19, "peak"),
            (19, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [11, 12, 1, 2],
        "summer_months": [6, 7, 8, 9],
        "shoulder_months": [3, 4, 5, 10],
        "winter_multiplier": 0.9,
        "summer_multiplier": 1.3,
        "shoulder_multiplier": 1.0,
    },
    "ComEd": {
        "energy_rates": {"off_peak": 48, "mid_peak": 95, "peak": 140},
        "demand_charge": 13,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 10, "peak"),
            (10, 17, "mid_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [11, 12, 1, 2, 3],
        "summer_months": [6, 7, 8],
        "shoulder_months": [4, 5, 9, 10],
        "winter_multiplier": 1.1,
        "summer_multiplier": 1.6,
        "shoulder_multiplier": 1.2,
    },
    "LG&E KU": {
        "energy_rates": {"off_peak": 44, "mid_peak": 88, "peak": 125},
        "demand_charge": 12.5,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 11, "peak"),
            (11, 17, "mid_peak"),
            (17, 21, "peak"),
            (21, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [11, 12, 1, 2],
        "summer_months": [6, 7, 8, 9],
        "shoulder_months": [3, 4, 5, 10],
        "winter_multiplier": 1.0,
        "summer_multiplier": 1.35,
        "shoulder_multiplier": 1.1,
    },
    "Dominion Energy": {
        "energy_rates": {"off_peak": 47, "mid_peak": 94, "peak": 138},
        "demand_charge": 13.5,
        "tou_periods": [
            (0, 6, "off_peak"),
            (6, 11, "peak"),
            (11, 16, "mid_peak"),
            (16, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [12, 1, 2, 3],
        "summer_months": [6, 7, 8, 9],
        "shoulder_months": [4, 5, 10, 11],
        "winter_multiplier": 1.05,
        "summer_multiplier": 1.45,
        "shoulder_multiplier": 1.15,
    },
    "Duke Energy": {
        "energy_rates": {"off_peak": 46, "mid_peak": 92, "peak": 135},
        "demand_charge": 14,
        "tou_periods": [
            (0, 7, "off_peak"),
            (7, 10, "peak"),
            (10, 16, "mid_peak"),
            (16, 20, "peak"),
            (20, 24, "off_peak"),
        ],
        "seasonal_rates": True,
        "winter_months": [11, 12, 1, 2],
        "summer_months": [6, 7, 8, 9],
        "shoulder_months": [3, 4, 5, 10],
        "winter_multiplier": 0.95,
        "summer_multiplier": 1.4,
        "shoulder_multiplier": 1.1,
    },
    # --- Start Additions based on PDF Data ---
        "Kentucky Utilities": { # For Gallatin
             # Rate details unavailable/inaccessible in provided PDFs [cite: 78507, 78522]
             # Using Custom Utility defaults as placeholder
             # Inherit defaults
        },
        "Mississippi County Electric Cooperative": { # For Hickman, Nucor-Yamato
            "energy_rates": {"off_peak": 32.72, "mid_peak": 32.72, "peak": 32.72}, # Flat rate ($/MWh) [cite: 78532]
            "demand_charge": 12.28, # Sum of Monthly ($1.55) and Coincident ($10.73) [cite: 78534, 78535] - SIMPLIFICATION
            "tou_periods": [(0, 24, "off_peak")], # No TOU mentioned for Rate #11 [cite: 78537]
            "seasonal_rates": False, # No seasonal variation mentioned for base rates
             # Using default multipliers as placeholder if needed
            "winter_months": default_utility_params["winter_months"],
            "summer_months": default_utility_params["summer_months"],
            "shoulder_months": default_utility_params["shoulder_months"],
            "winter_multiplier": 1.0, "summer_multiplier": 1.0, "shoulder_multiplier": 1.0,
        },
        "Santee Cooper": { # For Berkeley
            "energy_rates": {"off_peak": 37.50, "mid_peak": 37.50, "peak": 57.50}, # Base rates ($/MWh) [cite: 78442, 78443]
            "demand_charge": 19.26, # Base demand >300kW [cite: 78447]
            # Simplified TOU based on energy peak times only
            "tou_periods": [(0, 13, "off_peak"), (13, 22, "peak"), (22, 24, "off_peak")], # Jun-Aug, M-F peak 1p-10p [cite: 78455]
            "seasonal_rates": True, # Energy peak is seasonal
            "winter_months": [1, 2, 3, 4, 5, 9, 10, 11, 12], # All months except Jun, Jul, Aug
            "summer_months": [6, 7, 8], # Peak energy rate applies
            "shoulder_months": [], # N/A
            "winter_multiplier": 1.0, # Base rates apply
            "summer_multiplier": 1.0, # Base peak rate used directly
            "shoulder_multiplier": 1.0,
        },
        "Oncor Electric Delivery": { # For Texas (Jewett) - TDU ONLY
            # Represents Delivery charges only. Energy cost depends on separate REP contract. [cite: 78604, 78627]
            # Using Custom Utility defaults as placeholder for combined rate structure.
            
        },
        "UniSource Energy Services": { # For Kingman
            # Rates from E-38 LGP [cite: 79202]
            # Averaging seasonal peak/offpeak for simplicity (Peak ~77.5, Offpeak ~52.5)
            "energy_rates": {"off_peak": 52.5, "mid_peak": 52.5, "peak": 77.5}, # Approx avg ($/MWh) [cite: 79213, 79214, 79215, 79216]
            "demand_charge": 16.5, # Approx avg of Summer ($19) / Winter ($14) [cite: 79208]
            # Based on Energy TOU
            "tou_periods": [(0, 6, "off_peak"), (6, 10, "peak"), (10, 17, "off_peak"), (17, 21, "peak"), (21, 24, "off_peak")], # Winter Peak 6a-10a, 5p-9p [cite: 79215] -> Rough fit
            "seasonal_rates": True, # Both energy and demand vary seasonally
             "winter_months": [11, 12, 1, 2, 3, 4], # Nov-Apr [cite: 79208]
            "summer_months": [5, 6, 7, 8, 9, 10], # May-Oct [cite: 79208]
            "shoulder_months": [],
            "winter_multiplier": 0.85, # Approx ratio of Winter/Summer Demand charge (14/16.5)
            "summer_multiplier": 1.15, # Approx ratio of Summer/Summer Demand charge (19/16.5)
            "shoulder_multiplier": 1.0,
        },
        # Duke Energy Carolinas assumed for Lexington - Rate data unavailable/inaccessible
        # "Duke Energy Carolinas": {
        #      **utility_rates["Custom Utility"] # Placeholder
        # },
        "AEP Ohio": { # For Marion - Distribution ONLY
            # Represents Delivery charges only. Energy cost depends on separate CRES/SSO rates. [cite: 79111, 79274]
            # Using Custom Utility defaults as placeholder for combined rate structure.
            
        },
        "Nebraska Public Power District": { # For Nebraska (Norfolk)
            # Rates from LIS [cite: 78556]
            # Averaging seasonal peak/offpeak for simplicity (Peak ~34.4, Offpeak ~19.3)
            "energy_rates": {"off_peak": 19.3, "mid_peak": 19.3, "peak": 34.4}, # ($/MWh) [cite: 78558]
            # Summing demand components (Prod + Trans Line + Trans Sub + Ancillary) - Highly simplified
            "demand_charge": 19.0, # Approx Avg ((14.46+11.71)/2 + 3.88 + 0.52 + 0.16) [cite: 78560, 78561, 78562, 78563]
            # TOU defined for energy, using generic split
            "tou_periods": default_utility_params["tou_periods_filled"],
            "seasonal_rates": True, # Both energy and demand vary seasonally
            "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], # Oct-May [cite: 78558]
            "summer_months": [6, 7, 8, 9], # Jun-Sep [cite: 78558]
            "shoulder_months": [],
             # Ratio based on Production Demand
            "winter_multiplier": 0.9,  # Approx (11.71+3.88+0.52+0.16) / 19.0
            "summer_multiplier": 1.1, # Approx (14.46+3.88+0.52+0.16) / 19.0
            "shoulder_multiplier": 1.0,
        },
        "Rocky Mountain Power": { # For Utah (Plymouth)
            # Rates from Schedule 9 [cite: 78583]
            # Averaging seasonal peak/offpeak (Peak ~48.5, Offpeak ~24.7)
            "energy_rates": {"off_peak": 24.7, "mid_peak": 24.7, "peak": 48.5}, # ($/MWh) [cite: 78584, 78585]
            # Summing demand components (Power Charge + Facilities Charge)
            "demand_charge": 15.79, # Approx Avg ((14.33+12.68)/2 + 2.28) [cite: 78586, 78576]
            # Using Schedule 9 TOU
            "tou_periods": [(0, 6, "off_peak"), (6, 9, "peak"), (9, 15, "off_peak"), (15, 22, "peak"), (22, 24, "off_peak")], # Winter peak 6a-9a & 6p-10p; Summer peak 3p-10p - simplified fit [cite: 78588, 78589]
            "seasonal_rates": True, # Both energy and demand vary seasonally
            "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], # Oct-May [cite: 78584]
            "summer_months": [6, 7, 8, 9], # Jun-Sep [cite: 78584]
            "shoulder_months": [],
            # Ratio based on Power Charge
            "winter_multiplier": 0.95, # Approx (12.68+2.28)/15.79
            "summer_multiplier": 1.05, # Approx (14.33+2.28)/15.79
            "shoulder_multiplier": 1.0,
        },
        "Seattle City Light": { # For Seattle
            # Rates from High Demand 'C' [cite: 78902]
            "energy_rates": {"off_peak": 55.30, "mid_peak": 55.30, "peak": 110.70}, # ($/MWh) [cite: 78904]
            # Using Peak Demand charge primarily (offpeak demand charge is very low)
            "demand_charge": 5.13, # Peak kW charge [cite: 78905]
            # TOU: Peak 6am-10pm M-Sat
            "tou_periods": [(0, 6, "off_peak"), (6, 22, "peak"), (22, 24, "off_peak")], # Simplified M-F fit
            "seasonal_rates": False, # No seasonal variation mentioned for base rates
            "winter_months": default_utility_params["winter_months"],
            "summer_months": default_utility_params["summer_months"],
            "shoulder_months": default_utility_params["shoulder_months"],
            "winter_multiplier": 1.0, "summer_multiplier": 1.0, "shoulder_multiplier": 1.0,
        },
        "Evergy": { # For Sedalia
            # Rates from LPS Transmission [cite: 78728]
            # Using highest tier energy rate for peak, lowest for off-peak (simplification)
            "energy_rates": {"off_peak": 32.59, "mid_peak": 37.19, "peak": 53.91}, # Summer peak, Winter off-peak ($/MWh) [cite: 78730, 78731]
            "demand_charge": 9.69, # Avg of Summer ($12.746) / Winter ($6.637) [cite: 78733]
            "tou_periods": [(0, 24, "off_peak")], # Standard LPS is seasonal, not daily TOU [cite: 78735]
            "seasonal_rates": True, # Both energy tiers and demand vary seasonally
            "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], # Oct-May [cite: 78731]
            "summer_months": [6, 7, 8, 9], # Jun-Sep [cite: 78730]
            "shoulder_months": [],
            "winter_multiplier": 0.69, # Ratio Winter/Avg Demand (6.637/9.69)
            "summer_multiplier": 1.31, # Ratio Summer/Avg Demand (12.746/9.69)
            "shoulder_multiplier": 1.0,
        },
        # Alabama Power already exists (for Birmingham), Tuscaloosa uses the same
        # Eversource Energy assumed for Connecticut - Rate data unavailable/inaccessible
        # "Eversource Energy": {
        #      **utility_rates["Custom Utility"] # Placeholder
        # },
        "Duke Energy Florida": { # For Florida (Frostproof)
             # Rate details unavailable/inaccessible in provided PDFs [cite: 78799, 78801]
             # Placeholder
        },
        "Entergy Mississippi (Assumed)": { # For Jackson
            # Rates from LGS-TOU [cite: 79177]
             "energy_rates": {"off_peak": 41.0, "mid_peak": 41.0, "peak": 67.0}, # ($/MWh) [cite: 79287]
             "demand_charge": 16.75, # Approx Avg Peak ((19.50+14.00)/2) [cite: 79282, 79283]
             "tou_periods": [(0, 6, "off_peak"), (6, 10, "peak"), (10, 12, "off_peak"), (12, 20, "peak"), (20, 24, "off_peak")], # Winter peak 6a-10a, 6p-10p; Summer peak 12p-8p [cite: 79284, 79285] -> Simplified fit
             "seasonal_rates": True, # Demand varies seasonally
             "winter_months": [10, 11, 12, 1, 2, 3, 4, 5], # Oct-May [cite: 79285]
             "summer_months": [6, 7, 8, 9], # Jun-Sep [cite: 79284]
             "shoulder_months": [],
             "winter_multiplier": 0.84, # Ratio Winter Peak/Avg Peak (14.00/16.75)
             "summer_multiplier": 1.16, # Ratio Summer Peak/Avg Peak (19.50/16.75)
             "shoulder_multiplier": 1.0,
        },
        # Memphis Light, Gas and Water (MLGW) (Assumed) - Rate data unavailable/inaccessible
        # "Memphis Light, Gas and Water (MLGW) (Assumed)": {
        #     **utility_rates["Custom Utility"] # Placeholder
        # },
        # Meade County RECC rate data from 2014 [cite: 78890], using Brandenburg's current LG&E KU assignment instead.

        # --- End Additions ---
    "Custom Utility": default_utility_params,  # Reference the default dict
}
# --- Add these lines AFTER the utility_rates dictionary is fully defined ---
placeholder_utilities = [
    "Kentucky Utilities",
    "Oncor Electric Delivery",
    "AEP Ohio",
    "Duke Energy Florida",
    # Add any other keys you left as placeholders above, e.g.:
    # "Duke Energy Carolinas",
    # "Eversource Energy",
    # "Memphis Light, Gas and Water (MLGW) (Assumed)",
]

for util_key in placeholder_utilities:
    if util_key in utility_rates: # Check if key exists
        # Use .update() to merge defaults without overwriting if needed later
        # Or simply assign if you want a direct copy:
        utility_rates[util_key] = utility_rates["Custom Utility"].copy()

# --- End of added update code ---
# --- Helper Functions ---


def fill_tou_gaps(periods):
    """Fill gaps in TOU periods with off-peak rates"""
    if not periods:
        return [(0.0, 24.0, "off_peak")]

    clean_periods = []
    for period in periods:
        try:
            # Ensure period has 3 elements and convert types
            if len(period) == 3:
                start = float(period[0])
                end = float(period[1])
                rate = str(period[2])
                # Basic validation
                if 0 <= start < end <= 24:
                    clean_periods.append((start, end, rate))
                else:
                    print(f"Warning: Skipping invalid TOU period data: {period}")
            else:
                print(f"Warning: Skipping malformed TOU period data: {period}")
        except (TypeError, ValueError, IndexError):
            print(f"Warning: Skipping invalid TOU period data: {period}")
            continue  # Skip invalid periods gracefully

    # Sort by start time
    clean_periods.sort(key=lambda x: x[0])

    # Check for overlaps after cleaning and sorting
    for i in range(len(clean_periods) - 1):
        if clean_periods[i][1] > clean_periods[i + 1][0]:
            print(
                f"Warning: Overlapping TOU periods detected between {clean_periods[i]} and {clean_periods[i+1]}. Using the first encountered."
            )
            # Simple resolution: truncate the first period or remove the second
            # For simplicity, let's just warn and proceed. A better UI validation should prevent this.
            pass  # Or implement overlap resolution logic

    filled_periods = []
    current_time = 0.0

    for start, end, rate in clean_periods:
        if start > current_time:
            filled_periods.append((current_time, start, "off_peak"))
        filled_periods.append((start, end, rate))
        current_time = end

    if current_time < 24.0:
        filled_periods.append((current_time, 24.0, "off_peak"))

    # Handle the case where clean_periods was empty
    if not filled_periods:
        filled_periods.append((0.0, 24.0, "off_peak"))

    return filled_periods


def get_month_season_multiplier(month, seasonal_data):
    """Determine the rate multiplier based on the month and seasonal configuration"""
    if not seasonal_data.get("seasonal_rates", False):  # Use .get for safety
        return 1.0

    # Use .get with default empty lists for safety
    if month in seasonal_data.get("winter_months", []):
        return seasonal_data.get("winter_multiplier", 1.0)
    elif month in seasonal_data.get("summer_months", []):
        return seasonal_data.get("summer_multiplier", 1.0)
    elif month in seasonal_data.get("shoulder_months", []):
        return seasonal_data.get("shoulder_multiplier", 1.0)
    else:
        # If month doesn't fit defined seasons, maybe default to shoulder or 1.0?
        print(
            f"Warning: Month {month} not found in any defined season. Using multiplier 1.0."
        )
        return 1.0


# Improved EAF profile calculation to respect cycle duration
def calculate_eaf_profile(time_minutes, eaf_size=100, cycle_duration=36):
    """Calculate EAF power profile for a given time array (in minutes) and EAF size in tons"""
    if cycle_duration <= 0:  # Avoid division by zero
        return np.zeros_like(time_minutes)

    eaf_power = np.zeros_like(time_minutes)
    # Scale factor based on EAF size (assuming power scales roughly with EAF size^0.6)
    scale = (eaf_size / 100) ** 0.6 if eaf_size > 0 else 0

    # Reference cycle duration for timing fractions (e.g., original 28 min)
    ref_duration = 28.0
    # Define key points in the cycle as fractions of the REFERENCE cycle duration
    bore_in_end_frac = 3 / ref_duration
    main_melting_end_frac = 17 / ref_duration
    melting_end_frac = 20 / ref_duration
    # remaining time is refining

    for i, t_actual in enumerate(time_minutes):
        # Normalize the actual time based on the *actual* cycle duration
        t_norm_actual_cycle = t_actual / cycle_duration if cycle_duration > 0 else 0

        # Determine phase based on normalized time within the actual cycle
        if t_norm_actual_cycle <= bore_in_end_frac:  # Bore-in
            # Interpolate power based on progress within this phase
            phase_progress = (
                t_norm_actual_cycle / bore_in_end_frac if bore_in_end_frac > 0 else 0
            )
            eaf_power[i] = (15 + (25 - 15) * phase_progress) * scale
        elif t_norm_actual_cycle <= main_melting_end_frac:  # Main melting
            # Adjust frequency of sine wave based on actual cycle duration relative to reference
            freq_scale = ref_duration / cycle_duration if cycle_duration > 0 else 1
            eaf_power[i] = (55 + 5 * np.sin(t_actual * 0.5 * freq_scale)) * scale
        elif t_norm_actual_cycle <= melting_end_frac:  # End of melting
            # Interpolate power based on progress within this phase
            phase_progress = (
                (
                    (t_norm_actual_cycle - main_melting_end_frac)
                    / (melting_end_frac - main_melting_end_frac)
                )
                if (melting_end_frac > main_melting_end_frac)
                else 0
            )
            eaf_power[i] = (50 - (50 - 40) * phase_progress) * scale
        else:  # Refining
            # Adjust frequency of sine wave
            freq_scale = ref_duration / cycle_duration if cycle_duration > 0 else 1
            eaf_power[i] = (20 + 5 * np.sin(t_actual * 0.3 * freq_scale)) * scale

    return eaf_power


def calculate_grid_bess_power(eaf_power, grid_cap, bess_power_max):
    """Calculate grid and BESS power based on EAF power and constraints"""
    grid_power = np.zeros_like(eaf_power)
    bess_power = np.zeros_like(eaf_power)  # Positive for discharge

    # Ensure non-negative inputs
    grid_cap = max(0, grid_cap)
    bess_power_max = max(0, bess_power_max)

    for i, p_eaf in enumerate(eaf_power):
        p_eaf = max(0, p_eaf)  # Ensure EAF power is not negative
        if p_eaf > grid_cap:
            # BESS discharges to cover the difference, up to its max power
            discharge_needed = p_eaf - grid_cap
            actual_discharge = min(discharge_needed, bess_power_max)
            bess_power[i] = actual_discharge  # BESS power is positive discharge
            grid_power[i] = p_eaf - actual_discharge  # Grid covers the rest
        else:
            # Grid supplies all power, BESS is idle
            # (Charging is not modeled here, assume charged from grid during off-peak implicitly)
            grid_power[i] = p_eaf
            bess_power[i] = 0  # No discharge needed

    return grid_power, bess_power


def create_monthly_bill_with_bess(
    eaf_params, bess_params, utility_params, days_in_month, month_number
):
    """Calculate monthly electricity bill with BESS for a specific month"""
    # Get seasonal multiplier
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)

    # Adjust rates for the season
    energy_rates = {
        rate_type: rate * seasonal_mult
        for rate_type, rate in utility_params.get("energy_rates", {}).items()
    }
    demand_charge = utility_params.get("demand_charge", 0) * seasonal_mult

    # Use the pre-filled TOU periods from the utility_params
    filled_tou_periods = utility_params.get(
        "tou_periods_filled", [(0.0, 24.0, "off_peak")]
    )

    # EAF profile calculation
    eaf_size = eaf_params.get("eaf_size", 100)
    # Use the specific input field ID for cycle duration if available
    cycle_duration_min = eaf_params.get(
        "cycle_duration_input", eaf_params.get("cycle_duration", 36)
    )

    if cycle_duration_min <= 0:  # Basic validation
        print("Warning: Cycle duration must be positive. Using default 36 min.")
        cycle_duration_min = 36

    time_step_min = cycle_duration_min / 200  # Simulation time step
    time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min)

    # Calculate grid and BESS power
    grid_cap = eaf_params.get("grid_cap", 50)
    bess_power_max = bess_params.get("power_max", 20)
    grid_power_cycle, bess_power_cycle = calculate_grid_bess_power(
        eaf_power_cycle, grid_cap, bess_power_max
    )

    # Peak demand calculation from the GRID perspective
    peak_demand_kw = (
        np.max(grid_power_cycle) * 1000 if len(grid_power_cycle) > 0 else 0
    )  # Convert MW to kW

    # Energy calculations per cycle
    # Note: BESS energy calculation here only tracks discharge during peak shaving.
    # It doesn't account for charging energy or RTE losses explicitly in the billing cost,
    # assuming charging happens off-peak and RTE impacts overall system cost/viability.
    bess_energy_cycle_discharged = np.sum(bess_power_cycle) * (
        time_step_min / 60
    )  # MWh discharged per cycle
    grid_energy_cycle = np.sum(grid_power_cycle) * (
        time_step_min / 60
    )  # MWh from grid per cycle

    # Calculate energy charge by time-of-use period
    # Assume cycles are evenly distributed throughout the day for simplicity
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}
    total_energy_cost = 0
    total_grid_energy_month = 0
    cycles_per_day = eaf_params.get("cycles_per_day", 24)

    for start, end, period in filled_tou_periods:
        if period in energy_rates:
            period_hours = end - start
            period_fraction = period_hours / 24.0
            # Cycles occurring *during* this period type across the month
            cycles_in_period_month = cycles_per_day * period_fraction * days_in_month
            # Grid energy consumed during these cycles
            energy_in_period_month = grid_energy_cycle * cycles_in_period_month
            period_cost = energy_in_period_month * energy_rates[period]

            tou_energy_costs[
                period
            ] += period_cost  # Accumulate cost for this rate type
            total_energy_cost += period_cost
            total_grid_energy_month += energy_in_period_month
        else:
            print(
                f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict."
            )

    # Calculate demand charge
    demand_cost = peak_demand_kw * demand_charge

    # Total monthly bill
    total_bill = total_energy_cost + demand_cost

    return {
        "energy_cost": total_energy_cost,
        "demand_cost": demand_cost,
        "total_bill": total_bill,
        "peak_demand_kw": peak_demand_kw,
        "energy_consumed_mwh": total_grid_energy_month,  # Total grid energy for the month
        "tou_breakdown": tou_energy_costs,
        "bess_discharged_per_cycle_mwh": bess_energy_cycle_discharged,  # Info metric
    }


def create_monthly_bill_without_bess(
    eaf_params, utility_params, days_in_month, month_number
):
    """Calculate monthly electricity bill without BESS for a specific month"""
    # Get seasonal multiplier
    seasonal_mult = get_month_season_multiplier(month_number, utility_params)

    # Adjust rates for the season
    energy_rates = {
        rate_type: rate * seasonal_mult
        for rate_type, rate in utility_params.get("energy_rates", {}).items()
    }
    demand_charge = utility_params.get("demand_charge", 0) * seasonal_mult

    # Use the pre-filled TOU periods
    filled_tou_periods = utility_params.get(
        "tou_periods_filled", [(0.0, 24.0, "off_peak")]
    )

    # EAF profile calculation
    eaf_size = eaf_params.get("eaf_size", 100)
    # Use the specific input field ID for cycle duration if available
    cycle_duration_min = eaf_params.get(
        "cycle_duration_input", eaf_params.get("cycle_duration", 36)
    )

    if cycle_duration_min <= 0:
        print("Warning: Cycle duration must be positive. Using default 36 min.")
        cycle_duration_min = 36

    time_step_min = cycle_duration_min / 200
    time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(time, eaf_size, cycle_duration_min)

    # Without BESS, grid power equals EAF power
    grid_power_cycle = eaf_power_cycle

    # Peak demand calculation (directly from EAF power)
    peak_demand_kw = np.max(grid_power_cycle) * 1000 if len(grid_power_cycle) > 0 else 0

    # Energy calculations per cycle
    grid_energy_cycle = np.sum(grid_power_cycle) * (
        time_step_min / 60
    )  # MWh from grid per cycle

    # Calculate energy charge by time-of-use period
    tou_energy_costs = {rate_type: 0.0 for rate_type in energy_rates.keys()}
    total_energy_cost = 0
    total_grid_energy_month = 0
    cycles_per_day = eaf_params.get("cycles_per_day", 24)

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
        else:
            print(
                f"Warning: Rate type '{period}' found in TOU schedule but not in energy_rates dict."
            )

    # Calculate demand charge
    demand_cost = peak_demand_kw * demand_charge

    # Total monthly bill
    total_bill = total_energy_cost + demand_cost

    return {
        "energy_cost": total_energy_cost,
        "demand_cost": demand_cost,
        "total_bill": total_bill,
        "peak_demand_kw": peak_demand_kw,
        "energy_consumed_mwh": total_grid_energy_month,
        "tou_breakdown": tou_energy_costs,
    }


# *** Corrected calculate_annual_billings function (removed duplicate) ***
def calculate_annual_billings(eaf_params, bess_params, utility_params):
    """Calculate monthly and annual bills with and without BESS"""
    monthly_bills_with_bess = []
    monthly_bills_without_bess = []
    monthly_savings = []
    # Use a non-leap year like 2025 for consistency unless specified
    year = 2025

    # Ensure utility_params contains filled TOU periods
    if (
        "tou_periods_filled" not in utility_params
        or not utility_params["tou_periods_filled"]
    ):
        raw_periods = utility_params.get(
            "tou_periods_raw", default_utility_params["tou_periods_raw"]
        )
        utility_params["tou_periods_filled"] = fill_tou_gaps(raw_periods)
        print("Warning: Filled TOU periods were missing, generated them.")

    for month in range(1, 13):
        days_in_month = calendar.monthrange(year, month)[1]

        # Calculate bills for this month
        bill_with_bess = create_monthly_bill_with_bess(
            eaf_params, bess_params, utility_params, days_in_month, month
        )

        bill_without_bess = create_monthly_bill_without_bess(
            eaf_params, utility_params, days_in_month, month
        )

        # Calculate savings
        savings = bill_without_bess["total_bill"] - bill_with_bess["total_bill"]

        monthly_bills_with_bess.append(bill_with_bess)
        monthly_bills_without_bess.append(bill_without_bess)
        monthly_savings.append(savings)  # Ensure this line exists

    # Calculate annual totals
    annual_bill_with_bess = sum(bill["total_bill"] for bill in monthly_bills_with_bess)
    annual_bill_without_bess = sum(
        bill["total_bill"] for bill in monthly_bills_without_bess
    )
    annual_savings = sum(monthly_savings)

    return {
        "monthly_bills_with_bess": monthly_bills_with_bess,
        "monthly_bills_without_bess": monthly_bills_without_bess,
        "monthly_savings": monthly_savings,
        "annual_bill_with_bess": annual_bill_with_bess,
        "annual_bill_without_bess": annual_bill_without_bess,
        "annual_savings": annual_savings,
    }


# Improved incentive calculation function
def calculate_incentives(bess_params, incentive_params):
    """Calculate total incentives based on selected programs, ensuring proper handling of mutually exclusive incentives"""
    total_incentive = 0
    incentive_breakdown = {}

    capacity_kwh = bess_params.get("capacity", 0) * 1000  # Convert MWh to kWh
    cost_per_kwh = bess_params.get("cost_per_kwh", 0)
    total_cost = capacity_kwh * cost_per_kwh

    # --- Helper to safely get incentive values ---
    def get_incentive_param(key, default):
        return incentive_params.get(key, default)

    # --- Calculate individual incentives ---
    itc_enabled = get_incentive_param("itc_enabled", False)
    itc_perc = get_incentive_param("itc_percentage", 30) / 100.0
    itc_amount = total_cost * itc_perc if itc_enabled else 0

    ceic_enabled = get_incentive_param("ceic_enabled", False)
    ceic_perc = get_incentive_param("ceic_percentage", 30) / 100.0
    ceic_amount = total_cost * ceic_perc if ceic_enabled else 0

    bonus_enabled = get_incentive_param("bonus_credit_enabled", False)
    bonus_perc = get_incentive_param("bonus_credit_percentage", 10) / 100.0
    bonus_amount = total_cost * bonus_perc if bonus_enabled else 0

    sgip_enabled = get_incentive_param("sgip_enabled", False)
    sgip_rate = get_incentive_param("sgip_amount", 400)
    sgip_amount = capacity_kwh * sgip_rate if sgip_enabled else 0

    ess_enabled = get_incentive_param("ess_enabled", False)
    ess_rate = get_incentive_param("ess_amount", 280)
    ess_amount = capacity_kwh * ess_rate if ess_enabled else 0

    mabi_enabled = get_incentive_param("mabi_enabled", False)
    mabi_rate = get_incentive_param("mabi_amount", 250)
    mabi_amount = capacity_kwh * mabi_rate if mabi_enabled else 0

    cs_enabled = get_incentive_param("cs_enabled", False)
    cs_rate = get_incentive_param("cs_amount", 225)
    cs_amount = capacity_kwh * cs_rate if cs_enabled else 0

    custom_enabled = get_incentive_param("custom_incentive_enabled", False)
    custom_type = get_incentive_param("custom_incentive_type", "per_kwh")
    custom_rate = get_incentive_param("custom_incentive_amount", 100)
    custom_desc = get_incentive_param("custom_incentive_description", "Custom")
    custom_amount = 0
    if custom_enabled:
        if custom_type == "per_kwh":
            custom_amount = capacity_kwh * custom_rate
        elif custom_type == "percentage":
            custom_amount = total_cost * (custom_rate / 100.0)

    # --- Apply Logic (Mutual Exclusivity, Stacking) ---
    applied_federal_base = 0
    federal_base_desc = ""

    # ITC vs CEIC (mutually exclusive)
    if itc_enabled and ceic_enabled:
        if itc_amount >= ceic_amount:  # Choose the larger one
            applied_federal_base = itc_amount
            federal_base_desc = "Investment Tax Credit (ITC)"
        else:
            applied_federal_base = ceic_amount
            federal_base_desc = "Clean Electricity Investment Credit (CEIC)"
    elif itc_enabled:
        applied_federal_base = itc_amount
        federal_base_desc = "Investment Tax Credit (ITC)"
    elif ceic_enabled:
        applied_federal_base = ceic_amount
        federal_base_desc = "Clean Electricity Investment Credit (CEIC)"

    if applied_federal_base > 0:
        total_incentive += applied_federal_base
        incentive_breakdown[federal_base_desc] = applied_federal_base

    # Bonus credits stack on top
    if bonus_amount > 0:
        total_incentive += bonus_amount
        incentive_breakdown["Bonus Credits"] = bonus_amount

    # State and custom incentives (assume they stack, verify specific rules)
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

    return {"total_incentive": total_incentive, "breakdown": incentive_breakdown}


# Improved financial metrics calculation (Corrected Version Apr 21, 2025)
def calculate_financial_metrics(
    bess_params, financial_params, eaf_params, annual_savings, incentives
):
    """Calculate NPV, IRR, payback period, etc. with incentives included,
       using WACC for discounting and handling recurring replacements."""

    # --- Get Parameters ---
    # BESS Parameters
    capacity_kwh = bess_params.get("capacity", 0) * 1000
    cost_per_kwh = bess_params.get("cost_per_kwh", 0)
    om_cost_per_kwh_year = bess_params.get("om_cost_per_kwh_year", 0)
    cycle_life = bess_params.get("cycle_life", 5000)

    # Financial Parameters (using .get for safety)
    years = int(financial_params.get("project_lifespan", 30)) # Ensure integer
    wacc = financial_params.get("wacc", 0.131)
    inflation_rate = financial_params.get("inflation_rate", 0.024)
    tax_rate = financial_params.get("tax_rate", 0.2009)
    salvage_fraction = financial_params.get("salvage_value", 0.1)
    # Note: interest_rate and debt_fraction are no longer used

    # EAF Parameters for battery life calculation
    days_per_year = eaf_params.get("days_per_year", 300)
    cycles_per_day = eaf_params.get("cycles_per_day", 24)

    # --- Initial Calculations ---
    bess_cost = capacity_kwh * cost_per_kwh # Initial BESS hardware cost
    initial_om_cost = capacity_kwh * om_cost_per_kwh_year # O&M cost in year 1
    net_initial_cost = bess_cost - incentives.get("total_incentive", 0) # Cost after year 0 incentives

    if net_initial_cost < 0:
        print("Warning: Total incentives exceed initial BESS cost.")

    # --- Battery Life Calculation ---
    if days_per_year <= 0 or cycles_per_day <= 0 or cycle_life <= 0:
        cycles_per_year = 0
        battery_life_years = float('inf')
    else:
        cycles_per_year = cycles_per_day * days_per_year
        battery_life_years = cycle_life / cycles_per_year

    # --- Cash Flow Calculation Loop ---
    cash_flows = [-net_initial_cost]  # Year 0: Net initial investment

    for year in range(1, years + 1):
        # Inflated Savings and O&M Costs
        savings_t = annual_savings * ((1 + inflation_rate) ** (year - 1))
        o_m_cost_t = initial_om_cost * ((1 + inflation_rate) ** (year - 1))

        # Corrected Recurring Replacement Cost Logic
        replacement_cost_year = 0
        if battery_life_years > 0:
             # Replacements due by start of year vs end of year
             replacements_due_by_last_year = np.floor((year - 1) / battery_life_years)
             replacements_due_by_this_year = np.floor(year / battery_life_years)

             if replacements_due_by_this_year > replacements_due_by_last_year:
                 inflated_replacement_cost = bess_cost * ((1 + inflation_rate) ** (year - 1))
                 # Assuming no incentives on replacement cost
                 replacement_cost_year = inflated_replacement_cost
                 # print(f"DEBUG: Battery replacement cost ${replacement_cost_year:,.0f} applied in year {year}") # Optional

        # EBT (Earnings Before Tax) - Simplified (no depreciation)
        ebt = savings_t - o_m_cost_t - replacement_cost_year

        # Taxes
        taxes = ebt * tax_rate if ebt > 0 else 0

        # Net Cash Flow (After Tax, Before Salvage)
        net_cash_flow = savings_t - o_m_cost_t - replacement_cost_year - taxes

        # Corrected Salvage Value Logic (Applied ONLY in the final year)
        if year == years:
            salvage_value_year = 0 # Start with 0 salvage for this year
            # Base salvage on the *original* cost, inflated to the final year
            inflated_original_cost = bess_cost * ((1 + inflation_rate) ** (year - 1))
            base_salvage = inflated_original_cost * salvage_fraction

            # Calculate age of the battery operating in the final year
            age_of_final_battery = years
            if battery_life_years > 0:
                 num_prior_replacements = np.floor(years / battery_life_years)
                 # When the last battery was installed (relative to project start time 0)
                 last_replacement_install_time = num_prior_replacements * battery_life_years
                 age_of_final_battery = years - last_replacement_install_time

            # Calculate remaining life fraction
            remaining_life_fraction = 0.0
            if battery_life_years > 0:
                 remaining_life_fraction = max(0, 1 - (age_of_final_battery / battery_life_years))

            # Calculate raw salvage and after-tax salvage
            raw_salvage_value = base_salvage * remaining_life_fraction
            # Assume salvage taxed as ordinary income (simplification)
            salvage_after_tax = raw_salvage_value * (1 - tax_rate)
            salvage_value_year = salvage_after_tax
            # print(f"DEBUG: Salvage Value: Base=${base_salvage:,.0f}, Final Age={age_of_final_battery:.1f}yrs, Frac={remaining_life_fraction:.2f}, Applied=${salvage_value_year:,.0f}") # Optional

            # Add the calculated after-tax salvage to the net cash flow for THIS final year
            net_cash_flow += salvage_value_year

        # Append the calculated cash flow for the current year
        cash_flows.append(net_cash_flow)
    # --- End of Cash Flow Loop ---

    # --- Calculate Financial Metrics ---
    npv = float('nan')
    irr = float('nan')
    try:
        if wacc > -1:
             npv = npf.npv(wacc, cash_flows)
        else:
             print("Warning: WACC <= -1, cannot calculate NPV.")
    except Exception as e:
        print(f"Error calculating NPV: {e}")

    try:
        # Check for valid cash flow pattern for IRR calculation
        if cash_flows and len(cash_flows) > 1 and cash_flows[0] < 0 and any(cf > 0 for cf in cash_flows[1:]):
            irr = npf.irr(cash_flows)
            # npf.irr might return nan if it fails to converge
            if irr is None or np.isnan(irr): irr = float("nan")
        else:
             # If pattern invalid (e.g., no sign change, all negative), IRR is undefined or meaningless
             irr = float('nan')
    except Exception as e:
        # Catch potential errors during IRR calculation
        print(f"Error calculating IRR: {e}")
        irr = float('nan')

    # --- Payback Period Calculation ---
    cumulative_cash_flow = cash_flows[0] # Initial investment (usually negative)
    payback_years = float('inf') # Default if never pays back

    if cumulative_cash_flow >= 0: # Pays back immediately (Year 0 due to high incentives > cost)
        payback_years = 0.0
    else:
        # Iterate through years 1 to end
        for year_pbk in range(1, len(cash_flows)):
            current_year_cf = cash_flows[year_pbk]
            # Check if adding this year's cash flow makes cumulative non-negative
            if cumulative_cash_flow + current_year_cf >= 0:
                # Calculate fractional year if CF is positive
                fraction_needed = abs(cumulative_cash_flow) / current_year_cf if current_year_cf > 0 else 0
                payback_years = (year_pbk - 1) + fraction_needed
                break # Payback found
            cumulative_cash_flow += current_year_cf # Add this year's flow

    # --- Return Results ---
    return {
        "npv": npv,
        "irr": irr,
        "payback_years": payback_years,
        "cash_flows": cash_flows,
        "net_initial_cost": net_initial_cost,
        "battery_life_years": battery_life_years,
        "annual_savings_year1": annual_savings, # Base savings for reference
        "initial_om_cost_year1": initial_om_cost, # Base O&M for reference
    }


def optimize_battery_size(
    eaf_params, utility_params, financial_params, incentive_params, bess_base_params
):
    """Find optimal battery size (Capacity MWh, Power MW) for best ROI using NPV as metric"""
    # Define search space for battery capacity & power
    # Reduced steps for faster testing, increase for finer grid search
    capacity_options = np.linspace(5, 100, 10)  # 5 MWh to 100 MWh in 10 steps
    power_options = np.linspace(2, 50, 10)  # 2 MW to 50 MW in 10 steps

    best_npv = -float("inf")  # Optimize for NPV
    best_capacity = None
    best_power = None
    best_metrics = None
    optimization_results = []

    print(
        f"Starting optimization: {len(capacity_options)} capacities, {len(power_options)} powers..."
    )

    count = 0
    total_combinations = len(capacity_options) * len(power_options)

    # Grid search
    for capacity in capacity_options:
        for power in power_options:
            count += 1
            print(
                f"  Testing {count}/{total_combinations}: Cap={capacity:.1f} MWh, Pow={power:.1f} MW"
            )

            # Skip invalid combinations (e.g., power >> capacity might be unrealistic/costly)
            # Rule of thumb: C-rate (Power/Capacity) between 0.25 and 2 is common.
            c_rate = power / capacity if capacity > 0 else float("inf")
            if not (0.2 <= c_rate <= 2.5):  # Allow wider range for exploration
                print(f"    Skipping C-rate {c_rate:.2f} (out of range 0.2-2.5)")
                continue

            # Create test BESS parameters based on the base, modifying size
            test_bess_params = bess_base_params.copy()
            test_bess_params["capacity"] = capacity
            test_bess_params["power_max"] = power

            try:
                # --- Run full analysis for this combination ---
                billing_results = calculate_annual_billings(
                    eaf_params, test_bess_params, utility_params
                )
                annual_savings = billing_results["annual_savings"]

                incentive_results = calculate_incentives(
                    test_bess_params, incentive_params
                )

                # Pass eaf_params for cycle/day info
                metrics = calculate_financial_metrics(
                    test_bess_params,
                    financial_params,
                    eaf_params,
                    annual_savings,
                    incentive_results,
                )

                # Store results for this combination
                current_result = {
                    "capacity": capacity,
                    "power": power,
                    "npv": metrics["npv"],
                    "irr": metrics["irr"],
                    "payback_years": metrics["payback_years"],
                    "annual_savings": annual_savings,
                    "net_initial_cost": metrics["net_initial_cost"],
                }
                optimization_results.append(current_result)

                # Update best result if current NPV is better
                # Ensure NPV is a valid number before comparing
                if pd.notna(metrics["npv"]) and metrics["npv"] > best_npv:
                    best_npv = metrics["npv"]
                    best_capacity = capacity
                    best_power = power
                    best_metrics = metrics  # Store the full metrics dict
                    print(f"    *** New best NPV found: ${best_npv:,.0f} ***")

            except Exception as e:
                print(
                    f"    Error during optimization step (Cap={capacity:.1f}, Pow={power:.1f}): {e}"
                )
                optimization_results.append(
                    {
                        "capacity": capacity,
                        "power": power,
                        "npv": float("nan"),
                        "error": str(e),
                    }
                )  # Log error

    print("Optimization finished.")

    return {
        "best_capacity": best_capacity,
        "best_power": best_power,
        "best_npv": best_npv,
        "best_metrics": best_metrics,  # Contains all metrics for the best combo
        "all_results": optimization_results,  # List of dicts for each combo tested
    }


# --- Application Layout ---
app.layout = html.Div(
    [
        # Store components for maintaining state across callbacks
        # Initialize stores with default data
        dcc.Store(id="eaf-params-store", data=nucor_mills["Custom"]),
        dcc.Store(id="utility-params-store", data=utility_rates["Custom Utility"]),
        dcc.Store(id="bess-params-store", data=default_bess_params),
        dcc.Store(id="financial-params-store", data=default_financial_params),
        dcc.Store(id="incentive-params-store", data=default_incentive_params),
        dcc.Store(id="calculation-results-store", data={}),  # Stores final calc outputs
        dcc.Store(
            id="optimization-results-store", data={}
        ),  # Stores optimization run outputs
        html.Div(
            [
                html.H1(
                    "Battery Profitability Tool", className="mb-4 text-center"
                ),
                # Container for validation errors/warnings
                html.Div(
                    id="validation-error-container",
                    className="alert alert-danger mx-auto",  # Centered
                    style={
                        "display": "none",
                        "max-width": "800px",
                    },  # Initially hidden, limited width
                ),
                # Container for general calculation errors
                html.Div(
                    id="calculation-error-container",
                    className="alert alert-warning mx-auto",  # Centered
                    style={"display": "none", "max-width": "800px"},  # Initially hidden
                ),
                # Tabs for organized sections
                dcc.Tabs(
                    id="main-tabs",
                    value="tab-mill",
                    children=[
                        # Mill Selection Tab
                        dcc.Tab(
                            label="1. Mill Selection",
                            value="tab-mill",
                            children=[
                                html.Div(
                                    [
                                        html.H3("Select Nucor Mill", className="mb-3"),
                                        html.P(
                                            "Choose a mill to pre-fill parameters, or select 'Custom' to enter values manually.",
                                            className="text-muted mb-4",
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Mill Selection:",
                                                    className="form-label",
                                                ),
                                                dcc.Dropdown(
                                                    id="mill-selection-dropdown",
                                                    options=[
                                                        {
                                                            "label": f"Nucor Steel {mill}",
                                                            "value": mill,
                                                        }
                                                        for mill in nucor_mills.keys()
                                                    ],
                                                    value="Custom",  # Default to Custom
                                                    clearable=False,
                                                    className="form-select mb-3",
                                                ),
                                            ],
                                            className="mb-4",
                                        ),
                                        # Mill Information Card
                                        html.Div(
                                            id="mill-info-card", className="card mb-4"
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Continue to Parameters",
                                                    id="continue-to-params-button",
                                                    n_clicks=0,
                                                    className="btn btn-primary mt-3",
                                                )
                                            ],
                                            className="d-flex justify-content-center",
                                        ),
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),  # End Tab 1
                        # Parameters Tab
                        dcc.Tab(
                            label="2. System Parameters",
                            value="tab-params",
                            children=[
                                html.Div(
                                    [
                                        html.Div(  # Row for parameters
                                            [
                                                # Left column: Utility & EAF Parameters
                                                html.Div(
                                                    [
                                                        # Utility Parameters Section
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "Utility Rates",
                                                                    className="mb-3",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Utility Provider:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Dropdown(
                                                                            id="utility-provider-dropdown",
                                                                            options=[
                                                                                {
                                                                                    "label": utility,
                                                                                    "value": utility,
                                                                                }
                                                                                for utility in utility_rates.keys()
                                                                            ],
                                                                            value="Custom Utility",  # Default
                                                                            clearable=False,
                                                                            className="form-select mb-3",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # Basic rate inputs
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Off-Peak Rate ($/MWh):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="off-peak-rate",
                                                                            type="number",
                                                                            value=default_utility_params[
                                                                                "energy_rates"
                                                                            ][
                                                                                "off_peak"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Mid-Peak Rate ($/MWh):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="mid-peak-rate",
                                                                            type="number",
                                                                            value=default_utility_params[
                                                                                "energy_rates"
                                                                            ][
                                                                                "mid_peak"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Peak Rate ($/MWh):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="peak-rate",
                                                                            type="number",
                                                                            value=default_utility_params[
                                                                                "energy_rates"
                                                                            ][
                                                                                "peak"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Demand Charge ($/kW/month):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="demand-charge",
                                                                            type="number",
                                                                            value=default_utility_params[
                                                                                "demand_charge"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                # Seasonal Rates Toggle
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="seasonal-rates-toggle",
                                                                            options=[
                                                                                {
                                                                                    "label": "Enable Seasonal Rate Variations",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                [
                                                                                    "enabled"
                                                                                ]
                                                                                if default_utility_params[
                                                                                    "seasonal_rates"
                                                                                ]
                                                                                else []
                                                                            ),
                                                                            className="form-check form-switch",  # Use switch style
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # Seasonal multipliers (conditionally shown)
                                                                html.Div(
                                                                    id="seasonal-rates-container",
                                                                    className="mb-3 border p-2 rounded",
                                                                    style={
                                                                        "display": "none"
                                                                    },
                                                                ),  # Initially hidden
                                                                # Time-of-Use Periods
                                                                html.H5(
                                                                    "Time-of-Use Periods",
                                                                    className="mb-2",
                                                                ),
                                                                html.P(
                                                                    "Define periods covering 24 hours. Gaps will be filled with Off-Peak.",
                                                                    className="small text-muted",
                                                                ),
                                                                html.Div(
                                                                    id="tou-periods-container"
                                                                ),  # Populated by callback
                                                                html.Button(
                                                                    "Add TOU Period",
                                                                    id="add-tou-period-button",
                                                                    n_clicks=0,
                                                                    className="btn btn-sm btn-outline-success mt-2",
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),  # End Utility Card
                                                        # EAF Parameters Section
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "EAF Parameters",
                                                                    className="mb-3",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "EAF Size (tons):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="eaf-size",
                                                                            type="number",
                                                                            value=nucor_mills[
                                                                                "Custom"
                                                                            ][
                                                                                "eaf_size"
                                                                            ],
                                                                            min=1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Number of EAFs:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="eaf-count",
                                                                            type="number",
                                                                            value=nucor_mills[
                                                                                "Custom"
                                                                            ][
                                                                                "eaf_count"
                                                                            ],
                                                                            min=1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Grid Power Limit (MW):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="grid-cap",
                                                                            type="number",
                                                                            value=nucor_mills[
                                                                                "Custom"
                                                                            ][
                                                                                "grid_cap"
                                                                            ],
                                                                            min=1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "EAF Cycles per Day:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="cycles-per-day",
                                                                            type="number",
                                                                            value=nucor_mills[
                                                                                "Custom"
                                                                            ][
                                                                                "cycles_per_day"
                                                                            ],
                                                                            min=1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Avg. Cycle Duration (minutes):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="cycle-duration",
                                                                            type="number",
                                                                            value=nucor_mills[
                                                                                "Custom"
                                                                            ][
                                                                                "cycle_duration"
                                                                            ],
                                                                            min=1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Operating Days per Year:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="days-per-year",
                                                                            type="number",
                                                                            value=nucor_mills[
                                                                                "Custom"
                                                                            ][
                                                                                "days_per_year"
                                                                            ],
                                                                            min=1,
                                                                            max=366,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            className="card p-3",
                                                        ),  # End EAF Card
                                                    ],
                                                    className="col-md-6",
                                                ),  # End Left Column
                                                # Right Column: BESS & Financial Parameters
                                                html.Div(
                                                    [
                                                        # BESS Parameters Section
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "BESS Parameters",
                                                                    className="mb-3",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Energy Capacity (MWh):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="bess-capacity",
                                                                            type="number",
                                                                            value=default_bess_params[
                                                                                "capacity"
                                                                            ],
                                                                            min=0.1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Power Rating (MW):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="bess-power",
                                                                            type="number",
                                                                            value=default_bess_params[
                                                                                "power_max"
                                                                            ],
                                                                            min=0.1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Round-Trip Efficiency (%):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="bess-rte",
                                                                            type="number",
                                                                            value=default_bess_params[
                                                                                "rte"
                                                                            ]
                                                                            * 100,
                                                                            min=1,
                                                                            max=100,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Cycle Life (# of cycles):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="bess-cycle-life",
                                                                            type="number",
                                                                            value=default_bess_params[
                                                                                "cycle_life"
                                                                            ],
                                                                            min=100,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "BESS Cost ($/kWh):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="bess-cost-per-kwh",
                                                                            type="number",
                                                                            value=default_bess_params[
                                                                                "cost_per_kwh"
                                                                            ],
                                                                            min=1,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "O&M Cost ($/kWh/year):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="bess-om-cost",
                                                                            type="number",
                                                                            value=default_bess_params[
                                                                                "om_cost_per_kwh_year"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),  # End BESS Card
                                                        # Financial Parameters Section
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "Financial Parameters",
                                                                    className="mb-3",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "WACC (%):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="wacc",
                                                                            type="number",
                                                                            value=round(default_financial_params[
                                                                                "wacc"
                                                                            ]
                                                                            * 100, 1),
                                                                            min=0,
                                                                            max=100,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                # Removed Interest Rate & Debt Fraction as they aren't used in simplified finance model
                                                                # html.Div([html.Label("Interest Rate (%):", className="form-label"),dcc.Input(id="interest-rate", type="number",value=default_financial_params["interest_rate"] * 100,min=0, max=100, className="form-control"),], className="mb-2"),
                                                                # html.Div([html.Label("Debt Fraction (%):", className="form-label"), dcc.Input(id="debt-fraction", type="number", value=default_financial_params["debt_fraction"] * 100, min=0, max=100, className="form-control"),], className="mb-2"),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Project Lifespan (years):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="project-lifespan",
                                                                            type="number",
                                                                            value=default_financial_params[
                                                                                "project_lifespan"
                                                                            ],
                                                                            min=1,
                                                                            max=50,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Tax Rate (%):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="tax-rate",
                                                                            type="number",
                                                                            value=default_financial_params[
                                                                                "tax_rate"
                                                                            ]
                                                                            * 100,
                                                                            min=0,
                                                                            max=100,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Inflation Rate (%):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="inflation-rate",
                                                                            type="number",
                                                                            value=default_financial_params[
                                                                                "inflation_rate"
                                                                            ]
                                                                            * 100,
                                                                            min=-5,
                                                                            max=100,
                                                                            className="form-control",
                                                                        ),  # Allow deflation
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Salvage Value (% of initial BESS cost):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="salvage-value",
                                                                            type="number",
                                                                            value=default_financial_params[
                                                                                "salvage_value"
                                                                            ]
                                                                            * 100,
                                                                            min=0,
                                                                            max=100,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            className="card p-3",
                                                        ),  # End Financial Card
                                                    ],
                                                    className="col-md-6",
                                                ),  # End Right Column
                                            ],
                                            className="row",
                                        ),  # End Param Row
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Continue to Incentives",
                                                    id="continue-to-incentives-button",
                                                    n_clicks=0,
                                                    className="btn btn-primary mt-4 mb-3",
                                                )
                                            ],
                                            className="d-flex justify-content-center",
                                        ),
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),  # End Tab 2
                        # Incentives Tab
                        dcc.Tab(
                            label="3. Battery Incentives",
                            value="tab-incentives",
                            children=[
                                html.Div(
                                    [
                                        html.H3(
                                            "Battery Incentive Programs",
                                            className="mb-4 text-center",
                                        ),
                                        html.P(
                                            "Select applicable incentives. Ensure values are correct for your location/project.",
                                            className="text-muted mb-4 text-center",
                                        ),
                                        html.Div(  # Row for incentives
                                            [
                                                # Left column: Federal Incentives
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "Federal Incentives",
                                                                    className="mb-3",
                                                                ),
                                                                # ITC
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="itc-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " Investment Tax Credit (ITC)",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "itc_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "ITC Percentage (%):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="itc-percentage",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "itc_percentage"
                                                                                    ],
                                                                                    min=0,
                                                                                    max=100,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),  # Indent input
                                                                        html.P(
                                                                            "Tax credit on capital expenditure.",
                                                                            className="text-muted small ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # CEIC
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="ceic-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " Clean Electricity Investment Credit (CEIC)",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "ceic_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "CEIC Percentage (%):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="ceic-percentage",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "ceic_percentage"
                                                                                    ],
                                                                                    min=0,
                                                                                    max=100,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),
                                                                        html.P(
                                                                            "Mutually exclusive with ITC; higher value applies.",
                                                                            className="text-muted small ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # Bonus Credits
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="bonus-credit-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " Bonus Credits (Energy Communities, Domestic Content)",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "bonus_credit_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "Bonus Percentage (%):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="bonus-credit-percentage",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "bonus_credit_percentage"
                                                                                    ],
                                                                                    min=0,
                                                                                    max=100,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),
                                                                        html.P(
                                                                            "Stacks with ITC/CEIC.",
                                                                            className="text-muted small ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),
                                                    ],
                                                    className="col-md-6",
                                                ),  # End Left Col
                                                # Right column: State Incentives & Custom
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [  # State Card
                                                                html.H4(
                                                                    "State Incentives (Examples)",
                                                                    className="mb-3",
                                                                ),
                                                                # SGIP
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="sgip-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " CA Self-Generation Incentive Program (SGIP)",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "sgip_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "SGIP Amount ($/kWh):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="sgip-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "sgip_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # ESS
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="ess-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " CT Energy Storage Solutions",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "ess_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "ESS Amount ($/kWh):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="ess-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "ess_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # MABI
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="mabi-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " NY Market Acceleration Bridge Incentive",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "mabi_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "MABI Amount ($/kWh):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="mabi-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "mabi_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # CS
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="cs-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": " MA Connected Solutions",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=(
                                                                                []
                                                                                if not default_incentive_params[
                                                                                    "cs_enabled"
                                                                                ]
                                                                                else [
                                                                                    "enabled"
                                                                                ]
                                                                            ),
                                                                            className="form-check mb-1",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "CS Amount ($/kWh):",
                                                                                    className="form-label form-label-sm",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="cs-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "cs_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control form-control-sm",
                                                                                ),
                                                                            ],
                                                                            className="mb-2 ms-4",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),
                                                        # Custom Incentive Card
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "Custom Incentive",
                                                                    className="mb-3",
                                                                ),
                                                                dcc.Checklist(
                                                                    id="custom-incentive-enabled",
                                                                    options=[
                                                                        {
                                                                            "label": " Enable Custom Incentive",
                                                                            "value": "enabled",
                                                                        }
                                                                    ],
                                                                    value=(
                                                                        []
                                                                        if not default_incentive_params[
                                                                            "custom_incentive_enabled"
                                                                        ]
                                                                        else ["enabled"]
                                                                    ),
                                                                    className="form-check mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Incentive Type:",
                                                                            className="form-label form-label-sm",
                                                                        ),
                                                                        dcc.RadioItems(
                                                                            id="custom-incentive-type",
                                                                            options=[
                                                                                {
                                                                                    "label": " $/kWh",
                                                                                    "value": "per_kwh",
                                                                                },
                                                                                {
                                                                                    "label": " % of Cost",
                                                                                    "value": "percentage",
                                                                                },
                                                                            ],
                                                                            value=default_incentive_params[
                                                                                "custom_incentive_type"
                                                                            ],
                                                                            inline=True,
                                                                            className="form-check",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 ms-4",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Incentive Amount:",
                                                                            className="form-label form-label-sm",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="custom-incentive-amount",
                                                                            type="number",
                                                                            value=default_incentive_params[
                                                                                "custom_incentive_amount"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control form-control-sm",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 ms-4",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Description:",
                                                                            className="form-label form-label-sm",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="custom-incentive-description",
                                                                            type="text",
                                                                            value=default_incentive_params[
                                                                                "custom_incentive_description"
                                                                            ],
                                                                            className="form-control form-control-sm",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 ms-4",
                                                                ),
                                                            ],
                                                            className="card p-3",
                                                        ),
                                                    ],
                                                    className="col-md-6",
                                                ),  # End Right Col
                                            ],
                                            className="row",
                                        ),  # End Incentive Row
                                        # Action Buttons
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Calculate Results",
                                                    id="calculate-results-button",
                                                    n_clicks=0,
                                                    className="btn btn-primary mt-4 mb-3 me-3",
                                                ),
                                                html.Button(
                                                    "Optimize Battery Size",
                                                    id="optimize-battery-button",
                                                    n_clicks=0,
                                                    className="btn btn-success mt-4 mb-3",
                                                ),
                                                # Removed Debug Button
                                                # html.Button("Show Debug Info", id="debug-button", n_clicks=0, className="btn btn-warning mt-4 mb-3 ms-3"),
                                            ],
                                            className="d-flex justify-content-center",
                                        ),
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),  # End Tab 3
                        # Results Tab
                        dcc.Tab(
                            label="4. Results & Analysis",
                            value="tab-results",
                            children=[
                                html.Div(
                                    [
                                        # Loading spinner wraps the output container
                                        dcc.Loading(
                                            id="loading-results",
                                            type="circle",  # Options: "graph", "cube", "circle", "dot", "default"
                                            children=[
                                                html.Div(
                                                    id="results-output-container",
                                                    className="mt-4",
                                                )
                                                # Initial content or leave empty until calculation
                                                # html.P("Results will appear here after calculation.", className="text-center text-muted")
                                            ],
                                        )
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),  # End Tab 4
                        # Battery Sizing Optimization Tab
                        dcc.Tab(
                            label="5. Battery Sizing Tool",
                            value="tab-optimization",
                            children=[
                                html.Div(
                                    [
                                        dcc.Loading(
                                            id="loading-optimization",
                                            type="circle",
                                            children=[
                                                html.Div(
                                                    id="optimization-output-container",
                                                    className="mt-4",
                                                )
                                                # html.P("Optimization results will appear here.", className="text-center text-muted")
                                            ],
                                        )
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),  # End Tab 5
                    ],
                ),  # End Tabs
            ],
            className="container-fluid bg-light min-vh-100 py-4",
        ),
    ]
)

# --- Callbacks ---


# Callback to navigate tabs using "Continue" buttons
@app.callback(
    Output("main-tabs", "value"),
    [
        Input("continue-to-params-button", "n_clicks"),
        Input("continue-to-incentives-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def navigate_tabs(n_params, n_incentives):
    ctx = callback_context
    if not ctx.triggered_id:
        return dash.no_update

    if ctx.triggered_id == "continue-to-params-button":
        return "tab-params"
    elif ctx.triggered_id == "continue-to-incentives-button":
        return "tab-incentives"
    else:
        return dash.no_update


# Callback to update EAF params store based on inputs
@app.callback(
    Output("eaf-params-store", "data"),
    [Input("eaf-size", "value"),
     Input("eaf-count", "value"),
     Input("grid-cap", "value"),
     Input("cycles-per-day", "value"),
     Input("cycle-duration", "value"), # Input component value
     Input("days-per-year", "value"),
     Input("mill-selection-dropdown", "value")],
    State("eaf-params-store", "data") # Get previous state
)
def update_eaf_params_store(size, count, grid_cap, cycles, duration, days, selected_mill, existing_data):
    ctx = callback_context
    triggered_id = ctx.triggered_id if ctx.triggered_id else 'unknown'

    # Start with the previous state or default Custom data if no valid existing state
    output_data = {}
    if existing_data and isinstance(existing_data, dict):
        output_data = existing_data.copy()
    else:
        output_data = nucor_mills["Custom"].copy()
        # Ensure cycle_duration_input exists in Custom default
        if "cycle_duration_input" not in output_data:
             output_data["cycle_duration_input"] = output_data.get("cycle_duration", 0)

    if triggered_id == "mill-selection-dropdown":
        # --- Triggered by Dropdown ---
        # Load data fully from the selected mill's definition
        if selected_mill and selected_mill in nucor_mills:
            output_data = nucor_mills[selected_mill].copy()
        else: # Load Custom defaults if dropdown selection is invalid or "Custom"
            output_data = nucor_mills["Custom"].copy()
        # *** Always ensure cycle_duration_input is set after loading from mill data ***
        output_data["cycle_duration_input"] = output_data.get("cycle_duration", 0)

    else:
        # --- Triggered by Individual Input Change ---
        # Apply updates one by one only if the value is not None
        # This prevents None values during transitions from overwriting good data
        if size is not None: output_data["eaf_size"] = size
        if count is not None: output_data["eaf_count"] = count
        if grid_cap is not None: output_data["grid_cap"] = grid_cap
        if cycles is not None: output_data["cycles_per_day"] = cycles
        if duration is not None:
            output_data["cycle_duration"] = duration
            # Always update cycle_duration_input if cycle_duration changes from a valid input
            output_data["cycle_duration_input"] = duration
        if days is not None: output_data["days_per_year"] = days

    # *** Final Validation/Cleanup before returning ***
    # Ensure 'cycle_duration' and 'cycle_duration_input' keys exist and are numeric >= 0

    base_duration = output_data.get("cycle_duration")
    input_duration = output_data.get("cycle_duration_input")

    # Convert to numeric, default to 0 if invalid/None
    try: base_duration = float(base_duration) if base_duration is not None else 0.0
    except (ValueError, TypeError): base_duration = 0.0
    try: input_duration = float(input_duration) if input_duration is not None else 0.0
    except (ValueError, TypeError): input_duration = 0.0

    # Ensure non-negative
    base_duration = max(0.0, base_duration)
    input_duration = max(0.0, input_duration)

    # If input_duration became invalid (0), but base_duration is valid (>0), reset input
    if input_duration <= 0 and base_duration > 0:
        output_data["cycle_duration_input"] = base_duration
    elif input_duration > 0: # If input duration is valid, ensure base duration matches
         output_data["cycle_duration"] = input_duration
    else: # If both seem invalid, set both to 0
         output_data["cycle_duration"] = 0.0
         output_data["cycle_duration_input"] = 0.0

    # Update the dictionary with cleaned values
    output_data["cycle_duration"] = base_duration
    output_data["cycle_duration_input"] = input_duration


    return output_data


# Callback to update BESS params store
@app.callback(
    Output("bess-params-store", "data"),
    [
        Input("bess-capacity", "value"),
        Input("bess-power", "value"),
        Input("bess-rte", "value"),
        Input("bess-cycle-life", "value"),
        Input("bess-cost-per-kwh", "value"),
        Input("bess-om-cost", "value"),
    ],
)
def update_bess_params_store(capacity, power, rte, cycle_life, cost_kwh, om_cost):
    return {
        "capacity": capacity,
        "power_max": power,
        "rte": (
            rte / 100.0 if rte is not None else default_bess_params["rte"]
        ),  # Convert percentage
        "cycle_life": cycle_life,
        "cost_per_kwh": cost_kwh,
        "om_cost_per_kwh_year": om_cost,
    }


# Callback to update Financial params store
@app.callback(
    Output("financial-params-store", "data"),
    [
        Input("wacc", "value"),
        # Input("interest-rate", "value"), # Removed
        # Input("debt-fraction", "value"), # Removed
        Input("project-lifespan", "value"),
        Input("tax-rate", "value"),
        Input("inflation-rate", "value"),
        Input("salvage-value", "value"),
    ],
)
def update_financial_params_store(wacc, lifespan, tax, inflation, salvage):
    return {
        "wacc": wacc / 100.0 if wacc is not None else default_financial_params["wacc"],
        # "interest_rate": interest / 100.0 if interest is not None else default_financial_params['interest_rate'],
        # "debt_fraction": debt / 100.0 if debt is not None else default_financial_params['debt_fraction'],
        "project_lifespan": lifespan,
        "tax_rate": (
            tax / 100.0 if tax is not None else default_financial_params["tax_rate"]
        ),
        "inflation_rate": (
            inflation / 100.0
            if inflation is not None
            else default_financial_params["inflation_rate"]
        ),
        "salvage_value": (
            salvage / 100.0
            if salvage is not None
            else default_financial_params["salvage_value"]
        ),
    }


# Callback to update Incentive params store
@app.callback(
    Output("incentive-params-store", "data"),
    [
        Input("itc-enabled", "value"),
        Input("itc-percentage", "value"),
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
    return {
        "itc_enabled": "enabled" in itc_en,
        "itc_percentage": itc_pct,
        "ceic_enabled": "enabled" in ceic_en,
        "ceic_percentage": ceic_pct,
        "bonus_credit_enabled": "enabled" in bonus_en,
        "bonus_credit_percentage": bonus_pct,
        "sgip_enabled": "enabled" in sgip_en,
        "sgip_amount": sgip_amt,
        "ess_enabled": "enabled" in ess_en,
        "ess_amount": ess_amt,
        "mabi_enabled": "enabled" in mabi_en,
        "mabi_amount": mabi_amt,
        "cs_enabled": "enabled" in cs_en,
        "cs_amount": cs_amt,
        "custom_incentive_enabled": "enabled" in custom_en,
        "custom_incentive_type": custom_type,
        "custom_incentive_amount": custom_amt,
        "custom_incentive_description": custom_desc,
    }


# Callback to update Utility parameters store AND performs filling gaps
@app.callback(
    Output("utility-params-store", "data"),
    [
        Input("utility-provider-dropdown", "value"),
        Input("off-peak-rate", "value"),
        Input("mid-peak-rate", "value"),
        Input("peak-rate", "value"),
        Input("demand-charge", "value"),
        Input("seasonal-rates-toggle", "value"),
        # Use pattern-matching for dynamic inputs if feasible or standard inputs
        Input("winter-multiplier", "value"),
        Input("summer-multiplier", "value"),
        Input("shoulder-multiplier", "value"),
        Input("winter-months", "value"),
        Input("summer-months", "value"),
        Input("shoulder-months", "value"),
        # Inputs for dynamically added TOU periods
        Input({"type": "tou-start", "index": ALL}, "value"),
        Input({"type": "tou-end", "index": ALL}, "value"),
        Input({"type": "tou-rate", "index": ALL}, "value"),
    ],
    State("utility-params-store", "data"),  # Get existing state
)
def update_utility_params_store(
    utility_provider,
    off_peak_rate,
    mid_peak_rate,
    peak_rate,
    demand_charge,
    seasonal_toggle,
    winter_mult,
    summer_mult,
    shoulder_mult,
    winter_months_str,
    summer_months_str,
    shoulder_months_str,
    tou_starts,
    tou_ends,
    tou_rates,
    existing_data,
):
    """Update utility parameters store based on user inputs and fill TOU gaps."""

    ctx = callback_context
    triggered_id = ctx.triggered_id

    # Base parameters on provider selection or existing custom data
    if isinstance(triggered_id, str) and triggered_id == "utility-provider-dropdown":
        # Load defaults for the selected provider
        if utility_provider in utility_rates:
            params = utility_rates[utility_provider].copy()
            # Ensure raw tou_periods exists if loading from preset
            params["tou_periods_raw"] = params.get(
                "tou_periods", default_utility_params["tou_periods_raw"]
            )
        else:  # Should default to "Custom Utility" which references default_utility_params
            params = default_utility_params.copy()
    elif existing_data:
        # If other inputs changed, start with the current custom data
        params = existing_data.copy()
    else:
        # Fallback to default if no existing data (e.g., first load)
        params = default_utility_params.copy()

    # Update basic rates from direct inputs
    params["energy_rates"] = {
        "off_peak": off_peak_rate,
        "mid_peak": mid_peak_rate,
        "peak": peak_rate,
    }
    params["demand_charge"] = demand_charge

    # Update seasonal settings
    params["seasonal_rates"] = (
        True if seasonal_toggle and "enabled" in seasonal_toggle else False
    )

    # Safely parse month strings
    def parse_months(month_str, default_list):
        if not isinstance(month_str, str):
            return default_list
        try:
            parsed = [
                int(m.strip())
                for m in month_str.split(",")
                if m.strip() and 1 <= int(m.strip()) <= 12
            ]
            return parsed if parsed else default_list
        except ValueError:
            return default_list

    # Only update seasonal details if seasonal rates are enabled or inputs were triggered
    if params["seasonal_rates"] or any(
        trig["prop_id"].startswith(p)
        for trig in ctx.triggered
        for p in ["winter-", "summer-", "shoulder-"]
    ):
        params["winter_months"] = parse_months(
            winter_months_str, default_utility_params["winter_months"]
        )
        params["summer_months"] = parse_months(
            summer_months_str, default_utility_params["summer_months"]
        )
        params["shoulder_months"] = parse_months(
            shoulder_months_str, default_utility_params["shoulder_months"]
        )
        params["winter_multiplier"] = (
            winter_mult
            if winter_mult is not None
            else default_utility_params["winter_multiplier"]
        )
        params["summer_multiplier"] = (
            summer_mult
            if summer_mult is not None
            else default_utility_params["summer_multiplier"]
        )
        params["shoulder_multiplier"] = (
            shoulder_mult
            if shoulder_mult is not None
            else default_utility_params["shoulder_multiplier"]
        )

    # Build RAW TOU periods list from dynamic inputs
    # Only update if TOU inputs were triggered
    tou_triggered = any("tou-" in trig["prop_id"] for trig in ctx.triggered)

    # Load raw periods from preset if provider changed, otherwise use dynamic inputs
    if isinstance(triggered_id, str) and triggered_id == "utility-provider-dropdown":
        raw_tou_periods = params.get(
            "tou_periods", default_utility_params["tou_periods_raw"]
        )  # Use preset's tou list
    else:
        # Construct from dynamic inputs
        raw_tou_periods = []
        for i in range(len(tou_starts)):
            # Add basic validation for dynamic inputs
            start_val = tou_starts[i]
            end_val = tou_ends[i]
            rate_val = tou_rates[i]
            if start_val is not None and end_val is not None and rate_val is not None:
                try:
                    start_f = float(start_val)
                    end_f = float(end_val)
                    if 0 <= start_f < end_f <= 24:  # Ensure valid range
                        raw_tou_periods.append((start_f, end_f, str(rate_val)))
                    else:
                        print(f"Warning: Invalid TOU range {start_f}-{end_f} ignored.")
                except (ValueError, TypeError):
                    print(
                        f"Warning: Invalid TOU numeric values ({start_val}, {end_val}) ignored."
                    )
            elif (
                rate_val is not None
            ):  # Handle cases where numbers might be missing but rate exists
                print(f"Warning: Incomplete TOU period at index {i} ignored.")

    # Store the raw periods and calculate/store the filled periods
    params["tou_periods_raw"] = raw_tou_periods
    params["tou_periods_filled"] = fill_tou_gaps(raw_tou_periods)

    return params


# Callback to update Mill Info Card when mill is selected
@app.callback(
    Output("mill-info-card", "children"), Input("mill-selection-dropdown", "value")
)
def update_mill_info(selected_mill):
    """Update the mill information card based on the selected mill"""
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]  # Default to Custom info
        selected_mill = "Custom"  # Ensure title reflects Custom
        card_header_class = (
            "card-header bg-secondary text-white"  # Different color for custom
        )
    else:
        mill_data = nucor_mills[selected_mill]
        card_header_class = "card-header bg-primary text-white"

    # Create info card layout
    info_card = html.Div(
        [
            html.H5(
                f"Selected: Nucor Steel {selected_mill}", className=card_header_class
            ),
            html.Div(
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
                                f"{mill_data.get('eaf_count', 'N/A')} x {mill_data.get('eaf_size', 'N/A')} ton {mill_data.get('eaf_type', 'N/A')} ({mill_data.get('eaf_manufacturer', 'N/A')})"
                            ),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Production: "),
                            html.Span(
                                f"{mill_data.get('tons_per_year', 0):,} tons/year"
                            ),
                        ],
                        className="mb-1",
                    ),
                    html.Div(
                        [
                            html.Strong("Schedule: "),
                            html.Span(
                                f"{mill_data.get('cycles_per_day', 'N/A')} cycles/day, "
                                f"{mill_data.get('days_per_year', 'N/A')} days/year, "
                                f"{mill_data.get('cycle_duration', 'N/A')} min/cycle"
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
                            html.Span(f"{mill_data.get('grid_cap', 'N/A')} MW"),
                        ],
                        className="mb-1",
                    ),
                ],
                className="card-body",
            ),
        ]
    )
    return info_card


# Callback to update Utility Provider dropdown AND rates when mill is selected
# Also updates EAF parameter inputs
@app.callback(
    [
        Output("utility-provider-dropdown", "value"),
        Output("off-peak-rate", "value"),
        Output("mid-peak-rate", "value"),
        Output("peak-rate", "value"),
        Output("demand-charge", "value"),
        Output("seasonal-rates-toggle", "value"),  # Update toggle based on utility
        # EAF Outputs
        Output("eaf-size", "value"),
        Output("eaf-count", "value"),
        Output("grid-cap", "value"),
        Output("cycles-per-day", "value"),
        Output("cycle-duration", "value"),
        Output("days-per-year", "value"),
        # Also update the TOU periods UI when mill changes
        Output("tou-periods-container", "children", allow_duplicate=True),
    ],
    Input("mill-selection-dropdown", "value"),
    prevent_initial_call=True,  # Prevent running on initial load before user selects
)
def update_params_from_mill(selected_mill):
    """Set utility provider, rates, EAF params, and TOU UI based on selected mill"""
    if not selected_mill or selected_mill not in nucor_mills:
        mill_data = nucor_mills["Custom"]
        utility_provider = "Custom Utility"
        utility_data = utility_rates.get(
            utility_provider, default_utility_params
        )  # Use default params for Custom
    else:
        mill_data = nucor_mills[selected_mill]
        utility_provider = mill_data["utility"]
        # If the mill's utility isn't in our rate database, default to Custom Utility settings
        if utility_provider not in utility_rates:
            utility_data = utility_rates["Custom Utility"]
            utility_provider = "Custom Utility"  # Reflect this in the dropdown
        else:
            utility_data = utility_rates[utility_provider]

    # Extract utility rate values safely using .get
    off_peak = utility_data.get("energy_rates", {}).get(
        "off_peak", default_utility_params["energy_rates"]["off_peak"]
    )
    mid_peak = utility_data.get("energy_rates", {}).get(
        "mid_peak", default_utility_params["energy_rates"]["mid_peak"]
    )
    peak = utility_data.get("energy_rates", {}).get(
        "peak", default_utility_params["energy_rates"]["peak"]
    )
    demand = utility_data.get("demand_charge", default_utility_params["demand_charge"])
    seasonal_enabled = (
        ["enabled"]
        if utility_data.get("seasonal_rates", default_utility_params["seasonal_rates"])
        else []
    )

    # Extract EAF values safely using .get
    eaf_size = mill_data.get("eaf_size", nucor_mills["Custom"]["eaf_size"])
    eaf_count = mill_data.get("eaf_count", nucor_mills["Custom"]["eaf_count"])
    grid_cap = mill_data.get("grid_cap", nucor_mills["Custom"]["grid_cap"])
    cycles = mill_data.get("cycles_per_day", nucor_mills["Custom"]["cycles_per_day"])
    duration = mill_data.get("cycle_duration", nucor_mills["Custom"]["cycle_duration"])
    days = mill_data.get("days_per_year", nucor_mills["Custom"]["days_per_year"])

    # Get TOU periods for the selected utility to update the UI
    tou_periods_for_ui = utility_data.get(
        "tou_periods", default_utility_params["tou_periods_raw"]
    )
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)

    return [
        utility_provider,
        off_peak,
        mid_peak,
        peak,
        demand,
        seasonal_enabled,
        eaf_size,
        eaf_count,
        grid_cap,
        cycles,
        duration,
        days,
        tou_elements_ui,  # Update the TOU input rows
    ]


# Callback to update JUST the Utility Rates inputs when provider dropdown changes MANUALLY
@app.callback(
    [
        Output("off-peak-rate", "value", allow_duplicate=True),
        Output("mid-peak-rate", "value", allow_duplicate=True),
        Output("peak-rate", "value", allow_duplicate=True),
        Output("demand-charge", "value", allow_duplicate=True),
        Output("seasonal-rates-toggle", "value", allow_duplicate=True),
        Output("tou-periods-container", "children", allow_duplicate=True),
    ],
    Input("utility-provider-dropdown", "value"),
    State(
        "mill-selection-dropdown", "value"
    ),  # Check if mill selection triggered the change
    prevent_initial_call=True,
)
def update_rates_from_provider_manual(selected_utility, selected_mill):
    """Update utility rate inputs only when the provider dropdown is changed directly."""
    ctx = callback_context
    # Only run if the utility dropdown was the trigger, NOT the mill selection
    if not ctx.triggered_id or ctx.triggered_id != "utility-provider-dropdown":
        return dash.no_update

    if not selected_utility or selected_utility not in utility_rates:
        utility_data = utility_rates[
            "Custom Utility"
        ]  # Use default custom if invalid selection
    else:
        utility_data = utility_rates[selected_utility]

    # Extract values safely
    off_peak = utility_data.get("energy_rates", {}).get(
        "off_peak", default_utility_params["energy_rates"]["off_peak"]
    )
    mid_peak = utility_data.get("energy_rates", {}).get(
        "mid_peak", default_utility_params["energy_rates"]["mid_peak"]
    )
    peak = utility_data.get("energy_rates", {}).get(
        "peak", default_utility_params["energy_rates"]["peak"]
    )
    demand = utility_data.get("demand_charge", default_utility_params["demand_charge"])
    seasonal_enabled = (
        ["enabled"]
        if utility_data.get("seasonal_rates", default_utility_params["seasonal_rates"])
        else []
    )
    tou_periods_for_ui = utility_data.get(
        "tou_periods", default_utility_params["tou_periods_raw"]
    )
    tou_elements_ui = generate_tou_ui_elements(tou_periods_for_ui)

    return off_peak, mid_peak, peak, demand, seasonal_enabled, tou_elements_ui


# Callback to show/hide and update seasonal rate inputs
@app.callback(
    [
        Output("seasonal-rates-container", "children"),
        Output("seasonal-rates-container", "style"),
    ],
    [
        Input("seasonal-rates-toggle", "value"),
        Input("utility-provider-dropdown", "value"),
    ],  # Also trigger when provider changes
    State("mill-selection-dropdown", "value"),  # Get current mill
)
def update_seasonal_rates_ui(toggle_value, selected_utility, selected_mill):
    """Show/hide seasonal rate inputs and populate with defaults for the provider."""
    ctx = callback_context
    is_enabled = toggle_value and "enabled" in toggle_value

    # Determine which utility data to use (selected provider or default custom)
    utility_data_source = default_utility_params
    if selected_utility in utility_rates:
        utility_data_source = utility_rates[selected_utility]
    elif (
        selected_mill
        and selected_mill in nucor_mills
        and nucor_mills[selected_mill]["utility"] in utility_rates
    ):
        # Fallback to mill's utility if provider is custom but mill is known
        utility_data_source = utility_rates[nucor_mills[selected_mill]["utility"]]

    # Get defaults from the determined source
    winter_mult = utility_data_source.get(
        "winter_multiplier", default_utility_params["winter_multiplier"]
    )
    summer_mult = utility_data_source.get(
        "summer_multiplier", default_utility_params["summer_multiplier"]
    )
    shoulder_mult = utility_data_source.get(
        "shoulder_multiplier", default_utility_params["shoulder_multiplier"]
    )
    winter_m = ",".join(
        map(
            str,
            utility_data_source.get(
                "winter_months", default_utility_params["winter_months"]
            ),
        )
    )
    summer_m = ",".join(
        map(
            str,
            utility_data_source.get(
                "summer_months", default_utility_params["summer_months"]
            ),
        )
    )
    shoulder_m = ",".join(
        map(
            str,
            utility_data_source.get(
                "shoulder_months", default_utility_params["shoulder_months"]
            ),
        )
    )

    if not is_enabled:
        # Return empty children and hide the container
        return [], {"display": "none"}

    # Create seasonal rate inputs UI if enabled
    seasonal_ui = html.Div(
        [
            # html.H6("Seasonal Adjustments", className="mb-2"), # Smaller heading
            html.Div(
                [  # Row for multipliers
                    html.Div(
                        [
                            html.Label(
                                "Winter Multiplier:",
                                className="form-label form-label-sm",
                            ),
                            dcc.Input(
                                id="winter-multiplier",
                                type="number",
                                value=winter_mult,
                                min=0,
                                step=0.01,
                                className="form-control form-control-sm",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Summer Multiplier:",
                                className="form-label form-label-sm",
                            ),
                            dcc.Input(
                                id="summer-multiplier",
                                type="number",
                                value=summer_mult,
                                min=0,
                                step=0.01,
                                className="form-control form-control-sm",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Shoulder Multiplier:",
                                className="form-label form-label-sm",
                            ),
                            dcc.Input(
                                id="shoulder-multiplier",
                                type="number",
                                value=shoulder_mult,
                                min=0,
                                step=0.01,
                                className="form-control form-control-sm",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                ],
                className="row mb-2",
            ),
            html.Div(
                [  # Row for month inputs
                    html.Div(
                        [
                            html.Label(
                                "Winter Months (1-12):",
                                className="form-label form-label-sm",
                            ),
                            dcc.Input(
                                id="winter-months",
                                type="text",
                                value=winter_m,
                                placeholder="e.g., 11,12,1,2",
                                className="form-control form-control-sm",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Summer Months (1-12):",
                                className="form-label form-label-sm",
                            ),
                            dcc.Input(
                                id="summer-months",
                                type="text",
                                value=summer_m,
                                placeholder="e.g., 6,7,8,9",
                                className="form-control form-control-sm",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Shoulder Months (1-12):",
                                className="form-label form-label-sm",
                            ),
                            dcc.Input(
                                id="shoulder-months",
                                type="text",
                                value=shoulder_m,
                                placeholder="e.g., 3,4,5,10",
                                className="form-control form-control-sm",
                            ),
                        ],
                        className="col-md-4 mb-2",
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
    # Return the UI elements and make the container visible
    return seasonal_ui, {"display": "block"}


# --- TOU Period UI Management ---


# Helper function to generate TOU UI elements
def generate_tou_ui_elements(tou_periods_list):
    """Generates the Div containing rows for TOU period inputs"""
    tou_elements = []
    if not tou_periods_list:  # Ensure there's at least one default row
        tou_periods_list = [(0.0, 24.0, "off_peak")]

    for i, period_data in enumerate(tou_periods_list):
        # Basic validation of period data format
        if isinstance(period_data, (list, tuple)) and len(period_data) == 3:
            start, end, rate_type = period_data
        else:
            print(
                f"Warning: Invalid format for TOU period data at index {i}: {period_data}. Using default."
            )
            start, end, rate_type = (0.0, 0.0, "off_peak")  # Default fallback

        tou_row = html.Div(
            [
                html.Div(
                    [  # Input group row
                        # Start Time Input
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
                        # End Time Input
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
                        # Rate Type Dropdown
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
                        # Remove Button
                        html.Div(
                            html.Button(
                                "×",
                                id={"type": "remove-tou", "index": i},
                                className="btn btn-danger btn-sm",
                                title="Remove Period",
                                style={"lineHeight": "1"},  # Adjust button height
                                # Disable remove button if it's the only row left
                                disabled=len(tou_periods_list) <= 1,
                            ),
                            className="col-2 d-flex align-items-center justify-content-center",
                        ),
                    ],
                    className="row g-1 mb-1 align-items-center",
                ),
            ],
            id=f"tou-row-{i}",
            className="tou-period-row",  # Add class for potential styling
        )
        tou_elements.append(tou_row)
    return tou_elements


# Callback to initialize TOU periods UI on load or when provider changes (handled by update_params_from_mill)
# This callback now focuses ONLY on adding/removing rows based on button clicks.
@app.callback(
    Output("tou-periods-container", "children", allow_duplicate=True),
    [
        Input("add-tou-period-button", "n_clicks"),
        Input({"type": "remove-tou", "index": ALL}, "n_clicks"),
    ],
    State("tou-periods-container", "children"),
    prevent_initial_call=True,
)
def modify_tou_rows(add_clicks, remove_clicks_list, current_rows):
    """Add or remove TOU period rows based on button clicks."""
    ctx = callback_context
    if not ctx.triggered_id:
        return dash.no_update

    triggered_input = ctx.triggered_id

    new_rows = current_rows[:] if current_rows else []

    if triggered_input == "add-tou-period-button":
        # Add a new row
        new_index = len(new_rows)
        # Determine default start time based on last row's end time
        default_start = 0.0
        if new_rows:
            try:
                last_row_id = new_rows[-1]["props"]["id"]  # e.g., 'tou-row-1'
                last_index = int(last_row_id.split("-")[-1])
                # Find the end input value of the last row
                # This requires accessing the State of the inputs, which is complex here.
                # Simpler approach: just add a default [0, 0, off_peak] row.
                pass  # Keep default_start = 0.0 for simplicity
            except Exception:
                pass  # Ignore errors finding last end time

        new_row_elements = generate_tou_ui_elements(
            [(default_start, 0.0, "off_peak")]
        )  # Generate UI for one row
        # Update the index in the generated element's ID
        new_row_div = new_row_elements[0]
        new_row_div.id = f"tou-row-{new_index}"  # Correct the outer Div ID
        for col in new_row_div.children[0].children:  # Iterate through columns
            if hasattr(col.children, "id") and isinstance(col.children.id, dict):
                col.children.id["index"] = (
                    new_index  # Update index in Input/Dropdown IDs
                )

        new_rows.append(new_row_div)

    elif (
        isinstance(triggered_input, dict)
        and triggered_input.get("type") == "remove-tou"
    ):
        # Remove the clicked row, but only if more than one row exists
        if len(new_rows) > 1:
            clicked_index = triggered_input["index"]
            row_to_remove_id = f"tou-row-{clicked_index}"
            new_rows = [
                row
                for row in new_rows
                if row.get("props", {}).get("id") != row_to_remove_id
            ]
        else:
            print("Cannot remove the last TOU period row.")

    # After adding or removing, re-enable/disable remove buttons correctly
    num_rows = len(new_rows)
    for i, row in enumerate(new_rows):
        try:
            # Find the button within the row structure: row -> Div -> Row -> Col -> Button
            button_col = row.children[0].children[
                -1
            ]  # Assumes button is in the last column
            button = button_col.children
            button.disabled = num_rows <= 1  # Disable if only one row remains
        except (AttributeError, IndexError):
            print(f"Warning: Could not find or update remove button state for row {i}")

    return new_rows


import dash # Make sure dash is imported
from dash import callback_context # Import callback_context

# --- Input Validation Callback ---
@app.callback(
    [Output("validation-error-container", "children"),
     Output("validation-error-container", "style"),
     Output("calculation-error-container", "style", allow_duplicate=True)],
    [Input("calculate-results-button", "n_clicks"), # Trigger on calc button
     Input("optimize-battery-button", "n_clicks"), # Trigger on optimize button
     # Keep store inputs to trigger validation when params change *after* load
     Input("utility-params-store", "data"),
     Input("eaf-params-store", "data"),
     Input("bess-params-store", "data"),
     Input("financial-params-store", "data"),
     ],
    prevent_initial_call=True,
)
def validate_inputs(calc_clicks, opt_clicks, utility_params, eaf_params, bess_params, fin_params):
    """Validate inputs before running calculations or optimization."""
    ctx = dash.callback_context # Get callback context
    triggered_id = ctx.triggered_id if ctx.triggered_id else 'initial_load_or_unknown' # Handle potential None

    # Determine if validation is triggered by a calculation attempt
    is_calc_attempt = triggered_id in ["calculate-results-button", "optimize-battery-button"]

    errors = []
    warnings = []

    # --- Validate Utility Params ---
    if not utility_params:
        errors.append("Utility parameters are missing.")
    else:
        filled_periods = utility_params.get("tou_periods_filled", [])
        raw_periods = utility_params.get("tou_periods_raw", [])

        # --- MODIFIED CHECK ---
        # Only check for empty filled_periods if triggered by button or raw is also empty
        # This prevents the error message purely from the initial empty filled list
        if not raw_periods:
             errors.append("At least one Time-of-Use period must be defined in raw periods.")
        # Check if filled_periods became empty *after* processing potentially valid raw_periods
        elif not filled_periods and raw_periods:
             # This might indicate an actual error in fill_tou_gaps or the raw data format
             errors.append("Error processing Time-of-Use periods (resulted in empty filled list despite raw periods present). Check raw period format.")
        # --- END MODIFIED CHECK ---
        elif filled_periods: # Only check coverage if filled_periods exist
             total_duration = sum(end - start for start, end, rate in filled_periods)
             if not np.isclose(total_duration, 24.0):
                 warnings.append(f"Processed Time-of-Use periods do not cover exactly 24 hours (Total: {total_duration:.1f}h). Check raw periods for overlaps/errors.")

        # Keep the detailed checks for raw_periods format errors
        for i, p in enumerate(raw_periods):
            # ... (keep the existing detailed format checks for raw_periods) ...
            if not (isinstance(p, (list,tuple)) and len(p)==3):
                errors.append(f"TOU Period #{i+1} has incorrect format.")
                continue
            start, end, rate = p
            if start is None or end is None or rate is None:
                 errors.append(f"TOU Period #{i+1} has missing values.")
            try:
                 start_f, end_f = float(start), float(end)
                 if not (0 <= start_f < end_f <= 24):
                     errors.append(f"TOU Period #{i+1} has invalid time range ({start_f}-{end_f}). Must be 0 <= start < end <= 24.")
            except (ValueError, TypeError):
                 errors.append(f"TOU Period #{i+1} has non-numeric start/end times.")
            if rate not in ["peak", "mid_peak", "off_peak"]:
                 errors.append(f"TOU Period #{i+1} has invalid rate type '{rate}'.")

        # ... (Keep the rest of the validation checks for seasonal, EAF, BESS, Financial) ...
        # Check seasonal months if enabled
        if utility_params.get("seasonal_rates"):
            w_m = utility_params.get("winter_months", [])
            s_m = utility_params.get("summer_months", [])
            h_m = utility_params.get("shoulder_months", [])
            all_months = w_m + s_m + h_m
            if len(all_months) != len(set(all_months)):
                errors.append("Seasonal Months Error: Some months appear in multiple seasons.")
            if not all(m in all_months for m in range(1, 13)):
                errors.append("Seasonal Months Error: Not all months (1-12) are assigned to a season.")
            if not all(isinstance(m, int) and 1 <= m <= 12 for m in all_months):
                 errors.append("Seasonal Months Error: Month lists contain invalid values.")

    # --- Validate EAF Params ---
    # ... (keep EAF checks) ...
    if not eaf_params: errors.append("EAF parameters are missing.")
    else:
        if eaf_params.get('eaf_size', 0) <= 0: errors.append("EAF Size must be positive.")
        if eaf_params.get('cycle_duration_input', 0) <= 0: errors.append("Cycle Duration must be positive.")
        if eaf_params.get('cycles_per_day', 0) <= 0: errors.append("Cycles per Day must be positive.")
        if not (0 < eaf_params.get('days_per_year', 0) <= 366): errors.append("Operating Days must be between 1 and 366.")


    # --- Validate BESS Params ---
    # ... (keep BESS checks) ...
    if not bess_params: errors.append("BESS parameters are missing.")
    else:
        cap = bess_params.get('capacity', 0)
        power = bess_params.get('power_max', 0)
        if cap <= 0: errors.append("BESS Capacity (MWh) must be positive.")
        if power <= 0: errors.append("BESS Power (MW) must be positive.")
        if cap > 0 and power > 0:
            c_rate = power / cap
            if not (0.1 <= c_rate <= 5): # Wider warning range for C-rate
                warnings.append(f"BESS C-Rate ({c_rate:.1f}) is unusual (Power {power} MW / Capacity {cap} MWh). Typical range is 0.25-2.0.")
        if not (0 < bess_params.get('rte', 0) <= 1): errors.append("BESS RTE must be between 0% and 100%.") # Check percentage input logic if RTE is stored 0-1
        if bess_params.get('cycle_life', 0) <= 0: errors.append("BESS Cycle Life must be positive.")
        if bess_params.get('cost_per_kwh', 0) <= 0: errors.append("BESS Cost ($/kWh) must be positive.")
        if bess_params.get('om_cost_per_kwh_year', 0) < 0: errors.append("BESS O&M Cost cannot be negative.")


    # --- Validate Financial Params ---
    # ... (keep Financial checks - excluding interest/debt) ...
    if not fin_params: errors.append("Financial parameters are missing.")
    else:
        # Check WACC is 0-100% range (internal value 0-1)
        if not (0 <= fin_params.get('wacc', -1) < 1): errors.append("WACC must be between 0% and 100%.")
        if fin_params.get('project_lifespan', 0) <= 0: errors.append("Project Lifespan must be positive.")
        # Check Tax Rate is 0-100% range (internal value 0-1)
        if not (0 <= fin_params.get('tax_rate', -1) < 1): errors.append("Tax Rate must be between 0% and 100%.")
        # Check Inflation Rate is plausible (internal value -0.1 to 1)
        if not (-0.1 <= fin_params.get('inflation_rate', -1) <= 1): errors.append("Inflation Rate seems unusual (typical range -10% to 100%).")
        # Check Salvage Value is 0-100% range (internal value 0-1)
        if not (0 <= fin_params.get('salvage_value', -1) <= 1): errors.append("Salvage Value must be between 0% and 100%.")


    # --- Determine Output ---
    output_elements = []
    display_style = {"display": "none", "max-width": "800px", "margin": "10px auto"}
    calc_error_style = {"display": "none"}

    if errors:
        output_elements.append(html.H5("Validation Errors:", className="mb-2 text-danger"))
        output_elements.append(html.Ul([html.Li(e) for e in errors]))
        display_style["display"] = "block"
        display_style["border-color"] = "#f5c6cb"
        display_style["background-color"] = "#f8d7da"
        display_style["color"] = "#721c24"
        if is_calc_attempt: calc_error_style = {"display": "none"}
    elif warnings:
        # Only show warnings if triggered by user action, not initial load/store changes
        # Or always show warnings if desired. Let's show them always for now.
        output_elements.append(html.H5("Validation Warnings:", className="mb-2 text-warning"))
        output_elements.append(html.Ul([html.Li(w) for w in warnings]))
        display_style["display"] = "block"
        display_style["border-color"] = "#ffeeba"
        display_style["background-color"] = "#fff3cd"
        display_style["color"] = "#856404"

    return output_elements, display_style, calc_error_style


# --- Main Calculation Callback ---
@app.callback(
    [
        Output("results-output-container", "children"),
        Output("calculation-results-store", "data"),  # Store results
        Output(
            "calculation-error-container", "children"
        ),  # Display calculation errors separately
        Output("calculation-error-container", "style"),
    ],
    Input("calculate-results-button", "n_clicks"),
    [
        State("eaf-params-store", "data"),
        State("bess-params-store", "data"),
        State("utility-params-store", "data"),
        State("financial-params-store", "data"),
        State("incentive-params-store", "data"),
        State("validation-error-container", "children"),
    ],  # Check if validation errors exist
    prevent_initial_call=True,
)
def display_calculation_results(
    n_clicks,
    eaf_params,
    bess_params,
    utility_params,
    financial_params,
    incentive_params,
    validation_errors,
):
    """Perform calculations and display results in the Results tab."""

    # Default outputs
    results_output = html.Div(
        "Click 'Calculate Results' to generate the analysis.",
        className="text-center text-muted",
    )
    stored_data = {}
    error_output = ""
    error_style = {"display": "none", "max-width": "800px", "margin": "10px auto"}

    if n_clicks == 0:
        return results_output, stored_data, error_output, error_style

    # --- Check for Validation Errors ---
    # Assumes validation_errors list is non-empty if errors exist
    if validation_errors:
        error_output = html.Div(
            [
                html.H5(
                    "Cannot Calculate - Validation Errors Exist",
                    className="text-danger",
                ),
                html.P("Please fix the errors listed above before calculating."),
                # Optionally re-display validation errors here if needed
                # validation_errors
            ]
        )
        error_style["display"] = "block"
        error_style["border-color"] = "#f5c6cb"
        error_style["background-color"] = "#f8d7da"
        error_style["color"] = "#721c24"
        # Return current placeholder for results, no stored data, and the error message
        return results_output, stored_data, error_output, error_style

    # --- Proceed with Calculations ---
    try:
        # Ensure essential parameter dicts exist
        if not all(
            [
                eaf_params,
                bess_params,
                utility_params,
                financial_params,
                incentive_params,
            ]
        ):
            raise ValueError(
                "One or more parameter sets (EAF, BESS, Utility, Financial, Incentive) are missing."
            )

        # --- Core Calculations ---
        # Pass eaf_params to financial metrics for days/cycles per year
        billing_results = calculate_annual_billings(
            eaf_params, bess_params, utility_params
        )
        incentive_results = calculate_incentives(bess_params, incentive_params)
        financial_metrics = calculate_financial_metrics(
            bess_params,
            financial_params,
            eaf_params,
            billing_results["annual_savings"],
            incentive_results,
        )

        # Store results for potential use elsewhere (e.g., reports)
        stored_data = {
            "billing": billing_results,
            "incentives": incentive_results,
            "financials": financial_metrics,
            "inputs": {  # Store key inputs used for this calculation
                "eaf": eaf_params,
                "bess": bess_params,
                "utility": utility_params,
                "financial": financial_params,
                "incentive": incentive_params,
            },
        }
        # --- Add this block inside display_calculation_results ---
        # --- Single Cycle Profile Calculation for Plot ---
        try:
            # Use the actual cycle duration input by the user for the time axis
            plot_cycle_duration_min = eaf_params.get("cycle_duration_input", 36)
            if plot_cycle_duration_min <= 0: plot_cycle_duration_min = 36 # Fallback

            # Define time axis for the plot
            time_plot = np.linspace(0, plot_cycle_duration_min, 200) # 200 points over the cycle duration

            # Calculate EAF profile for the plot
            eaf_power_plot = calculate_eaf_profile(
                time_plot,
                eaf_params.get("eaf_size", 100),
                plot_cycle_duration_min # Pass actual duration
            )

            # Calculate Grid/BESS contribution for the plot
            grid_power_plot, bess_power_plot = calculate_grid_bess_power(
                eaf_power_plot,
                eaf_params.get("grid_cap", 35),
                bess_params.get("power_max", 20)
            )
            plot_data_calculated = True
            max_y_plot = max(np.max(eaf_power_plot) if len(eaf_power_plot)>0 else 0, eaf_params.get("grid_cap", 35)) * 1.15
            if max_y_plot <=0: max_y_plot = 60 # Ensure positive range

        except Exception as plot_err:
            plot_data_calculated = False
            plot_error_message = f"Error generating single cycle plot data: {plot_err}"
            print(plot_error_message) # Log error
            # Initialize empty arrays or handle error in plot generation below
            time_plot, eaf_power_plot, grid_power_plot, bess_power_plot = [], [], [], []
            max_y_plot = 60
        # --- End of added block ---

        # --- Format Results for Display ---
        # (Your existing code for cards, tables, cash flow graph follows)
        # ...
        
        # --- Format Results for Display ---

        # Helper to format currency
        def format_currency(value):
            if pd.isna(value):
                return "N/A"
            return f"${value:,.0f}"  # No decimals for large numbers

        def format_percent(value):
            if pd.isna(value) or not isinstance(value, (int, float)):
                return "N/A"
            # Handle IRR very large/small values
            if abs(value) > 5:  # If IRR > 500% or < -500%, display as >500% or <-500%
                return f"{'+' if value > 0 else ''}>500%" if value > 0 else "<-500%"
            return f"{value:.1%}"  # One decimal place

        def format_years(value):
            if pd.isna(value) or value == float("inf"):
                return "Never"
            if value < 0:
                return "< 0 (Immediate)"  # Payback < 0 means initial profit
            return f"{value:.1f} yrs"

        # --- Create Output Components ---

        # Financial Summary Card
        metrics_card = html.Div(
            [
                html.H5("Financial Summary", className="card-header"),
                html.Div(
                    [
                        html.Table(
                            [
                                html.Tr(
                                    [
                                        html.Td("Net Present Value (NPV)"),
                                        html.Td(
                                            format_currency(financial_metrics["npv"])
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Internal Rate of Return (IRR)"),
                                        html.Td(
                                            format_percent(financial_metrics["irr"])
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Simple Payback Period"),
                                        html.Td(
                                            format_years(
                                                financial_metrics["payback_years"]
                                            )
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Est. Battery Life (Cycles)"),
                                        html.Td(
                                            format_years(
                                                financial_metrics["battery_life_years"]
                                            )
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Net Initial Cost"),
                                        html.Td(
                                            format_currency(
                                                financial_metrics["net_initial_cost"]
                                            )
                                        ),
                                    ]
                                ),
                            ],
                            className="table table-sm",
                        )
                    ],
                    className="card-body",
                ),
            ],
            className="card mb-3",
        )

        # Annual Billing Card
        savings_card = html.Div(
            [
                html.H5("Annual Billing", className="card-header"),
                html.Div(
                    [
                        html.Table(
                            [
                                html.Tr(
                                    [
                                        html.Td("Baseline Bill (No BESS)"),
                                        html.Td(
                                            format_currency(
                                                billing_results[
                                                    "annual_bill_without_bess"
                                                ]
                                            )
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Projected Bill (With BESS)"),
                                        html.Td(
                                            format_currency(
                                                billing_results["annual_bill_with_bess"]
                                            )
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td(html.Strong("Annual Savings")),
                                        html.Td(
                                            html.Strong(
                                                format_currency(
                                                    billing_results["annual_savings"]
                                                )
                                            )
                                        ),
                                    ]
                                ),
                            ],
                            className="table table-sm",
                        )
                    ],
                    className="card-body",
                ),
            ],
            className="card mb-3",
        )

        # Incentives Card
        inc_items = [
            html.Tr([html.Td(desc), html.Td(format_currency(amount))])
            for desc, amount in incentive_results["breakdown"].items()
        ]
        inc_items.append(
            html.Tr(
                [
                    html.Td(html.Strong("Total Incentives")),
                    html.Td(
                        html.Strong(
                            format_currency(incentive_results["total_incentive"])
                        )
                    ),
                ]
            )
        )
        incentives_card = html.Div(
            [
                html.H5("Incentives Applied", className="card-header"),
                html.Div(
                    [html.Table(inc_items, className="table table-sm")],
                    className="card-body",
                ),
            ],
            className="card mb-3",
        )

        # Monthly Breakdown Table
        months = [calendar.month_abbr[i] for i in range(1, 13)]
        df_monthly = pd.DataFrame(
            {
                "Month": months,
                "Bill Without BESS": [
                    b["total_bill"]
                    for b in billing_results["monthly_bills_without_bess"]
                ],
                "Bill With BESS": [
                    b["total_bill"] for b in billing_results["monthly_bills_with_bess"]
                ],
                "Savings": billing_results["monthly_savings"],
                "Peak Demand w/o BESS (kW)": [
                    b["peak_demand_kw"]
                    for b in billing_results["monthly_bills_without_bess"]
                ],
                "Peak Demand w/ BESS (kW)": [
                    b["peak_demand_kw"]
                    for b in billing_results["monthly_bills_with_bess"]
                ],
            }
        )
        # Format currency columns only
        for col in ["Bill Without BESS", "Bill With BESS", "Savings"]:
            df_monthly[col] = df_monthly[col].apply(format_currency)
        for col in ["Peak Demand w/o BESS (kW)", "Peak Demand w/ BESS (kW)"]:
            df_monthly[col] = df_monthly[col].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
            )

        monthly_table = dash_table.DataTable(
            data=df_monthly.to_dict("records"),
            columns=[{"name": i, "id": i} for i in df_monthly.columns],
            style_cell={"textAlign": "right", "padding": "5px"},
            style_header={"fontWeight": "bold", "textAlign": "center"},
            style_data={"border": "1px solid grey"},
            style_table={
                "overflowX": "auto",
                "minWidth": "100%",
            },  # Ensure responsiveness
            style_cell_conditional=[
                {"if": {"column_id": "Month"}, "textAlign": "left"}
            ],
        )

        # Cash Flow Graph
        years = list(range(financial_params["project_lifespan"] + 1))
        cash_flows_data = financial_metrics.get("cash_flows", [])
        # Ensure cash_flows_data has the correct length
        if len(cash_flows_data) != len(years):
            print(
                f"Warning: Cash flow data length ({len(cash_flows_data)}) doesn't match project lifespan + 1 ({len(years)}). Graph might be incorrect."
            )
            # Pad or truncate cash_flows_data if necessary, or show error
            cash_flows_data = cash_flows_data[: len(years)] + [0] * (
                len(years) - len(cash_flows_data)
            )  # Simple padding

        fig_cashflow = go.Figure()
        fig_cashflow.add_trace(
            go.Bar(
                x=years,
                y=cash_flows_data,
                name="After-Tax Cash Flow",
                marker_color=[
                    "red" if cf < 0 else "green" for cf in cash_flows_data
                ],  # Color bars
            )
        )
        fig_cashflow.update_layout(
            title="Project After-Tax Cash Flows",
            xaxis_title="Year",
            yaxis_title="Cash Flow ($)",
            yaxis_tickformat="$,.0f",  # Format y-axis ticks as currency
            plot_bgcolor="white",
            margin=dict(l=40, r=20, t=40, b=30),  # Adjust margins
        )
        # --- Add this block for generating the Single Cycle Plot ---
        fig_single_cycle = go.Figure()

        if plot_data_calculated:
            fig_single_cycle.add_trace(go.Scatter(
                x=time_plot, y=eaf_power_plot, mode='lines', name='EAF Power Demand',
                line=dict(color='blue', width=2)
            ))
            fig_single_cycle.add_trace(go.Scatter(
                x=time_plot, y=grid_power_plot, mode='lines', name='Grid Power Supply',
                line=dict(color='green', width=2)
            ))
            fig_single_cycle.add_trace(go.Scatter(
                x=time_plot, y=bess_power_plot, mode='lines', name='BESS Power Output',
                line=dict(color='red', width=2), fill='tozeroy' # Fill BESS area
            ))
            # Add Grid Cap line
            fig_single_cycle.add_shape(
                type="line", x0=0, y0=eaf_params.get("grid_cap", 35),
                x1=plot_cycle_duration_min, y1=eaf_params.get("grid_cap", 35),
                line=dict(color='black', width=2, dash='dash'), name='Grid Cap'
            )
            # Add annotation for Grid Cap
            fig_single_cycle.add_annotation(
                x=plot_cycle_duration_min * 0.9, # Position near the end
                y=eaf_params.get("grid_cap", 35) + max_y_plot * 0.03, # Slightly above the line
                text=f"Grid Cap ({eaf_params.get('grid_cap', 35)} MW)",
                showarrow=False, font=dict(color='black', size=10)
            )
        else:
            # Display an error message on the plot if data failed
             fig_single_cycle.update_layout(
                  xaxis = {'visible': False}, yaxis = {'visible': False},
                  annotations = [{'text': 'Error generating plot data', 'xref': 'paper', 'yref': 'paper', 'showarrow': False, 'font': {'size': 16}}]
             )


        fig_single_cycle.update_layout(
            title=f'Simulated EAF Cycle Profile ({eaf_params.get("eaf_size", "N/A")}-ton)',
            xaxis_title=f"Time in Cycle (minutes, Duration: {plot_cycle_duration_min:.1f} min)",
            yaxis_title="Power (MW)",
            yaxis_range=[0, max_y_plot],
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_white",
            margin=dict(l=40, r=20, t=50, b=40)
        )
        # --- End of added block ---
        
        # Assemble the results layout
        results_output = html.Div(
            [
                html.H3("Calculation Results", className="mb-4"),
                html.Div(
                    [  # Row for summary cards
                        html.Div(metrics_card, className="col-lg-4 col-md-6"),
                        html.Div(savings_card, className="col-lg-4 col-md-6"),
                        html.Div(
                            incentives_card, className="col-lg-4 col-md-12"
                        ),  # Takes full width on medium down
                    ],
                    className="row mb-4",
                ),
                html.H4("Monthly Billing Breakdown", className="mb-3"),
                monthly_table,
                
                 # --- Add the Single Cycle Graph Here ---
                html.H4("Single Cycle Power Profile", className="mt-4 mb-3"),
                dcc.Graph(figure=fig_single_cycle),
                
                html.H4("Cash Flow Analysis", className="mt-4 mb-3"),
                dcc.Graph(figure=fig_cashflow),
            ]
        )

        # Clear any previous calculation errors
        error_output = ""
        error_style = {"display": "none"}

    except Exception as e:
        # Display specific errors to help debugging
        tb_str = traceback.format_exc()
        error_output = html.Div(
            [
                html.H5("Calculation Error", className="text-danger"),
                html.P("An error occurred during calculation:"),
                html.Pre(f"{type(e).__name__}: {str(e)}"),
                html.Details(
                    [  # Collapsible traceback
                        html.Summary("Click for technical details (Traceback)"),
                        html.Pre(tb_str),
                    ]
                ),
            ],
            className="alert alert-danger",
        )
        error_style["display"] = "block"
        # Keep results area empty or show placeholder
        results_output = html.Div(
            "Could not generate results due to an error.",
            className="text-center text-danger",
        )
        stored_data = {}  # Do not store partial/error results

    return results_output, stored_data, error_output, error_style


# --- Optimization Callback ---
@app.callback(
    [
        Output("optimization-output-container", "children"),
        Output("optimization-results-store", "data"),
    ],
    Input("optimize-battery-button", "n_clicks"),
    [
        State("eaf-params-store", "data"),
        State("bess-params-store", "data"),  # Base BESS params (cost, life, etc.)
        State("utility-params-store", "data"),
        State("financial-params-store", "data"),
        State("incentive-params-store", "data"),
        State("validation-error-container", "children"),
    ],  # Check validation
    prevent_initial_call=True,
)
def display_optimization_results(
    n_clicks,
    eaf_params,
    bess_base_params,
    utility_params,
    financial_params,
    incentive_params,
    validation_errors,
):
    """Run battery size optimization and display results."""

    opt_output = html.Div(
        "Click 'Optimize Battery Size' to run the analysis.",
        className="text-center text-muted",
    )
    opt_stored_data = {}

    if n_clicks == 0:
        return opt_output, opt_stored_data

    # --- Check for Validation Errors ---
    if validation_errors:
        opt_output = html.Div(
            [
                html.H4(
                    "Cannot Optimize - Validation Errors Exist", className="text-danger"
                ),
                html.P(
                    "Please fix the errors listed in the Parameters/Incentives tabs before optimizing."
                ),
            ],
            className="alert alert-danger",
        )
        return opt_output, opt_stored_data

    # --- Proceed with Optimization ---
    try:
        if not all(
            [
                eaf_params,
                bess_base_params,
                utility_params,
                financial_params,
                incentive_params,
            ]
        ):
            raise ValueError("One or more parameter sets are missing for optimization.")

        print("Starting Optimization Callback...")  # Log start

        # Run the optimization function
        opt_results = optimize_battery_size(
            eaf_params,
            utility_params,
            financial_params,
            incentive_params,
            bess_base_params,
        )
        opt_stored_data = opt_results  # Store the full optimization results

        print("Optimization Function Finished.")  # Log end

        # --- Format Optimization Results ---
        if opt_results and opt_results.get("best_capacity") is not None:
            best_metrics = opt_results.get(
                "best_metrics", {}
            )  # Metrics for the best size

            # Helper to format currency
            def format_currency(value):
                if pd.isna(value):
                    return "N/A"
                return f"${value:,.0f}"

            def format_percent(value):
                if pd.isna(value) or not isinstance(value, (int, float)):
                    return "N/A"
                if abs(value) > 5:
                    return f"{'+' if value > 0 else ''}>500%" if value > 0 else "<-500%"
                return f"{value:.1%}"

            def format_years(value):
                if pd.isna(value) or value == float("inf"):
                    return "Never"
                if value < 0:
                    return "< 0 yrs"
                return f"{value:.1f} yrs"

            # Summary Card for Best Result
            best_summary = html.Div(
                [
                    html.H4("Optimal Size Found (Max NPV)", className="card-header"),
                    html.Div(
                        html.Table(
                            [
                                html.Tr(
                                    [
                                        html.Td("Capacity (MWh)"),
                                        html.Td(f"{opt_results['best_capacity']:.1f}"),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Power (MW)"),
                                        html.Td(f"{opt_results['best_power']:.1f}"),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting NPV"),
                                        html.Td(
                                            format_currency(opt_results["best_npv"])
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting IRR"),
                                        html.Td(
                                            format_percent(best_metrics.get("irr"))
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Resulting Payback"),
                                        html.Td(
                                            format_years(
                                                best_metrics.get("payback_years")
                                            )
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Annual Savings (Year 1)"),
                                        html.Td(
                                            format_currency(
                                                best_metrics.get("annual_savings_year1")
                                            )
                                        ),
                                    ]
                                ),
                                html.Tr(
                                    [
                                        html.Td("Net Initial Cost"),
                                        html.Td(
                                            format_currency(
                                                best_metrics.get("net_initial_cost")
                                            )
                                        ),
                                    ]
                                ),
                            ],
                            className="table table-sm",
                        ),
                        className="card-body",
                    ),
                ],
                className="card mb-4",
            )

            # Table of all tested results (optional, can be large)
            # Consider filtering or summarizing if too many points
            all_results_df = pd.DataFrame(opt_results.get("all_results", []))
            # Select and rename columns for display
            if not all_results_df.empty:
                display_cols = {
                    "capacity": "Capacity (MWh)",
                    "power": "Power (MW)",
                    "npv": "NPV ($)",
                    "irr": "IRR (%)",
                    "payback_years": "Payback (Yrs)",
                    "annual_savings": "Savings ($/Yr)",
                    "net_initial_cost": "Net Cost ($)",
                }
                all_results_df = all_results_df[list(display_cols.keys())].copy()
                all_results_df.rename(columns=display_cols, inplace=True)

                # Format the table data
                all_results_df["Capacity (MWh)"] = all_results_df["Capacity (MWh)"].map(
                    "{:.1f}".format
                )
                all_results_df["Power (MW)"] = all_results_df["Power (MW)"].map(
                    "{:.1f}".format
                )
                all_results_df["NPV ($)"] = all_results_df["NPV ($)"].apply(
                    format_currency
                )
                all_results_df["IRR (%)"] = all_results_df["IRR (%)"].apply(
                    format_percent
                )
                all_results_df["Payback (Yrs)"] = all_results_df["Payback (Yrs)"].apply(
                    format_years
                )
                all_results_df["Savings ($/Yr)"] = all_results_df[
                    "Savings ($/Yr)"
                ].apply(format_currency)
                all_results_df["Net Cost ($)"] = all_results_df["Net Cost ($)"].apply(
                    format_currency
                )

                all_results_table = dash_table.DataTable(
                    data=all_results_df.to_dict("records"),
                    columns=[{"name": i, "id": i} for i in all_results_df.columns],
                    page_size=10,  # Paginate
                    sort_action="native",
                    filter_action="native",
                    style_cell={"textAlign": "right"},
                    style_header={"fontWeight": "bold"},
                    style_table={"overflowX": "auto", "minWidth": "100%"},
                    style_cell_conditional=[
                        {"if": {"column_id": "Capacity (MWh)"}, "textAlign": "left"},
                        {"if": {"column_id": "Power (MW)"}, "textAlign": "left"},
                    ],
                )
                table_section = html.Div(
                    [
                        html.H4("All Tested Combinations", className="mt-4 mb-3"),
                        all_results_table,
                    ]
                )
            else:
                table_section = html.P(
                    "No optimization results data to display in table."
                )

            # Assemble final output
            opt_output = html.Div(
                [
                    html.H3("Battery Sizing Optimization Results", className="mb-4"),
                    best_summary,
                    table_section,
                ]
            )

        else:
            # Handle case where optimization failed or found no valid results
            opt_output = html.Div(
                [
                    html.H4("Optimization Failed", className="text-warning"),
                    html.P(
                        "Could not find an optimal battery size with the given parameters. Reasons might include:"
                    ),
                    html.Ul(
                        [
                            html.Li(
                                "No combinations resulted in a positive NPV or reasonable payback."
                            ),
                            html.Li(
                                "Errors occurred during the simulation for all tested sizes."
                            ),
                            html.Li(
                                "Parameter ranges for optimization might need adjustment."
                            ),
                        ]
                    ),
                    html.P(
                        f"Details: {opt_results.get('error', 'No specific error message.')}"
                        if opt_results
                        else "No results data."
                    ),
                ],
                className="alert alert-warning",
            )

    except Exception as e:
        # Display specific errors
        tb_str = traceback.format_exc()
        opt_output = html.Div(
            [
                html.H5("Optimization Error", className="text-danger"),
                html.P("An error occurred during the optimization process:"),
                html.Pre(f"{type(e).__name__}: {str(e)}"),
                html.Details(
                    [
                        html.Summary("Click for technical details (Traceback)"),
                        html.Pre(tb_str),
                    ]
                ),
            ],
            className="alert alert-danger",
        )
        opt_stored_data = {}  # Clear stored data on error

    return opt_output, opt_stored_data


# --- Run the App ---
if __name__ == "__main__":
    # Use debug=False for production/stable deployment
    # Use debug=True for development to see errors and enable hot-reloading
    app.run_server(host="0.0.0.0", port=8050, debug=False)
