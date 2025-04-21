import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import json
from datetime import datetime
import calendar

# Improved numpy_financial fallback
try:
    import numpy_financial as npf
except ImportError:
    print(
        "numpy_financial package is required. Please install it with: pip install numpy-financial"
    )

    # Better fallback implementation
    class DummyNPF:
        def npv(self, rate, values):
            print(
                "WARNING: Using simplified NPV calculation. Install numpy-financial for accurate results."
            )
            return sum(values[i] / (1 + rate) ** i for i in range(len(values)))

        def irr(self, values):
            print(
                "WARNING: IRR calculation requires numpy-financial. Install with: pip install numpy-financial"
            )
            # Try a basic iterative approach for IRR if numpy-financial is missing
            if values[0] >= 0:  # IRR can't be calculated if first value is positive
                return float("nan")

            # Simple bisection method
            r_low, r_high = -0.99, 1.0
            for _ in range(100):  # Max 100 iterations
                r_mid = (r_low + r_high) / 2
                npv_mid = sum(values[i] / (1 + r_mid) ** i for i in range(len(values)))
                if abs(npv_mid) < 1:  # Convergence threshold
                    return r_mid
                if npv_mid > 0:
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

app.title = "EAF-BESS Peak Shaving Dashboard V4 (Nucor Facilities)"
# --- Default Parameters ---
# These will be used as fallbacks and for the custom option

# Default utility parameters
default_utility_params = {
    "energy_rates": {"off_peak": 50, "mid_peak": 100, "peak": 150},  # $/MWh
    "demand_charge": 10,  # $/kW/month
    "tou_periods": [
        (0, 8, "off_peak"),
        (8, 10, "peak"),
        (10, 16, "mid_peak"),
        (16, 20, "peak"),
        (20, 24, "off_peak"),
    ],
    # Adding seasonal parameters
    "seasonal_rates": False,  # Toggles seasonal rate differences
    "winter_months": [11, 12, 1, 2, 3],  # Nov-Mar
    "summer_months": [6, 7, 8, 9],  # Jun-Sep
    "shoulder_months": [4, 5, 10],  # Apr-May, Oct
    "winter_multiplier": 1.0,  # No change for winter
    "summer_multiplier": 1.2,  # 20% higher in summer
    "shoulder_multiplier": 1.1,  # 10% higher in shoulder seasons
}

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
default_financial_params = {
    "wacc": 0.06,  # 6% Weighted Average Cost of Capital
    "interest_rate": 0.04,  # 4% Interest rate for debt
    "debt_fraction": 0.5,  # 50% of BESS cost financed
    "project_lifespan": 10,  # 10 years
    "tax_rate": 0.25,  # 25% tax rate
    "inflation_rate": 0.02,  # 2% inflation
    "salvage_value": 0.1,  # 10% of BESS cost at end
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
# This dataset includes all the Nucor mills with their EAF specifications
# Source: Uploaded PDF document

nucor_mills = {
    "West Virginia": {
        "location": "Apple Grove, WV",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "DC",
        "eaf_manufacturer": "SMS",
        "eaf_size": 190,  # tons
        "cycles_per_day": 26,
        "tons_per_year": 3000000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Appalachian Power",
        "grid_cap": 50,  # Estimated MW
    },
    "Auburn": {
        "location": "Auburn, NY",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Unknown",
        "eaf_size": 60,  # tons
        "cycles_per_day": 28,
        "tons_per_year": 510000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "New York State Electric & Gas",
        "grid_cap": 25,  # Estimated MW
    },
    "Birmingham": {
        "location": "Birmingham, AL",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Unknown",
        "eaf_size": 52,  # tons
        "cycles_per_day": 20,
        "tons_per_year": 310000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Alabama Power",
        "grid_cap": 20,  # Estimated MW
    },
    "Arkansas": {
        "location": "Blytheville, AR",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "Demag",
        "eaf_size": 150,  # tons
        "cycles_per_day": 28,
        "tons_per_year": 2500000,
        "days_per_year": 300,
        "cycle_duration": 38,  # minutes
        "utility": "Entergy Arkansas",
        "grid_cap": 45,  # Estimated MW
    },
    "Kankakee": {
        "location": "Bourbonnais, IL",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Danieli",
        "eaf_size": 73,  # tons
        "cycles_per_day": 39,
        "tons_per_year": 850000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "ComEd",
        "grid_cap": 30,  # Estimated MW
    },
    "Brandenburg": {
        "location": "Brandenburg, KY",
        "type": "Sheet",
        "eaf_count": 1,
        "eaf_type": "DC",
        "eaf_manufacturer": "Danieli",
        "eaf_size": 150,  # tons
        "cycles_per_day": 27,
        "tons_per_year": 1200000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "LG&E KU",
        "grid_cap": 45,  # Estimated MW
    },
    "Hertford": {
        "location": "Cofield, NC",
        "type": "Plate",
        "eaf_count": 1,
        "eaf_type": "DC",
        "eaf_manufacturer": "MAN GHH",
        "eaf_size": 150,  # tons
        "cycles_per_day": 30,
        "tons_per_year": 1350000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Dominion Energy",
        "grid_cap": 45,  # Estimated MW
    },
    "Indiana": {
        "location": "Crawfordsville, IN",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "AC",
        "eaf_manufacturer": "Brown-Boveri",
        "eaf_size": 118,  # tons
        "cycles_per_day": 27,
        "tons_per_year": 1890000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Duke Energy",
        "grid_cap": 40,  # Estimated MW
    },
    "South Carolina": {
        "location": "Darlington, SC",
        "type": "Bar",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "MAN GHH",
        "eaf_size": 110,  # tons
        "cycles_per_day": 30,
        "tons_per_year": 980000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Duke Energy",
        "grid_cap": 40,  # Estimated MW
    },
    "Decatur": {
        "location": "Decatur, AL",
        "type": "Sheet",
        "eaf_count": 2,
        "eaf_type": "DC",
        "eaf_manufacturer": "NKK-SE",
        "eaf_size": 165,  # tons
        "cycles_per_day": 20,
        "tons_per_year": 2000000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Alabama Power",
        "grid_cap": 48,  # Estimated MW
    },
    "Custom": {
        "location": "Custom Location",
        "type": "Custom",
        "eaf_count": 1,
        "eaf_type": "AC",
        "eaf_manufacturer": "Custom",
        "eaf_size": 100,  # tons
        "cycles_per_day": 24,
        "tons_per_year": 1000000,
        "days_per_year": 300,
        "cycle_duration": 36,  # minutes
        "utility": "Custom Utility",
        "grid_cap": 35,  # MW
    },
}

# --- Utility Rate Data ---
# This is a simplified representation of utility rate structures
# In a real implementation, this would be much more detailed with actual rates

utility_rates = {
    "Appalachian Power": {
        "energy_rates": {"off_peak": 45, "mid_peak": 90, "peak": 135},  # $/MWh
        "demand_charge": 12,  # $/kW/month
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
        "energy_rates": {"off_peak": 60, "mid_peak": 110, "peak": 180},  # $/MWh
        "demand_charge": 15,  # $/kW/month
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
        "energy_rates": {"off_peak": 40, "mid_peak": 80, "peak": 120},  # $/MWh
        "demand_charge": 10,  # $/kW/month
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
        "energy_rates": {"off_peak": 42, "mid_peak": 85, "peak": 130},  # $/MWh
        "demand_charge": 11,  # $/kW/month
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
        "energy_rates": {"off_peak": 48, "mid_peak": 95, "peak": 140},  # $/MWh
        "demand_charge": 13,  # $/kW/month
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
        "energy_rates": {"off_peak": 44, "mid_peak": 88, "peak": 125},  # $/MWh
        "demand_charge": 12.5,  # $/kW/month
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
        "energy_rates": {"off_peak": 47, "mid_peak": 94, "peak": 138},  # $/MWh
        "demand_charge": 13.5,  # $/kW/month
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
        "energy_rates": {"off_peak": 46, "mid_peak": 92, "peak": 135},  # $/MWh
        "demand_charge": 14,  # $/kW/month
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
    "Custom Utility": default_utility_params,
}
# --- Helper Functions ---

def fill_tou_gaps(periods):
    """Fill gaps in TOU periods with off-peak rates"""
    # Sort periods by start time
    sorted_periods = sorted(periods)
    filled_periods = []
    
    # Add period from 0 to first start if needed
    if sorted_periods and sorted_periods[0][0] > 0:
        filled_periods.append((0, sorted_periods[0][0], "off_peak"))
    
    # Add all existing periods
    filled_periods.extend(sorted_periods)
    
    # Fill gaps between periods
    i = 0
    while i < len(filled_periods) - 1:
        if filled_periods[i][1] < filled_periods[i + 1][0]:
            filled_periods.insert(i + 1, (filled_periods[i][1], filled_periods[i + 1][0], "off_peak"))
            # Skip the newly inserted period in the next iteration
            i += 1
        i += 1
    
    # Add period from last end to 24 if needed
    if filled_periods and filled_periods[-1][1] < 24:
        filled_periods.append((filled_periods[-1][1], 24, "off_peak"))
    
    # Handle the case where no periods were provided
    if not filled_periods:
        filled_periods.append((0, 24, "off_peak"))
        
    return filled_periods
def get_month_season_multiplier(month, seasonal_data):
    """Determine the rate multiplier based on the month and seasonal configuration"""
    if not seasonal_data["seasonal_rates"]:
        return 1.0

    if month in seasonal_data["winter_months"]:
        return seasonal_data["winter_multiplier"]
    elif month in seasonal_data["summer_months"]:
        return seasonal_data["summer_multiplier"]
    elif month in seasonal_data["shoulder_months"]:
        return seasonal_data["shoulder_multiplier"]
    else:
        return 1.0  # Default multiplier if month doesn't fit in defined seasons


# Improved EAF profile calculation to respect cycle duration
def calculate_eaf_profile(time_minutes, eaf_size=100, cycle_duration=36):
    """Calculate EAF power profile for a given time array (in minutes) and EAF size in tons"""
    eaf_power = np.zeros_like(time_minutes)
    # Scale factor based on EAF size (assuming power scales roughly with EAF size^0.6)
    scale = (eaf_size / 100) ** 0.6

    # Normalize the time to 0-1 range to scale with cycle_duration
    time_normalized = time_minutes / np.max(time_minutes)

    # Define key points in the cycle as fractions of total cycle (using the original 28-min cycle as reference)
    bore_in_end = 3 / 28
    main_melting_end = 17 / 28
    melting_end = 20 / 28
    # remaining time is refining

    for i, t_norm in enumerate(time_normalized):
        actual_time = t_norm * cycle_duration  # Scale to actual cycle duration

        if t_norm <= bore_in_end:  # Bore-in
            eaf_power[i] = (15 + (25 - 15) * (t_norm / bore_in_end)) * scale
        elif t_norm <= main_melting_end:  # Main melting
            # Adjust frequency of sine wave to match new duration
            eaf_power[i] = (
                55 + 5 * np.sin(actual_time * 0.5 * (28 / cycle_duration))
            ) * scale
        elif t_norm <= melting_end:  # End of melting
            eaf_power[i] = (
                50
                - (50 - 40)
                * ((t_norm - main_melting_end) / (melting_end - main_melting_end))
            ) * scale
        else:  # Refining
            # Adjust frequency of sine wave to match new duration
            eaf_power[i] = (
                20 + 5 * np.sin(actual_time * 0.3 * (28 / cycle_duration))
            ) * scale
    return eaf_power


def calculate_grid_bess_power(eaf_power, grid_cap, bess_power_max):
    """Calculate grid and BESS power based on EAF power and constraints"""
    grid_power = np.zeros_like(eaf_power)
    bess_power = np.zeros_like(eaf_power)

    for i, p in enumerate(eaf_power):
        if p > grid_cap:
            # BESS discharges to cover the difference, up to its max power
            bess_power[i] = min(p - grid_cap, bess_power_max)
            grid_power[i] = p - bess_power[i]
        else:
            # Grid supplies all power, BESS is idle (or could be charging - not modeled here)
            grid_power[i] = p
            bess_power[i] = 0

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
        for rate_type, rate in utility_params["energy_rates"].items()
    }
    demand_charge = utility_params["demand_charge"] * seasonal_mult

    # Fill any gaps in TOU periods with off-peak
    filled_tou_periods = fill_tou_gaps(utility_params["tou_periods"])

    # EAF profile calculation - use actual cycle duration
    cycle_duration_min = eaf_params.get(
        "cycle_duration_input", 36
    )  # Get user-specified duration
    time_step_min = cycle_duration_min / 200  # Simulation time step
    time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(
        time, eaf_params["eaf_size"], cycle_duration_min
    )

    # Calculate grid and BESS power
    grid_power_cycle, bess_power_cycle = calculate_grid_bess_power(
        eaf_power_cycle, eaf_params["grid_cap"], bess_params["power_max"]
    )

    # Peak demand calculation
    peak_demand_kw = np.max(grid_power_cycle) * 1000  # Convert MW to kW

    # Energy calculations per cycle
    bess_energy_cycle = np.sum(bess_power_cycle) * (
        time_step_min / 60
    )  # MWh discharged per cycle
    grid_energy_cycle = np.sum(grid_power_cycle) * (
        time_step_min / 60
    )  # MWh from grid per cycle

    # Calculate energy charge by time-of-use period
    # For simplicity, we'll assume cycles are evenly distributed throughout the day
    tou_energy_costs = {}
    total_energy_cost = 0

    # Calculate proportion of cycles in each TOU period
    # Using filled_tou_periods instead of utility_params["tou_periods"]
    tou_hours = {
        period: end - start for start, end, period in filled_tou_periods
    }
    total_hours = 24

    for start, end, period in filled_tou_periods:
        period_hours = end - start
        period_fraction = period_hours / total_hours
        cycles_in_period = eaf_params["cycles_per_day"] * period_fraction
        energy_in_period = grid_energy_cycle * cycles_in_period * days_in_month
        period_cost = energy_in_period * energy_rates[period]

        tou_energy_costs[period] = period_cost
        total_energy_cost += period_cost

    # Calculate demand charge
    demand_cost = peak_demand_kw * demand_charge

    # Total monthly bill
    total_bill = total_energy_cost + demand_cost

    return {
        "energy_cost": total_energy_cost,
        "demand_cost": demand_cost,
        "total_bill": total_bill,
        "peak_demand_kw": peak_demand_kw,
        "energy_consumed_mwh": grid_energy_cycle
        * eaf_params["cycles_per_day"]
        * days_in_month,
        "tou_breakdown": tou_energy_costs,
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
        for rate_type, rate in utility_params["energy_rates"].items()
    }
    demand_charge = utility_params["demand_charge"] * seasonal_mult

    # Fill any gaps in TOU periods with off-peak
    filled_tou_periods = fill_tou_gaps(utility_params["tou_periods"])

    # EAF profile calculation - use actual cycle duration
    cycle_duration_min = eaf_params.get(
        "cycle_duration_input", 36
    )  # Get user-specified duration
    time_step_min = cycle_duration_min / 200  # Simulation time step
    time = np.linspace(0, cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(
        time, eaf_params["eaf_size"], cycle_duration_min
    )

    # Without BESS, grid power equals EAF power
    grid_power_cycle = eaf_power_cycle

    # Peak demand calculation
    peak_demand_kw = np.max(grid_power_cycle) * 1000  # Convert MW to kW

    # Energy calculations per cycle
    grid_energy_cycle = np.sum(grid_power_cycle) * (
        time_step_min / 60
    )  # MWh from grid per cycle

    # Calculate energy charge by time-of-use period
    tou_energy_costs = {}
    total_energy_cost = 0

    # Calculate proportion of cycles in each TOU period
    # Using filled_tou_periods instead of utility_params["tou_periods"]
    for start, end, period in filled_tou_periods:
        period_hours = end - start
        period_fraction = period_hours / 24
        cycles_in_period = eaf_params["cycles_per_day"] * period_fraction
        energy_in_period = grid_energy_cycle * cycles_in_period * days_in_month
        period_cost = energy_in_period * energy_rates[period]

        tou_energy_costs[period] = period_cost
        total_energy_cost += period_cost

    # Calculate demand charge
    demand_cost = peak_demand_kw * demand_charge

    # Total monthly bill
    total_bill = total_energy_cost + demand_cost

    return {
        "energy_cost": total_energy_cost,
        "demand_cost": demand_cost,
        "total_bill": total_bill,
        "peak_demand_kw": peak_demand_kw,
        "energy_consumed_mwh": grid_energy_cycle
        * eaf_params["cycles_per_day"]
        * days_in_month,
        "tou_breakdown": tou_energy_costs,
    }


def calculate_annual_billings(eaf_params, bess_params, utility_params):
    """Calculate monthly and annual bills with and without BESS"""
    monthly_bills_with_bess = []
    monthly_bills_without_bess = []
    monthly_savings = []

    for month in range(1, 13):
        days_in_month = calendar.monthrange(2024, month)[1]  # Using 2024 as a leap year

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
        monthly_


def calculate_annual_billings(eaf_params, bess_params, utility_params):
    """Calculate monthly and annual bills with and without BESS"""
    monthly_bills_with_bess = []
    monthly_bills_without_bess = []
    monthly_savings = []

    for month in range(1, 13):
        days_in_month = calendar.monthrange(2024, month)[1]  # Using 2024 as a leap year

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
        monthly_savings.append(savings)

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

    capacity_kwh = bess_params["capacity"] * 1000  # Convert MWh to kWh
    total_cost = capacity_kwh * bess_params["cost_per_kwh"]

    # Federal Investment Tax Credit (ITC) and CEIC are mutually exclusive
    # Choose the more beneficial one if both are enabled
    if incentive_params["itc_enabled"] and incentive_params["ceic_enabled"]:
        itc_amount = total_cost * (incentive_params["itc_percentage"] / 100)
        ceic_amount = total_cost * (incentive_params["ceic_percentage"] / 100)

        if itc_amount > ceic_amount:
            total_incentive += itc_amount
            incentive_breakdown["Investment Tax Credit (ITC)"] = itc_amount
        else:
            total_incentive += ceic_amount
            incentive_breakdown["Clean Electricity Investment Credit (CEIC)"] = (
                ceic_amount
            )
    elif incentive_params["itc_enabled"]:
        itc_amount = total_cost * (incentive_params["itc_percentage"] / 100)
        total_incentive += itc_amount
        incentive_breakdown["Investment Tax Credit (ITC)"] = itc_amount
    elif incentive_params["ceic_enabled"]:
        ceic_amount = total_cost * (incentive_params["ceic_percentage"] / 100)
        total_incentive += ceic_amount
        incentive_breakdown["Clean Electricity Investment Credit (CEIC)"] = ceic_amount

    # Bonus credits (can stack with ITC or CEIC)
    if incentive_params["bonus_credit_enabled"]:
        bonus_amount = total_cost * (incentive_params["bonus_credit_percentage"] / 100)
        total_incentive += bonus_amount
        incentive_breakdown["Bonus Credits"] = bonus_amount

    # California SGIP
    if incentive_params["sgip_enabled"]:
        sgip_amount = capacity_kwh * incentive_params["sgip_amount"]
        total_incentive += sgip_amount
        incentive_breakdown["CA Self-Generation Incentive Program"] = sgip_amount

    # Connecticut Energy Storage Solutions
    if incentive_params["ess_enabled"]:
        ess_amount = capacity_kwh * incentive_params["ess_amount"]
        total_incentive += ess_amount
        incentive_breakdown["CT Energy Storage Solutions"] = ess_amount

    # NY Market Acceleration Bridge Incentive
    if incentive_params["mabi_enabled"]:
        mabi_amount = capacity_kwh * incentive_params["mabi_amount"]
        total_incentive += mabi_amount
        incentive_breakdown["NY Market Acceleration Bridge Incentive"] = mabi_amount

    # Massachusetts Connected Solutions
    if incentive_params["cs_enabled"]:
        cs_amount = capacity_kwh * incentive_params["cs_amount"]
        total_incentive += cs_amount
        incentive_breakdown["MA Connected Solutions"] = cs_amount

    # Custom incentive
    if incentive_params["custom_incentive_enabled"]:
        if incentive_params["custom_incentive_type"] == "per_kwh":
            custom_amount = capacity_kwh * incentive_params["custom_incentive_amount"]
        else:  # percentage
            custom_amount = total_cost * (
                incentive_params["custom_incentive_amount"] / 100
            )

        total_incentive += custom_amount
        incentive_breakdown[incentive_params["custom_incentive_description"]] = (
            custom_amount
        )

    return {"total_incentive": total_incentive, "breakdown": incentive_breakdown}


# Improved financial metrics calculation
def calculate_financial_metrics(
    bess_params, financial_params, annual_savings, incentives, o_m_costs
):
    """Calculate NPV, IRR, payback period, etc. with incentives included"""
    # Initial investment calculation
    capacity_kwh = bess_params["capacity"] * 1000  # Convert MWh to kWh
    bess_cost = capacity_kwh * bess_params["cost_per_kwh"]

    # Adjust initial cost by incentives
    net_initial_cost = bess_cost - incentives["total_incentive"]

    # Prepare cash flow calculation
    project_years = financial_params["project_lifespan"]
    inflation_rate = financial_params["inflation_rate"]
    wacc = financial_params["wacc"]

    # Calculate battery replacement timing based on actual operating days
    # Default to 365 days if not provided in eaf_params
    days_per_year = bess_params.get("days_per_year", 365)
    cycles_per_year = bess_params["cycles_per_day"] * days_per_year
    battery_life_years = bess_params["cycle_life"] / cycles_per_year

    # Cash flow array
    cash_flows = [-net_initial_cost]  # Initial investment (year 0)

    # Track if battery has been replaced
    battery_replaced = False

    for year in range(1, project_years + 1):
        # Annual savings adjusted for inflation
        year_savings = annual_savings * ((1 + inflation_rate) ** (year - 1))

        # O&M costs adjusted for inflation
        year_om_costs = o_m_costs * ((1 + inflation_rate) ** (year - 1))

        # Check if battery replacement is needed - only replace once when lifetime is exceeded
        replacement_cost = 0
        if not battery_replaced and year > battery_life_years:
            replacement_cost = bess_cost * ((1 + inflation_rate) ** (year - 1))
            # Apply incentives to replacement (may need to adjust based on incentive rules)
            replacement_cost -= (
                incentives["total_incentive"] * 0.5
            )  # Assume 50% of incentives apply to replacement
            battery_replaced = True

        # Add salvage value in final year
        salvage_value = 0
        if year == project_years:
            # Calculate remaining life as a fraction of total life
            if battery_replaced:
                years_since_replacement = project_years - int(battery_life_years)
                remaining_life_fraction = 1 - (
                    years_since_replacement / battery_life_years
                )
                if remaining_life_fraction < 0:
                    remaining_life_fraction = 0
            else:
                remaining_life_fraction = 1 - (project_years / battery_life_years)
                if remaining_life_fraction < 0:
                    remaining_life_fraction = 0

            # If remaining life fraction is positive, calculate salvage value
            if remaining_life_fraction > 0:
                salvage_value = (
                    bess_cost
                    * financial_params["salvage_value"]
                    * ((1 + inflation_rate) ** (year - 1))
                )

        # Net cash flow for the year
        year_cash_flow = year_savings - year_om_costs - replacement_cost + salvage_value

        # Apply tax effects if needed
        taxable_income = year_savings - year_om_costs
        tax_effect = -taxable_income * financial_params["tax_rate"]
        year_cash_flow += tax_effect

        cash_flows.append(year_cash_flow)

    # Calculate financial metrics
    try:
        npv = npf.npv(wacc, cash_flows)
    except Exception as e:
        print(f"Error calculating NPV: {e}")
        npv = float("nan")

    try:
        irr = npf.irr(cash_flows)
    except Exception as e:
        print(f"Error calculating IRR: {e}")
        irr = float("nan")

    # Simple payback calculation with more robust handling
    cumulative_cash_flow = -net_initial_cost
    payback_years = float("inf")

    for year in range(1, project_years + 1):
        previous_ccf = cumulative_cash_flow
        cumulative_cash_flow += cash_flows[year]
        if previous_ccf < 0 and cumulative_cash_flow >= 0:
            # Linear interpolation for more accurate payback
            payback_years = year - 1 + (abs(previous_ccf) / abs(cash_flows[year]))
            break

    return {
        "npv": npv,
        "irr": irr,
        "payback_years": payback_years,
        "cash_flows": cash_flows,
        "net_initial_cost": net_initial_cost,
        "battery_life_years": battery_life_years,
    }


def optimize_battery_size(
    eaf_params, utility_params, financial_params, incentive_params, bess_base_params
):
    """Find optimal battery size for best ROI"""
    # Define search space for battery capacity
    capacity_options = np.linspace(5, 100, 20)  # 5 MWh to 100 MWh in 20 steps
    power_options = np.linspace(2, 50, 20)  # 2 MW to 50 MW in 20 steps

    best_roi = -float("inf")
    best_capacity = None
    best_power = None
    best_metrics = None
    optimization_results = []

    # Simple grid search for illustration purposes
    # In a real implementation, a more sophisticated optimization algorithm would be used
    for capacity in capacity_options:
        for power in power_options:
            # Skip invalid combinations (power > 2*capacity is usually not practical)
            if power > 2 * capacity:
                continue

            # Create test BESS parameters
            test_bess_params = bess_base_params.copy()
            test_bess_params["capacity"] = capacity
            test_bess_params["power_max"] = power
            # Add days_per_year from EAF params if available
            if "days_per_year" in eaf_params:
                test_bess_params["days_per_year"] = eaf_params["days_per_year"]

            # Calculate O&M costs
            o_m_costs = (
                test_bess_params["capacity"]
                * 1000
                * test_bess_params["om_cost_per_kwh_year"]
            )

            # Calculate annual savings
            billing_results = calculate_annual_billings(
                eaf_params, test_bess_params, utility_params
            )
            annual_savings = billing_results["annual_savings"]

            # Calculate incentives
            incentive_results = calculate_incentives(test_bess_params, incentive_params)

            # Calculate financial metrics
            metrics = calculate_financial_metrics(
                test_bess_params,
                financial_params,
                annual_savings,
                incentive_results,
                o_m_costs,
            )

            # Calculate ROI
            if metrics["payback_years"] <= financial_params["project_lifespan"]:
                # Use NPV divided by initial investment as ROI metric
                roi = (
                    metrics["npv"] / metrics["net_initial_cost"]
                    if metrics["net_initial_cost"] > 0
                    else -float("inf")
                )
            else:
                roi = -float("inf")  # No payback within project lifespan

            optimization_results.append(
                {
                    "capacity": capacity,
                    "power": power,
                    "roi": roi,
                    "npv": metrics["npv"],
                    "irr": metrics["irr"],
                    "payback_years": metrics["payback_years"],
                }
            )

            # Update best result if better ROI found
            if roi > best_roi:
                best_roi = roi
                best_capacity = capacity
                best_power = power
                best_metrics = metrics

    return {
        "best_capacity": best_capacity,
        "best_power": best_power,
        "best_roi": best_roi,
        "best_metrics": best_metrics,
        "all_results": optimization_results,
    }
# --- Application Layout ---
app.layout = html.Div(
    [
        # Store components for maintaining state across callbacks
        dcc.Store(id="eaf-params-store", data={}),
        dcc.Store(id="utility-params-store", data={}),
        dcc.Store(id="bess-params-store", data={}),
        dcc.Store(id="financial-params-store", data={}),
        dcc.Store(id="incentive-params-store", data={}),
        dcc.Store(id="calculation-results-store", data={}),
        dcc.Store(
            id="optimization-results-store", data={}
        ),  # New store for optimization results
        html.Div(
            [
                html.H1(
                    "EAF-BESS Peak Shaving Dashboard", className="mb-4 text-center"
                ),
                html.Div(
                    id="error-message-container",
                    className="alert alert-warning",
                    style={"display": "none"},
                ),
                html.Div(
                    id="validation-error-container",
                    className="alert alert-danger",
                    style={"display": "none"},
                ),
                # Tabs for organized sections
                dcc.Tabs(
                    [
                        # Mill Selection Tab
                        dcc.Tab(
                            label="Mill Selection",
                            children=[
                                html.Div(
                                    [
                                        html.H3("Select Nucor Mill", className="mb-3"),
                                        html.P(
                                            "Choose a mill from the dropdown to automatically populate parameters, or select 'Custom' to enter your own values.",
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
                                                    value="Custom",
                                                    clearable=False,
                                                    className="form-select mb-3",
                                                ),
                                            ],
                                            className="mb-4",
                                        ),
                                        # Mill Information Card
                                        html.Div(
                                            id="mill-info-card",
                                            className="card mb-4",
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
                        ),
                        # Parameters Tab
                        dcc.Tab(
                            label="System Parameters",
                            children=[
                                html.Div(
                                    [
                                        # Row for parameters
                                        html.Div(
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
                                                                            value="Custom Utility",
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
                                                                        html.Label(
                                                                            "Seasonal Rates:",
                                                                            className="form-check-label",
                                                                        ),
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
                                                                            className="form-check",
                                                                        ),
                                                                    ],
                                                                    className="mb-3",
                                                                ),
                                                                # Seasonal multipliers (conditionally shown)
                                                                html.Div(
                                                                    id="seasonal-rates-container",
                                                                    className="mb-3",
                                                                ),
                                                                # Time-of-Use Periods
                                                                html.H5(
                                                                    "Time-of-Use Periods",
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    id="tou-periods-container",
                                                                    children=[
                                                                        # To be populated by callback
                                                                    ],
                                                                ),
                                                                html.Button(
                                                                    "Add TOU Period",
                                                                    id="add-tou-period-button",
                                                                    n_clicks=0,
                                                                    className="btn btn-sm btn-success mt-2",
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),
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
                                                                            "Cycle Duration (minutes):",
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
                                                                            max=365,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                            ],
                                                            className="card p-3",
                                                        ),
                                                    ],
                                                    className="col-md-6",
                                                ),
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
                                                        ),
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
                                                                            value=default_financial_params[
                                                                                "wacc"
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
                                                                            "Interest Rate (%):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="interest-rate",
                                                                            type="number",
                                                                            value=default_financial_params[
                                                                                "interest_rate"
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
                                                                            "Debt Fraction (%):",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="debt-fraction",
                                                                            type="number",
                                                                            value=default_financial_params[
                                                                                "debt_fraction"
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
                                                                            "Salvage Value (% of BESS cost):",
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
                                                        ),
                                                    ],
                                                    className="col-md-6",
                                                ),
                                            ],
                                            className="row",
                                        ),
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
                        ),
                        # Incentives Tab
                        dcc.Tab(
                            label="Battery Incentives",
                            children=[
                                html.Div(
                                    [
                                        html.H3(
                                            "Battery Incentive Programs",
                                            className="mb-4 text-center",
                                        ),
                                        html.P(
                                            "Select applicable incentives to include in financial calculations.",
                                            className="text-muted mb-4 text-center",
                                        ),
                                        # Row for incentives
                                        html.Div(
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
                                                                # Investment Tax Credit (ITC)
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="itc-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "Investment Tax Credit (ITC)",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Provides a tax credit of up to 30% of the capital expenditure for energy storage systems.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "ITC Percentage (%):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="itc-percentage",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "itc_percentage"
                                                                                    ],
                                                                                    min=0,
                                                                                    max=100,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                                # Clean Electricity Investment Credit (CEIC)
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="ceic-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "Clean Electricity Investment Credit (CEIC)",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Credit for clean electricity generation and storage facilities with zero greenhouse gas emissions.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                                html.P(
                                                                                    "Note: ITC and CEIC are mutually exclusive. If both are selected, the more beneficial one will be applied.",
                                                                                    className="text-warning small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "CEIC Percentage (%):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="ceic-percentage",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "ceic_percentage"
                                                                                    ],
                                                                                    min=0,
                                                                                    max=100,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                                # Bonus Credits
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="bonus-credit-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "Bonus Credits",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Additional incentives for projects in energy communities or meeting domestic content requirements.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "Bonus Percentage (%):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="bonus-credit-percentage",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "bonus_credit_percentage"
                                                                                    ],
                                                                                    min=0,
                                                                                    max=100,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),
                                                    ],
                                                    className="col-md-6",
                                                ),
                                                # Right column: State Incentives & Custom
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "State Incentives",
                                                                    className="mb-3",
                                                                ),
                                                                # California SGIP
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="sgip-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "California Self-Generation Incentive Program (SGIP)",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Rebates for installing energy storage technologies.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "SGIP Amount ($/kWh):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="sgip-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "sgip_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                                # Connecticut ESS
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="ess-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "Connecticut Energy Storage Solutions",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Upfront incentives for customer-sited energy storage systems.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "ESS Amount ($/kWh):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="ess-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "ess_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                                # NY MABI
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="mabi-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "NY Market Acceleration Bridge Incentive",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Incentives for retail and bulk energy storage systems.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "MABI Amount ($/kWh):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="mabi-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "mabi_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                                # MA Connected Solutions
                                                                html.Div(
                                                                    [
                                                                        html.Div(
                                                                            [
                                                                                dcc.Checklist(
                                                                                    id="cs-enabled",
                                                                                    options=[
                                                                                        {
                                                                                            "label": "Massachusetts Connected Solutions",
                                                                                            "value": "enabled",
                                                                                        }
                                                                                    ],
                                                                                    value=[],
                                                                                    className="form-check",
                                                                                ),
                                                                                html.P(
                                                                                    "Demand response program for battery storage systems.",
                                                                                    className="text-muted small mt-1",
                                                                                ),
                                                                            ],
                                                                            className="mb-2",
                                                                        ),
                                                                        html.Div(
                                                                            [
                                                                                html.Label(
                                                                                    "CS Amount ($/kWh):",
                                                                                    className="form-label",
                                                                                ),
                                                                                dcc.Input(
                                                                                    id="cs-amount",
                                                                                    type="number",
                                                                                    value=default_incentive_params[
                                                                                        "cs_amount"
                                                                                    ],
                                                                                    min=0,
                                                                                    className="form-control",
                                                                                ),
                                                                            ],
                                                                            className="mb-3 ms-4",
                                                                        ),
                                                                    ],
                                                                ),
                                                            ],
                                                            className="card p-3 mb-4",
                                                        ),
                                                        # Custom Incentive
                                                        html.Div(
                                                            [
                                                                html.H4(
                                                                    "Custom Incentive",
                                                                    className="mb-3",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        dcc.Checklist(
                                                                            id="custom-incentive-enabled",
                                                                            options=[
                                                                                {
                                                                                    "label": "Enable Custom Incentive",
                                                                                    "value": "enabled",
                                                                                }
                                                                            ],
                                                                            value=[],
                                                                            className="form-check",
                                                                        ),
                                                                    ],
                                                                    className="mb-2",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Incentive Type:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.RadioItems(
                                                                            id="custom-incentive-type",
                                                                            options=[
                                                                                {
                                                                                    "label": "Per kWh ($/kWh)",
                                                                                    "value": "per_kwh",
                                                                                },
                                                                                {
                                                                                    "label": "Percentage of Cost (%)",
                                                                                    "value": "percentage",
                                                                                },
                                                                            ],
                                                                            value="per_kwh",
                                                                            className="form-check",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 ms-4",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Incentive Amount:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="custom-incentive-amount",
                                                                            type="number",
                                                                            value=default_incentive_params[
                                                                                "custom_incentive_amount"
                                                                            ],
                                                                            min=0,
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 ms-4",
                                                                ),
                                                                html.Div(
                                                                    [
                                                                        html.Label(
                                                                            "Description:",
                                                                            className="form-label",
                                                                        ),
                                                                        dcc.Input(
                                                                            id="custom-incentive-description",
                                                                            type="text",
                                                                            value=default_incentive_params[
                                                                                "custom_incentive_description"
                                                                            ],
                                                                            className="form-control",
                                                                        ),
                                                                    ],
                                                                    className="mb-2 ms-4",
                                                                ),
                                                            ],
                                                            className="card p-3",
                                                        ),
                                                    ],
                                                    className="col-md-6",
                                                ),
                                            ],
                                            className="row",
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Calculate Results",
                                                    id="calculate-results-button",
                                                    n_clicks=0,
                                                    className="btn btn-primary mt-4 mb-3",
                                                ),
                                                html.Button(
                                                    "Show Debug Info",
                                                    id="debug-button",
                                                    n_clicks=0,
                                                    className="btn btn-warning mt-4 mb-3 ms-3",
                                                ),
                                                html.Button(
                                                    "Optimize Battery Size",
                                                    id="optimize-battery-button",
                                                    n_clicks=0,
                                                    className="btn btn-success mt-4 mb-3 ms-3",
                                                ),
                                            ],
                                            className="d-flex justify-content-center",
                                        ),
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),
                        # Results Tab
                        dcc.Tab(
                            label="Results & Analysis",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="results-loading-spinner",
                                            children=[
                                                dcc.Loading(
                                                    type="circle",
                                                    children=html.Div(
                                                        id="results-output-container"
                                                    ),
                                                )
                                            ],
                                        )
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),
                        # Battery Sizing Optimization Tab
                        dcc.Tab(
                            label="Battery Sizing Tool",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="optimization-loading-spinner",
                                            children=[
                                                dcc.Loading(
                                                    type="circle",
                                                    children=html.Div(
                                                        id="optimization-output-container"
                                                    ),
                                                )
                                            ],
                                        )
                                    ],
                                    className="container py-4",
                                )
                            ],
                        ),
                    ]
                ),
            ],
            className="container-fluid bg-light min-vh-100 py-4",
        ),
    ]
)
# --- Callbacks ---

# Callback to update utility parameters store
@app.callback(
    Output("utility-params-store", "data"),
    [Input("utility-provider-dropdown", "value"),
     Input("off-peak-rate", "value"),
     Input("mid-peak-rate", "value"),
     Input("peak-rate", "value"),
     Input("demand-charge", "value"),
     Input("seasonal-rates-toggle", "value"),
     Input("winter-multiplier", "value"),
     Input("summer-multiplier", "value"),
     Input("shoulder-multiplier", "value"),
     Input("winter-months", "value"),
     Input("summer-months", "value"),
     Input("shoulder-months", "value"),
     Input({"type": "tou-start", "index": dash.dependencies.ALL}, "value"),
     Input({"type": "tou-end", "index": dash.dependencies.ALL}, "value"),
     Input({"type": "tou-rate", "index": dash.dependencies.ALL}, "value")],
)
def update_utility_params(
    utility_provider, off_peak_rate, mid_peak_rate, peak_rate, demand_charge,
    seasonal_toggle, winter_mult, summer_mult, shoulder_mult,
    winter_months, summer_months, shoulder_months,
    tou_starts, tou_ends, tou_rates
):
    """Update utility parameters store based on user inputs"""
    # Create energy rates dictionary
    energy_rates = {
        "off_peak": off_peak_rate,
        "mid_peak": mid_peak_rate,
        "peak": peak_rate
    }
    
    # Parse seasonal months
    try:
        winter_months_list = [int(m.strip()) for m in winter_months.split(",") if m.strip()]
    except (ValueError, AttributeError, TypeError):
        winter_months_list = [11, 12, 1, 2, 3]  # Default
        
    try:
        summer_months_list = [int(m.strip()) for m in summer_months.split(",") if m.strip()]
    except (ValueError, AttributeError, TypeError):
        summer_months_list = [6, 7, 8, 9]  # Default
        
    try:
        shoulder_months_list = [int(m.strip()) for m in shoulder_months.split(",") if m.strip()]
    except (ValueError, AttributeError, TypeError):
        shoulder_months_list = [4, 5, 10]  # Default
    
    # Build TOU periods - ensure all values are of the same type
    tou_periods = []
    for i in range(len(tou_starts)):
        if tou_starts[i] is not None and tou_ends[i] is not None and tou_rates[i] is not None:
            # Convert all values to appropriate types
            start = float(tou_starts[i])
            end = float(tou_ends[i])
            rate = str(tou_rates[i])
            tou_periods.append((start, end, rate))
    
    # Sort periods by start time - using a key function to avoid type comparison
    tou_periods.sort(key=lambda x: x[0])
    
    # Create utility parameters dictionary
    utility_params = {
        "energy_rates": energy_rates,
        "demand_charge": demand_charge,
        "tou_periods": tou_periods,
        "seasonal_rates": True if seasonal_toggle and "enabled" in seasonal_toggle else False,
        "winter_months": winter_months_list,
        "summer_months": summer_months_list,
        "shoulder_months": shoulder_months_list,
        "winter_multiplier": winter_mult if winter_mult is not None else 1.0,
        "summer_multiplier": summer_mult if summer_mult is not None else 1.0,
        "shoulder_multiplier": shoulder_mult if shoulder_mult is not None else 1.0
    }
    
    return utility_params
# Callback to update Mill Info Card when mill is selected
@app.callback(
    Output("mill-info-card", "children"), Input("mill-selection-dropdown", "value")
)
def update_mill_info(selected_mill):
    """Update the mill information card based on the selected mill"""
    if not selected_mill or selected_mill not in nucor_mills:
        return html.Div("Please select a valid mill", className="text-danger")

    mill_data = nucor_mills[selected_mill]

    # Create info card layout
    info_card = html.Div(
        [
            html.H5(
                f"Nucor Steel {selected_mill}",
                className="card-header bg-primary text-white",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Strong("Location: "),
                            html.Span(mill_data["location"]),
                        ],
                        className="mb-2",
                    ),
                    html.Div(
                        [
                            html.Strong("Mill Type: "),
                            html.Span(mill_data["type"]),
                        ],
                        className="mb-2",
                    ),
                    html.Div(
                        [
                            html.Strong("EAF Configuration: "),
                            html.Span(
                                f"{mill_data['eaf_count']} x {mill_data['eaf_size']} ton {mill_data['eaf_type']} "
                                f"({mill_data['eaf_manufacturer']})"
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.Div(
                        [
                            html.Strong("Annual Production: "),
                            html.Span(f"{mill_data['tons_per_year']:,} tons"),
                        ],
                        className="mb-2",
                    ),
                    html.Div(
                        [
                            html.Strong("Operating Schedule: "),
                            html.Span(
                                f"{mill_data['cycles_per_day']} cycles/day, "
                                f"{mill_data['days_per_year']} days/year, "
                                f"{mill_data['cycle_duration']} min/cycle"
                            ),
                        ],
                        className="mb-2",
                    ),
                    html.Div(
                        [
                            html.Strong("Utility Provider: "),
                            html.Span(mill_data["utility"]),
                        ],
                        className="mb-2",
                    ),
                ],
                className="card-body",
            ),
        ]
    )

    return info_card


# Callback to update Utility Provider dropdown when mill is selected
@app.callback(
    Output("utility-provider-dropdown", "value"),
    Input("mill-selection-dropdown", "value"),
)
def update_utility_provider(selected_mill):
    """Set the utility provider based on selected mill"""
    if not selected_mill or selected_mill not in nucor_mills:
        return "Custom Utility"

    mill_data = nucor_mills[selected_mill]
    utility = mill_data["utility"]

    # If the utility isn't in our database, default to Custom
    if utility not in utility_rates:
        return "Custom Utility"

    return utility


# Callback to update EAF Parameters when mill is selected
@app.callback(
    [
        Output("eaf-size", "value"),
        Output("eaf-count", "value"),
        Output("grid-cap", "value"),
        Output("cycles-per-day", "value"),
        Output("cycle-duration", "value"),
        Output("days-per-year", "value"),
    ],
    Input("mill-selection-dropdown", "value"),
)
def update_eaf_parameters(selected_mill):
    """Update EAF parameters based on selected mill"""
    if not selected_mill or selected_mill not in nucor_mills:
        return (
            nucor_mills["Custom"]["eaf_size"],
            nucor_mills["Custom"]["eaf_count"],
            nucor_mills["Custom"]["grid_cap"],
            nucor_mills["Custom"]["cycles_per_day"],
            nucor_mills["Custom"]["cycle_duration"],
            nucor_mills["Custom"]["days_per_year"],
        )

    mill_data = nucor_mills[selected_mill]

    return (
        mill_data["eaf_size"],
        mill_data["eaf_count"],
        mill_data["grid_cap"],
        mill_data["cycles_per_day"],
        mill_data["cycle_duration"],
        mill_data["days_per_year"],
    )


# Callback to update Utility Rates when provider is selected
@app.callback(
    [
        Output("off-peak-rate", "value"),
        Output("mid-peak-rate", "value"),
        Output("peak-rate", "value"),
        Output("demand-charge", "value"),
        Output("seasonal-rates-toggle", "value"),
    ],
    Input("utility-provider-dropdown", "value"),
)
def update_utility_rates(selected_utility):
    """Update utility rates based on selected provider"""
    if not selected_utility or selected_utility not in utility_rates:
        return (
            default_utility_params["energy_rates"]["off_peak"],
            default_utility_params["energy_rates"]["mid_peak"],
            default_utility_params["energy_rates"]["peak"],
            default_utility_params["demand_charge"],
            ["enabled"] if default_utility_params["seasonal_rates"] else [],
        )

    utility_data = utility_rates[selected_utility]

    return (
        utility_data["energy_rates"]["off_peak"],
        utility_data["energy_rates"]["mid_peak"],
        utility_data["energy_rates"]["peak"],
        utility_data["demand_charge"],
        ["enabled"] if utility_data["seasonal_rates"] else [],
    )


# Callback to show/hide seasonal rate inputs
@app.callback(
    Output("seasonal-rates-container", "children"),
    Input("seasonal-rates-toggle", "value"),
)
def update_seasonal_rates_ui(toggle_value):
    """Show or hide seasonal rate inputs based on toggle"""
    if not toggle_value or "enabled" not in toggle_value:
        return []

    # Create seasonal rate inputs UI
    seasonal_ui = html.Div(
        [
            html.H5("Seasonal Rate Adjustments", className="mb-2"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label("Winter Multiplier:", className="form-label"),
                            dcc.Input(
                                id="winter-multiplier",
                                type="number",
                                value=default_utility_params["winter_multiplier"],
                                min=0.1,
                                step=0.1,
                                className="form-control",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                    html.Div(
                        [
                            html.Label("Summer Multiplier:", className="form-label"),
                            dcc.Input(
                                id="summer-multiplier",
                                type="number",
                                value=default_utility_params["summer_multiplier"],
                                min=0.1,
                                step=0.1,
                                className="form-control",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                    html.Div(
                        [
                            html.Label("Shoulder Multiplier:", className="form-label"),
                            dcc.Input(
                                id="shoulder-multiplier",
                                type="number",
                                value=default_utility_params["shoulder_multiplier"],
                                min=0.1,
                                step=0.1,
                                className="form-control",
                            ),
                        ],
                        className="col-md-4 mb-2",
                    ),
                ],
                className="row",
            ),
            html.Div(
                [
                    html.Label("Winter Months:", className="form-label"),
                    dcc.Input(
                        id="winter-months",
                        type="text",
                        value=",".join(
                            str(m) for m in default_utility_params["winter_months"]
                        ),
                        placeholder="Comma-separated list of months (1-12)",
                        className="form-control",
                    ),
                ],
                className="mb-2",
            ),
            html.Div(
                [
                    html.Label("Summer Months:", className="form-label"),
                    dcc.Input(
                        id="summer-months",
                        type="text",
                        value=",".join(
                            str(m) for m in default_utility_params["summer_months"]
                        ),
                        placeholder="Comma-separated list of months (1-12)",
                        className="form-control",
                    ),
                ],
                className="mb-2",
            ),
            html.Div(
                [
                    html.Label("Shoulder Months:", className="form-label"),
                    dcc.Input(
                        id="shoulder-months",
                        type="text",
                        value=",".join(
                            str(m) for m in default_utility_params["shoulder_months"]
                        ),
                        placeholder="Comma-separated list of months (1-12)",
                        className="form-control",
                    ),
                ],
                className="mb-2",
            ),
        ]
    )


    return seasonal_ui
# Callback to initialize TOU periods
@app.callback(
    Output("tou-periods-container", "children"),
    Input("utility-provider-dropdown", "value"),
)
def initialize_tou_periods(selected_utility):
    """Initialize TOU period UI elements based on selected utility"""
    if not selected_utility or selected_utility not in utility_rates:
        tou_periods = default_utility_params["tou_periods"]
    else:
        tou_periods = utility_rates[selected_utility]["tou_periods"]

    tou_elements = []
    for i, (start, end, rate_type) in enumerate(tou_periods):
        tou_row = html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                dcc.Input(
                                    id={"type": "tou-start", "index": i},
                                    type="number",
                                    min=0,
                                    max=24,
                                    step=0.5,
                                    value=start,
                                    className="form-control form-control-sm",
                                    placeholder="Start Hr",
                                ),
                            ],
                            className="col-3",
                        ),
                        html.Div(
                            [
                                dcc.Input(
                                    id={"type": "tou-end", "index": i},
                                    type="number",
                                    min=0,
                                    max=24,
                                    step=0.5,
                                    value=end,
                                    className="form-control form-control-sm",
                                    placeholder="End Hr",
                                ),
                            ],
                            className="col-3",
                        ),
                        html.Div(
                            [
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
                            ],
                            className="col-4",
                        ),
                        html.Div(
                            [
                                html.Button(
                                    "×",
                                    id={"type": "remove-tou", "index": i},
                                    className="btn btn-danger btn-sm mt-1",
                                    disabled=(i == 0),  # Disable remove for first row
                                ),
                            ],
                            className="col-2 d-flex align-items-center justify-content-center",
                        ),
                    ],
                    className="row g-1 mb-1 align-items-center tou-period",
                ),
            ],
            id=f"tou-row-{i}",
        )
        tou_elements.append(tou_row)

    return tou_elements


# Callback to add TOU period
@app.callback(
    Output("tou-periods-container", "children", allow_duplicate=True),
    Input("add-tou-period-button", "n_clicks"),
    State("tou-periods-container", "children"),
    prevent_initial_call=True,
)
def add_tou_period(n_clicks, current_rows):
    """Add a new TOU period row"""
    if n_clicks == 0 or not current_rows:
        return dash.no_update

    # Determine the next index
    next_index = len(current_rows)

    # Create new row with default values
    new_row = html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Input(
                                id={"type": "tou-start", "index": next_index},
                                type="number",
                                min=0,
                                max=24,
                                step=0.5,
                                value=0,  # Default start
                                className="form-control form-control-sm",
                                placeholder="Start Hr",
                            ),
                        ],
                        className="col-3",
                    ),
                    html.Div(
                        [
                            dcc.Input(
                                id={"type": "tou-end", "index": next_index},
                                type="number",
                                min=0,
                                max=24,
                                step=0.5,
                                value=0,  # Default end
                                className="form-control form-control-sm",
                                placeholder="End Hr",
                            ),
                        ],
                        className="col-3",
                    ),
                    html.Div(
                        [
                            dcc.Dropdown(
                                id={"type": "tou-rate", "index": next_index},
                                options=[
                                    {"label": "Off-Peak", "value": "off_peak"},
                                    {"label": "Mid-Peak", "value": "mid_peak"},
                                    {"label": "Peak", "value": "peak"},
                                ],
                                value="off_peak",  # Default rate
                                clearable=False,
                                className="form-select form-select-sm",
                            ),
                        ],
                        className="col-4",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "×",
                                id={"type": "remove-tou", "index": next_index},
                                className="btn btn-danger btn-sm mt-1",
                                disabled=False,
                            ),
                        ],
                        className="col-2 d-flex align-items-center justify-content-center",
                    ),
                ],
                className="row g-1 mb-1 align-items-center tou-period",
            ),
        ],
        id=f"tou-row-{next_index}",
    )

    return current_rows + [new_row]


# Improved callback to remove TOU period
@app.callback(
    Output("tou-periods-container", "children", allow_duplicate=True),
    Input({"type": "remove-tou", "index": dash.dependencies.ALL}, "n_clicks"),
    State("tou-periods-container", "children"),
    prevent_initial_call=True,
)
def remove_tou_period(n_clicks_list, current_rows):
    """Remove a TOU period row when the remove button is clicked"""
    ctx = dash.callback_context
    if not ctx.triggered or not current_rows:
        return dash.no_update

    # Get the index of the button that was clicked
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        clicked_index = json.loads(button_id)["index"]
    except:
        return dash.no_update

    # Remove the row by matching the id
    new_rows = []
    for row in current_rows:
        # Extract row_id from the row component
        row_id = row["props"]["id"]
        if row_id != f"tou-row-{clicked_index}":
            new_rows.append(row)

    # If no rows left, add a default row
    if not new_rows:
        new_rows = [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    dcc.Input(
                                        id={"type": "tou-start", "index": 0},
                                        type="number",
                                        min=0,
                                        max=24,
                                        step=0.5,
                                        value=0,
                                        className="form-control form-control-sm",
                                        placeholder="Start Hr",
                                    ),
                                ],
                                className="col-3",
                            ),
                            html.Div(
                                [
                                    dcc.Input(
                                        id={"type": "tou-end", "index": 0},
                                        type="number",
                                        min=0,
                                        max=24,
                                        step=0.5,
                                        value=24,
                                        className="form-control form-control-sm",
                                        placeholder="End Hr",
                                    ),
                                ],
                                className="col-3",
                            ),
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id={"type": "tou-rate", "index": 0},
                                        options=[
                                            {"label": "Off-Peak", "value": "off_peak"},
                                            {"label": "Mid-Peak", "value": "mid_peak"},
                                            {"label": "Peak", "value": "peak"},
                                        ],
                                        value="off_peak",
                                        clearable=False,
                                        className="form-select form-select-sm",
                                    ),
                                ],
                                className="col-4",
                            ),
                            html.Div(
                                [
                                    html.Button(
                                        "×",
                                        id={"type": "remove-tou", "index": 0},
                                        className="btn btn-danger btn-sm mt-1",
                                        disabled=True,  # Disable remove for last row
                                    ),
                                ],
                                className="col-2 d-flex align-items-center justify-content-center",
                            ),
                        ],
                        className="row g-1 mb-1 align-items-center tou-period",
                    ),
                ],
                id="tou-row-0",
            )
        ]

    return new_rows


# Add input validation callback
@app.callback(
    [
        Output("validation-error-container", "children"),
        Output("validation-error-container", "style"),
    ],
    [
        Input("calculate-results-button", "n_clicks"),
        # Required inputs to validate
        State({"type": "tou-start", "index": dash.dependencies.ALL}, "value"),
        State({"type": "tou-end", "index": dash.dependencies.ALL}, "value"),
        State({"type": "tou-rate", "index": dash.dependencies.ALL}, "value"),
        State("seasonal-rates-toggle", "value"),
        State("winter-months", "value"),
        State("summer-months", "value"),
        State("shoulder-months", "value"),
        State("bess-capacity", "value"),
        State("bess-power", "value"),
    ],
    prevent_initial_call=True,
)
def validate_inputs(
    n_clicks,
    tou_starts,
    tou_ends,
    tou_rates,
    seasonal_toggle,
    winter_months,
    summer_months,
    shoulder_months,
    bess_capacity,
    bess_power,
):
    """Validate inputs before running calculations"""
    if n_clicks == 0:
        return "", {"display": "none"}

    errors = []
    warnings = []

    # Check TOU periods
    if (
        not tou_starts
        or not tou_ends
        or not tou_rates
        or len(tou_starts) != len(tou_ends)
        or len(tou_starts) != len(tou_rates)
    ):
        errors.append("Time-of-Use periods are incomplete.")
    else:
        # Sort periods by start time
        periods = sorted(
            [
                (start, end, rate)
                for start, end, rate in zip(tou_starts, tou_ends, tou_rates)
                if start is not None and end is not None
            ]
        )

        # Check for gaps or overlaps
        if not periods:
            errors.append("No valid Time-of-Use periods defined.")
        else:
            # Generate a warning if periods don't cover 0-24
            if periods[0][0] != 0 or periods[-1][1] != 24:
                warnings.append(
                    "Time-of-Use periods don't cover the full 24 hours. Off-peak rates will be applied to missing hours."
                )
            
            # Check for overlaps (but allow gaps)
            for i in range(len(periods) - 1):
                if periods[i][1] > periods[i + 1][0]:
                    errors.append(
                        f"Time-of-Use periods have overlaps. Period ending at {periods[i][1]} overlaps with period starting at {periods[i+1][0]}."
                    )

    # Check seasonal months if enabled
    if seasonal_toggle and "enabled" in seasonal_toggle:
        try:
            winter_months_list = [
                int(m.strip()) for m in winter_months.split(",") if m.strip()
            ]
            if not all(1 <= m <= 12 for m in winter_months_list):
                errors.append("Winter months must be between 1 and 12.")
        except ValueError:
            errors.append(
                "Invalid winter months format. Use comma-separated numbers (1-12)."
            )

        try:
            summer_months_list = [
                int(m.strip()) for m in summer_months.split(",") if m.strip()
            ]
            if not all(1 <= m <= 12 for m in summer_months_list):
                errors.append("Summer months must be between 1 and 12.")
        except ValueError:
            errors.append(
                "Invalid summer months format. Use comma-separated numbers (1-12)."
            )

        try:
            shoulder_months_list = [
                int(m.strip()) for m in shoulder_months.split(",") if m.strip()
            ]
            if not all(1 <= m <= 12 for m in shoulder_months_list):
                errors.append("Shoulder months must be between 1 and 12.")
        except ValueError:
            errors.append(
                "Invalid shoulder months format. Use comma-separated numbers (1-12)."
            )

        # Check if all months are covered and no month appears twice
        all_months = winter_months_list + summer_months_list + shoulder_months_list
        if len(all_months) != len(set(all_months)):
            errors.append("Some months appear in multiple seasons.")
        if not all(m in all_months for m in range(1, 13)):
            errors.append("Not all months (1-12) are assigned to a season.")

    # Check BESS parameters
    if bess_capacity is not None and bess_power is not None:
        if bess_power > 2 * bess_capacity:
            warnings.append(
                "Battery power rating (MW) is more than twice the energy capacity (MWh), which may not be practical."
            )

    # If errors exist, display them, otherwise show warnings
    if errors:
        error_list = html.Ul([html.Li(error) for error in errors])
        return [html.H5("Validation Errors:", className="mb-2"), error_list], {
            "display": "block"
        }
    elif warnings:
        warning_list = html.Ul([html.Li(warning) for warning in warnings])
        return [html.H5("Warnings:", className="mb-2"), warning_list], {
            "display": "block", "background-color": "#fff3cd", "color": "#856404"  # Yellow warning style
        }
    else:
        return "", {"display": "none"}
@app.callback(
    Output("results-output-container", "children"), 
    Input("calculate-results-button", "n_clicks"),
    [State("eaf-params-store", "data"),
     State("bess-params-store", "data"),
     State("utility-params-store", "data")],
    prevent_initial_call=True
)
def debug_display_results(n_clicks, eaf_params, bess_params, utility_params):
    if n_clicks == 0:
        return html.Div("Click the Calculate Results button to see results")
    
    try:
        # Try a basic calculation
        if "tou_periods" in utility_params:
            filled_periods = fill_tou_gaps(utility_params["tou_periods"])
            utility_params_copy = utility_params.copy()
            utility_params_copy["tou_periods"] = filled_periods
            
            # Calculate for one month
            monthly_bill = create_monthly_bill_with_bess(
                eaf_params, bess_params, utility_params_copy, 30, 1  # January
            )
            
            return html.Div([
                html.H3("Debug Results"),
                html.H4("Original TOU Periods:"),
                html.Pre(str(utility_params["tou_periods"])),
                html.H4("Filled TOU Periods:"),
                html.Pre(str(filled_periods)),
                html.H4("Sample Monthly Bill (January):"),
                html.Pre(str(monthly_bill))
            ], className="card p-3")
        
        else:
            return html.Div([
                html.H3("Error"),
                html.P("No TOU periods found in utility parameters"),
                html.Pre(str(utility_params))
            ])
    
    except Exception as e:
        # Show any errors
        return html.Div([
            html.H3("Error"),
            html.P(str(e)),
            html.Pre(f"Error type: {type(e).__name__}")
        ], className="alert alert-danger")   
        
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8050, debug=False)
