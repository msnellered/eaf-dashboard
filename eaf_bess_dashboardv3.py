# Import libraries for the dashboard and calculations
import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import plotly.graph_objects as go

# import plotly.express as px # Removed - Unused
import numpy as np

# import pandas as pd # Removed - Unused
# import warnings # Removed - Unused
import json  # Moved import to top

# Make sure numpy_financial is installed
try:
    import numpy_financial as npf
except ImportError:
    print(
        "numpy_financial package is required. Please install it with: pip install numpy-financial"
    )
    # Provide a fallback for NPV and IRR calculations (simplified)
    npf = type(
        "DummyNPF",
        (),
        {
            "npv": lambda r, c: sum(c[i] / (1 + r) ** i for i in range(len(c))),
            "irr": lambda c: np.nan,  # Simplified fallback returns NaN
        },
    )

# Initialize the Dash app (this creates the web server)
app = dash.Dash(
    __name__,
    external_stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css"
    ],
    suppress_callback_exceptions=True,  # Needed for pattern-matching callbacks
)
server = app.server

app.title = "EAF-BESS Peak Shaving Dashboard V2 (Fixed)"

# --- Default Parameters ---
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
}
default_financial_params = {
    "wacc": 0.06,  # 6% Weighted Average Cost of Capital
    "interest_rate": 0.04,  # 4% Interest rate for debt
    "debt_fraction": 0.5,  # 50% of BESS cost financed
    "project_lifespan": 10,  # 10 years
    "tax_rate": 0.25,  # 25% tax rate
    "inflation_rate": 0.02,  # 2% inflation
    "salvage_value": 0.1,  # 10% of BESS cost at end
}
default_eaf_params = {
    "eaf_size": 100,  # tons
    "cycles_per_day": 10,  # 10 EAF cycles per day
    "cycle_duration": 36 / 60,  # 36 minutes in hours (used for calculations)
    "cycle_duration_input": 36,  # minutes (for UI)
    "days_per_year": 300,  # Operating days
    "grid_cap": 35,  # MW (grid power limit)
}
default_bess_params = {
    "capacity": 40,  # MWh
    "power_max": 20,  # MW
    "rte": 0.98,  # 98% round-trip efficiency
    "cycle_life": 5000,  # cycles
    "cost_per_kwh": 350,  # $/kWh
    "om_cost_per_kwh_year": 15,  # $/kWh/year
}

# --- Helper Functions ---


# Updated version of calculate_eaf_profile that scales with EAF size
def calculate_eaf_profile(time_minutes, eaf_size=100):
    """Calculate EAF power profile for a given time array (in minutes) and EAF size in tons"""
    eaf_power = np.zeros_like(time_minutes)
    # Scale factor based on EAF size (assuming power scales roughly, e.g., EAF size^0.7)
    # Using 0.6 as per the original v2 code
    scale = (eaf_size / 100) ** 0.6

    for i, t in enumerate(time_minutes):
        if t <= 3:  # Bore-in
            eaf_power[i] = (15 + (25 - 15) * (t / 3)) * scale
        elif t <= 17:  # Main melting
            eaf_power[i] = (55 + 5 * np.sin(t * 0.5)) * scale
        elif t <= 20:  # End of melting
            eaf_power[i] = (50 - (50 - 40) * ((t - 17) / 3)) * scale
        else:  # Refining
            eaf_power[i] = (20 + 5 * np.sin(t * 0.3)) * scale
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
            bess_power[i] = 0  # Explicitly set BESS power to 0 when not discharging

    return grid_power, bess_power


def parse_tou_periods(tou_periods_string):
    """Parse TOU periods from string input and validate them"""
    valid_rate_types = {"off_peak", "mid_peak", "peak"}
    tou_list = []
    errors = []

    if not tou_periods_string or not isinstance(tou_periods_string, str):
        errors.append("TOU periods string is empty or invalid.")
        return [], errors

    try:
        periods_data = tou_periods_string.strip().split(";")
        if not periods_data or periods_data == [""]:
            errors.append("No TOU periods provided.")
            return [], errors

        for period in periods_data:
            if not period.strip():
                continue

            parts = period.split(",")
            if len(parts) != 3:
                errors.append(
                    f"Invalid format for period '{period}'. Expected 'start,end,rate_type'"
                )
                continue

            start_str, end_str, rate_type = [p.strip() for p in parts]

            try:
                start = float(start_str)
                end = float(end_str)
            except ValueError:
                errors.append(f"Start and end times must be numbers: '{period}'")
                continue

            if rate_type not in valid_rate_types:
                errors.append(
                    f"Rate type '{rate_type}' must be one of: {', '.join(valid_rate_types)}"
                )
                continue

            if start < 0 or start >= 24 or end <= 0 or end > 24 or start >= end:
                errors.append(
                    f"Invalid time range {start}-{end}. Must be within 0-24 with start < end."
                )
                continue

            tou_list.append((start, end, rate_type))

        if not tou_list and not errors:
            errors.append("No valid TOU periods found after parsing.")
            return [], errors
        if not tou_list:
            return [], errors

        # Sort by start time
        tou_list.sort()

        # Check for gaps and overlaps
        if tou_list[0][0] != 0:
            errors.append("TOU periods must start at hour 0.")
        if tou_list[-1][1] != 24:
            errors.append("TOU periods must end at hour 24.")

        coverage = 0
        for i in range(len(tou_list)):
            coverage += tou_list[i][1] - tou_list[i][0]
            if i > 0 and tou_list[i][0] != tou_list[i - 1][1]:
                errors.append(
                    f"Gap or overlap detected: Period ending at {tou_list[i-1][1]} and period starting at {tou_list[i][0]}."
                )

        # Allow for minor floating point inaccuracies
        if not (23.99 < coverage < 24.01):
            errors.append(
                f"TOU periods do not cover exactly 24 hours (covered {coverage:.2f} hours). Check for gaps or overlaps."
            )

    except Exception as e:
        errors.append(f"Error parsing TOU periods string: {str(e)}")
        # In case of catastrophic parsing error, return empty list
        return [], errors

    return tou_list, errors


def validate_numeric_input(value, name, min_val=None, max_val=None, default=None):
    """Validate numeric input, returning default if invalid or out of range, and generating an error message."""
    error = None
    if value is None:
        return default, f"'{name}' is missing, using default: {default}"

    try:
        num_value = float(value)
        if min_val is not None and num_value < min_val:
            error = f"'{name}' ({num_value}) is below minimum ({min_val}), using default: {default}"
            return default, error
        if max_val is not None and num_value > max_val:
            error = f"'{name}' ({num_value}) is above maximum ({max_val}), using default: {default}"
            return default, error
        return num_value, None  # Return validated value and no error
    except (ValueError, TypeError):
        error = f"'{name}' ({value}) is not a valid number, using default: {default}"
        return default, error


def get_period_colors(tou_periods, max_power_y):
    """Generate colors and annotations for ToU periods"""
    colors = []
    annotations = []
    y_annotation = max_power_y * 0.9  # Place annotation relative to max power

    for start, end, rate in tou_periods:
        color = {
            "off_peak": "rgba(0,0,255,0.1)",
            "mid_peak": "rgba(255,255,0,0.1)",
            "peak": "rgba(255,0,0,0.1)",
        }[rate]

        colors.append(
            {
                "type": "rect",
                "x0": start,
                "x1": end,
                "y0": 0,
                "y1": max_power_y,  # Use dynamic Y axis
                "fillcolor": color,
                "opacity": 0.4,
                "layer": "below",
                "line": {"width": 0},
            }
        )

        annotations.append(
            {
                "x": (start + end) / 2,
                "y": y_annotation,
                "text": rate.replace("_", " ").title(),
                "showarrow": False,
                "font": {"size": 10},
            }
        )

    return colors, annotations


def create_tou_period_row(
    index, start_val=0, end_val=8, rate_val="off_peak", is_first=False
):
    """Helper function to create a row for the TOU period builder UI"""
    return html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            # html.Label("Start Hour:", className="form-label", style={'fontSize':'small'}), # Smaller labels
                            dcc.Input(
                                id={"type": "tou-start", "index": index},
                                type="number",
                                min=0,
                                max=24,
                                step=0.5,
                                value=start_val,
                                className="form-control form-control-sm",  # Smaller input
                                placeholder="Start Hr",
                            ),
                        ],
                        className="col-3",
                    ),
                    html.Div(
                        [
                            # html.Label("End Hour:", className="form-label", style={'fontSize':'small'}),
                            dcc.Input(
                                id={"type": "tou-end", "index": index},
                                type="number",
                                min=0,
                                max=24,
                                step=0.5,
                                value=end_val,
                                className="form-control form-control-sm",  # Smaller input
                                placeholder="End Hr",
                            ),
                        ],
                        className="col-3",
                    ),
                    html.Div(
                        [
                            # html.Label("Rate Type:", className="form-label", style={'fontSize':'small'}),
                            dcc.Dropdown(
                                id={"type": "tou-rate", "index": index},
                                options=[
                                    {
                                        "label": "Off",
                                        "value": "off_peak",
                                    },  # Shorter labels
                                    {"label": "Mid", "value": "mid_peak"},
                                    {"label": "Peak", "value": "peak"},
                                ],
                                value=rate_val,
                                clearable=False,
                                className="form-select form-select-sm",  # Smaller dropdown
                            ),
                        ],
                        className="col-4",
                    ),
                    html.Div(
                        [
                            html.Button(
                                "×",
                                id={"type": "remove-tou", "index": index},
                                className="btn btn-danger btn-sm mt-1",  # Smaller button
                                disabled=is_first,  # Disable remove for the very first row
                            ),
                        ],
                        className="col-2 d-flex align-items-center justify-content-center",
                    ),  # Align button better
                ],
                className="row g-1 mb-1 align-items-center tou-period",
            ),  # Use g-1 for smaller gutters
        ],
        id=f"tou-row-{index}",
    )  # Give the outer Div an ID for removal


# --- App Layout ---
app.layout = html.Div(
    [
        # Store component to hold TOU periods string (acts as intermediary)
        dcc.Store(
            id="tou-periods-store",
            data="0,8,off_peak;8,10,peak;10,16,mid_peak;16,20,peak;20,24,off_peak",
        ),
        html.Div(
            [
                html.H1(
                    "EAF-BESS Peak Shaving Dashboard", className="mb-4 text-center"
                ),
                html.Div(
                    id="error-message-container",
                    className="alert alert-warning",
                    style={"display": "none"},
                ),  # Use warning style
                html.Div(
                    id="validation-error-container",
                    className="alert alert-danger",
                    style={"display": "none"},
                ),  # For validation errors
                # Tabs for parameter groups
                dcc.Tabs(
                    [
                        # System Parameters Tab
                        dcc.Tab(
                            label="System Parameters",
                            children=[
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
                                                        ),  # H4 for subsections
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
                                                    ],
                                                    className="card p-3 mb-4",
                                                ),
                                                # New TOU Period Builder UI
                                                html.Div(
                                                    [
                                                        html.H4(
                                                            "Time-of-Use Periods",
                                                            className="mb-2 d-flex justify-content-between align-items-center",
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Span(
                                                                    "Define 24hr schedule (Start, End, Rate)",
                                                                    className="form-text text-muted",
                                                                ),
                                                                html.Button(
                                                                    "Add Period",
                                                                    id="add-tou-period",
                                                                    n_clicks=0,
                                                                    className="btn btn-success btn-sm mb-2",
                                                                ),
                                                            ],
                                                            className="d-flex justify-content-between align-items-center mb-2",
                                                        ),
                                                        html.Div(
                                                            id="tou-period-container",
                                                            children=[
                                                                # Initial periods will be populated by callback
                                                            ],
                                                        ),
                                                        html.Div(
                                                            id="tou-validation-output",
                                                            className="form-text text-danger mt-1",
                                                        ),  # For TOU validation messages
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
                                                                    value=default_eaf_params[
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
                                                                    "Grid Power Limit (MW):",
                                                                    className="form-label",
                                                                ),
                                                                dcc.Input(
                                                                    id="grid-cap",
                                                                    type="number",
                                                                    value=default_eaf_params[
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
                                                                    value=default_eaf_params[
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
                                                                    value=default_eaf_params[
                                                                        "cycle_duration_input"
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
                                                                    value=default_eaf_params[
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
                                            "Calculate Results",
                                            id="calculate-button",
                                            n_clicks=0,
                                            className="btn btn-primary mt-4 mb-3",
                                        )
                                    ],
                                    className="d-flex justify-content-center",
                                ),
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
                                    className="row",
                                )
                            ],
                        ),
                    ]
                ),
            ],
            className="container py-4",
        ),
    ],
    className="bg-light min-vh-100",
)


# --- Callbacks ---


# Callback to initialize and update TOU period builder UI
@app.callback(
    Output("tou-period-container", "children"),
    Input("tou-periods-store", "data"),  # Triggered by changes in the stored string
)
def initialize_tou_periods(tou_string):
    tou_list, errors = parse_tou_periods(tou_string)
    if not tou_list:
        # Use default if parsing fails or string is empty initially
        tou_list = default_utility_params["tou_periods"]

    # Create UI elements for each period
    period_elements = []
    for i, (start, end, rate) in enumerate(tou_list):
        period_elements.append(
            create_tou_period_row(i, start, end, rate, is_first=(i == 0))
        )

    return period_elements


# Callback to add a new TOU period row
@app.callback(
    Output("tou-periods-store", "data", allow_duplicate=True),  # Update the store
    Output(
        "tou-validation-output", "children", allow_duplicate=True
    ),  # Update validation message
    Input("add-tou-period", "n_clicks"),
    State("tou-periods-store", "data"),  # Get current periods
    State(
        {"type": "tou-start", "index": ALL}, "value"
    ),  # Get values from existing rows
    State({"type": "tou-end", "index": ALL}, "value"),
    State({"type": "tou-rate", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def add_tou_period(n_clicks, current_tou_string, start_times, end_times, rate_types):
    if n_clicks == 0:
        return dash.no_update, dash.no_update  # Prevent update on initial load

    periods = []
    max_index = -1
    # Reconstruct periods from current UI state
    for i in range(len(start_times)):
        # Check if values are not None before processing
        if (
            start_times[i] is not None
            and end_times[i] is not None
            and rate_types[i] is not None
        ):
            periods.append(
                {
                    "start": start_times[i],
                    "end": end_times[i],
                    "rate": rate_types[i],
                    "index": i,  # Keep track of original index if needed, though not strictly necessary here
                }
            )
            max_index = max(max_index, i)  # Find the highest current index

    # Add a new default period
    # Try to make the new period start where the last one ended, if possible
    new_start = periods[-1]["end"] if periods and periods[-1]["end"] < 24 else 0
    new_end = (
        min(new_start + 1, 24) if new_start < 24 else 24
    )  # Default to 1 hour duration
    new_rate = "off_peak"
    new_index = max_index + 1

    periods.append(
        {"start": new_start, "end": new_end, "rate": new_rate, "index": new_index}
    )

    # Sort by start time
    periods.sort(key=lambda x: x["start"])

    # Format as string and validate
    new_tou_string = ";".join(f"{p['start']},{p['end']},{p['rate']}" for p in periods)
    _, errors = parse_tou_periods(new_tou_string)
    error_msg = " | ".join(errors) if errors else ""

    # Update the store, which will trigger the UI update via initialize_tou_periods
    return new_tou_string, error_msg


# Callback to handle removing a TOU period row
@app.callback(
    Output("tou-periods-store", "data", allow_duplicate=True),
    Output("tou-validation-output", "children", allow_duplicate=True),
    Input({"type": "remove-tou", "index": ALL}, "n_clicks"),
    State({"type": "tou-start", "index": ALL}, "value"),
    State({"type": "tou-end", "index": ALL}, "value"),
    State({"type": "tou-rate", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def remove_tou_period(n_clicks_list, start_times, end_times, rate_types):
    ctx = dash.callback_context
    if not ctx.triggered or not any(
        n_clicks > 0 for n_clicks in n_clicks_list if n_clicks
    ):
        return dash.no_update, dash.no_update

    # Find which button was clicked
    button_id_str = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        trigger_index = json.loads(button_id_str)["index"]
    except json.JSONDecodeError:
        return dash.no_update, "Error identifying period to remove."

    periods = []
    # Reconstruct the list of periods *excluding* the one to be removed
    for i in range(len(start_times)):
        # Check if values are not None and index doesn't match the one to remove
        if (
            start_times[i] is not None
            and end_times[i] is not None
            and rate_types[i] is not None
            and i != trigger_index
        ):
            periods.append(
                {
                    "start": start_times[i],
                    "end": end_times[i],
                    "rate": rate_types[i],
                    "index": i,
                }
            )

    # Sort by start time
    periods.sort(key=lambda x: x["start"])

    # Format as string and validate
    new_tou_string = ";".join(f"{p['start']},{p['end']},{p['rate']}" for p in periods)
    _, errors = parse_tou_periods(new_tou_string)
    error_msg = " | ".join(errors) if errors else ""

    # Update the store, which will trigger the UI update
    return new_tou_string, error_msg


# Callback to dynamically update TOU periods string from UI inputs (and validate)
@app.callback(
    Output("tou-periods-store", "data", allow_duplicate=True),
    Output("tou-validation-output", "children", allow_duplicate=True),
    Input({"type": "tou-start", "index": ALL}, "value"),
    Input({"type": "tou-end", "index": ALL}, "value"),
    Input({"type": "tou-rate", "index": ALL}, "value"),
    prevent_initial_call=True,  # Prevent running on load before components exist fully
)
def update_tou_string_and_validate(start_times, end_times, rate_types):
    if (
        not start_times
    ):  # If container is empty (e.g., after removing last item incorrectly)
        return "", "No TOU periods defined."

    periods = []
    # Collect all periods from the UI inputs
    for i in range(len(start_times)):
        if (
            start_times[i] is not None
            and end_times[i] is not None
            and rate_types[i] is not None
        ):
            periods.append(
                {"start": start_times[i], "end": end_times[i], "rate": rate_types[i]}
            )
        # else: # Handle potentially missing inputs if needed, though ALL selector usually prevents this
        # print(f"Warning: Incomplete input for TOU period index {i}")

    # Sort by start time before creating the string
    periods.sort(key=lambda x: x["start"])

    # Format as string
    tou_string = ";".join(f"{p['start']},{p['end']},{p['rate']}" for p in periods)

    # Validate the constructed string
    _, errors = parse_tou_periods(tou_string)
    error_msg = " | ".join(errors) if errors else ""

    return tou_string, error_msg


# --- Main Calculation and Results Callback ---
@app.callback(
    Output("results-output-container", "children"),
    Output("error-message-container", "children"),
    Output("error-message-container", "style"),
    Output("validation-error-container", "children"),
    Output("validation-error-container", "style"),
    Input("calculate-button", "n_clicks"),
    State("tou-periods-store", "data"),  # Use the validated string from the store
    # Utility parameters
    State("off-peak-rate", "value"),
    State("mid-peak-rate", "value"),
    State("peak-rate", "value"),
    State("demand-charge", "value"),
    # EAF parameters
    State("eaf-size", "value"),
    State("grid-cap", "value"),
    State("cycles-per-day", "value"),
    State("cycle-duration", "value"),  # Input is in minutes
    State("days-per-year", "value"),
    # BESS parameters
    State("bess-capacity", "value"),
    State("bess-power", "value"),
    State("bess-rte", "value"),
    State("bess-cycle-life", "value"),
    State("bess-cost-per-kwh", "value"),
    State("bess-om-cost", "value"),
    # Financial parameters
    State("wacc", "value"),
    State("interest-rate", "value"),
    State("debt-fraction", "value"),
    State("project-lifespan", "value"),
    State("tax-rate", "value"),
    State("inflation-rate", "value"),
    State("salvage-value", "value"),
    prevent_initial_call=True,  # Only run when calculate button is clicked
)
def update_results(
    n_clicks,
    tou_periods_string,
    off_peak_rate,
    mid_peak_rate,
    peak_rate,
    demand_charge,
    eaf_size,
    grid_cap,
    cycles_per_day,
    cycle_duration_min,
    days_per_year,
    bess_capacity,
    bess_power,
    bess_rte_percent,
    bess_cycle_life,
    bess_cost_per_kwh,
    bess_om_cost,
    wacc_percent,
    interest_rate_percent,
    debt_fraction_percent,
    project_lifespan,
    tax_rate_percent,
    inflation_rate_percent,
    salvage_value_percent,
):

    if n_clicks == 0:
        return (
            html.Div(
                "Click 'Calculate Results' to generate analysis.",
                className="text-center text-muted mt-4",
            ),
            [],
            {"display": "none"},
            [],
            {"display": "none"},
        )

    # --- Input Validation and Parameter Setup ---
    validation_errors = []
    general_errors = []  # For warnings like battery replacement

    # Validate TOU periods first
    tou_list, tou_errors = parse_tou_periods(tou_periods_string)
    if tou_errors:
        validation_errors.extend(tou_errors)
        # Use default if parsing failed critically
        if not tou_list:
            tou_list = default_utility_params["tou_periods"]
            validation_errors.append("Using default TOU periods due to parsing errors.")

    # Validate and update parameters with user inputs or defaults
    utility_params = {}
    utility_params["off_peak_rate"], err = validate_numeric_input(
        off_peak_rate,
        "Off-Peak Rate",
        min_val=0,
        default=default_utility_params["energy_rates"]["off_peak"],
    )
    if err:
        validation_errors.append(err)
    utility_params["mid_peak_rate"], err = validate_numeric_input(
        mid_peak_rate,
        "Mid-Peak Rate",
        min_val=0,
        default=default_utility_params["energy_rates"]["mid_peak"],
    )
    if err:
        validation_errors.append(err)
    utility_params["peak_rate"], err = validate_numeric_input(
        peak_rate,
        "Peak Rate",
        min_val=0,
        default=default_utility_params["energy_rates"]["peak"],
    )
    if err:
        validation_errors.append(err)
    utility_params["demand_charge"], err = validate_numeric_input(
        demand_charge,
        "Demand Charge",
        min_val=0,
        default=default_utility_params["demand_charge"],
    )
    if err:
        validation_errors.append(err)
    utility_params["tou_periods"] = tou_list  # Already validated

    eaf_params = {}
    eaf_params["eaf_size"], err = validate_numeric_input(
        eaf_size, "EAF Size", min_val=1, default=default_eaf_params["eaf_size"]
    )
    if err:
        validation_errors.append(err)
    eaf_params["grid_cap"], err = validate_numeric_input(
        grid_cap, "Grid Cap", min_val=1, default=default_eaf_params["grid_cap"]
    )
    if err:
        validation_errors.append(err)
    eaf_params["cycles_per_day"], err = validate_numeric_input(
        cycles_per_day,
        "Cycles/Day",
        min_val=1,
        default=default_eaf_params["cycles_per_day"],
    )
    if err:
        validation_errors.append(err)
    cycle_duration_validated, err = validate_numeric_input(
        cycle_duration_min,
        "Cycle Duration",
        min_val=1,
        default=default_eaf_params["cycle_duration_input"],
    )
    if err:
        validation_errors.append(err)
    eaf_params["cycle_duration_hrs"] = (
        cycle_duration_validated / 60.0
    )  # Convert minutes to hours for calculations
    eaf_params["days_per_year"], err = validate_numeric_input(
        days_per_year,
        "Days/Year",
        min_val=1,
        max_val=365,
        default=default_eaf_params["days_per_year"],
    )
    if err:
        validation_errors.append(err)

    bess_params = {}
    bess_params["capacity"], err = validate_numeric_input(
        bess_capacity,
        "BESS Capacity",
        min_val=0.1,
        default=default_bess_params["capacity"],
    )
    if err:
        validation_errors.append(err)
    bess_params["power_max"], err = validate_numeric_input(
        bess_power, "BESS Power", min_val=0.1, default=default_bess_params["power_max"]
    )
    if err:
        validation_errors.append(err)
    bess_rte_validated, err = validate_numeric_input(
        bess_rte_percent,
        "BESS RTE",
        min_val=1,
        max_val=100,
        default=default_bess_params["rte"] * 100,
    )
    if err:
        validation_errors.append(err)
    bess_params["rte"] = bess_rte_validated / 100.0  # Convert percentage to fraction
    bess_params["cycle_life"], err = validate_numeric_input(
        bess_cycle_life,
        "BESS Cycle Life",
        min_val=100,
        default=default_bess_params["cycle_life"],
    )
    if err:
        validation_errors.append(err)
    bess_params["cost_per_kwh"], err = validate_numeric_input(
        bess_cost_per_kwh,
        "BESS Cost/kWh",
        min_val=1,
        default=default_bess_params["cost_per_kwh"],
    )
    if err:
        validation_errors.append(err)
    bess_params["om_cost_per_kwh_year"], err = validate_numeric_input(
        bess_om_cost,
        "BESS O&M Cost",
        min_val=0,
        default=default_bess_params["om_cost_per_kwh_year"],
    )
    if err:
        validation_errors.append(err)

    financial_params = {}
    wacc_validated, err = validate_numeric_input(
        wacc_percent,
        "WACC",
        min_val=0,
        max_val=100,
        default=default_financial_params["wacc"] * 100,
    )
    if err:
        validation_errors.append(err)
    financial_params["wacc"] = wacc_validated / 100.0
    interest_rate_validated, err = validate_numeric_input(
        interest_rate_percent,
        "Interest Rate",
        min_val=0,
        max_val=100,
        default=default_financial_params["interest_rate"] * 100,
    )
    if err:
        validation_errors.append(err)
    financial_params["interest_rate"] = interest_rate_validated / 100.0
    debt_fraction_validated, err = validate_numeric_input(
        debt_fraction_percent,
        "Debt Fraction",
        min_val=0,
        max_val=100,
        default=default_financial_params["debt_fraction"] * 100,
    )
    if err:
        validation_errors.append(err)
    financial_params["debt_fraction"] = debt_fraction_validated / 100.0
    project_lifespan_validated, err = validate_numeric_input(
        project_lifespan,
        "Project Lifespan",
        min_val=1,
        max_val=50,
        default=default_financial_params["project_lifespan"],
    )
    if err:
        validation_errors.append(err)
    financial_params["project_lifespan"] = int(
        project_lifespan_validated
    )  # Ensure integer
    tax_rate_validated, err = validate_numeric_input(
        tax_rate_percent,
        "Tax Rate",
        min_val=0,
        max_val=100,
        default=default_financial_params["tax_rate"] * 100,
    )
    if err:
        validation_errors.append(err)
    financial_params["tax_rate"] = tax_rate_validated / 100.0
    inflation_rate_validated, err = validate_numeric_input(
        inflation_rate_percent,
        "Inflation Rate",
        min_val=0,
        max_val=100,
        default=default_financial_params["inflation_rate"] * 100,
    )
    if err:
        validation_errors.append(err)
    financial_params["inflation_rate"] = inflation_rate_validated / 100.0
    salvage_value_validated, err = validate_numeric_input(
        salvage_value_percent,
        "Salvage Value",
        min_val=0,
        max_val=100,
        default=default_financial_params["salvage_value"] * 100,
    )
    if err:
        validation_errors.append(err)
    financial_params["salvage_value"] = salvage_value_validated / 100.0

    # Display validation errors if any
    if validation_errors:
        error_divs = [html.Div(e) for e in validation_errors]
        return (
            html.Div(
                "Please correct the errors in the parameters and recalculate.",
                className="text-center text-danger mt-4",
            ),
            [],
            {"display": "none"},
            error_divs,
            {"display": "block", "marginBottom": "20px"},
        )

    # --- Core Calculations ---
    # Calculate total BESS cost and O&M cost
    bess_cost = (
        bess_params["capacity"] * 1000 * bess_params["cost_per_kwh"]
    )  # $ (convert MWh to kWh)
    o_m_cost = (
        bess_params["capacity"] * 1000 * bess_params["om_cost_per_kwh_year"]
    )  # $/year (convert MWh to kWh)

    # Single-cycle EAF profile (using a fixed 28-minute profile duration for simulation)
    sim_cycle_duration_min = 28  # Duration of the pre-defined EAF profile
    time_step_min = sim_cycle_duration_min / 200  # Simulation time step in minutes
    time = np.linspace(0, sim_cycle_duration_min, 200)
    eaf_power_cycle = calculate_eaf_profile(
        time, eaf_params["eaf_size"]
    )  # Scale profile
    grid_power_cycle, bess_power_cycle = calculate_grid_bess_power(
        eaf_power_cycle, eaf_params["grid_cap"], bess_params["power_max"]
    )

    # Energy calculations per simulated cycle
    bess_energy_cycle = np.sum(bess_power_cycle) * (
        time_step_min / 60
    )  # MWh discharged per cycle
    grid_energy_cycle = np.sum(grid_power_cycle) * (
        time_step_min / 60
    )  # MWh from grid per cycle
    charge_energy_cycle = (
        bess_energy_cycle / bess_params["rte"]
        if bess_params["rte"] > 0
        else float("inf")
    )  # MWh needed to recharge

    # Check if BESS energy/power is sufficient for the simulated cycle demand
    if bess_energy_cycle > bess_params["capacity"]:
        general_errors.append(
            f"Warning: BESS capacity ({bess_params['capacity']:.1f} MWh) may be insufficient for peak shaving demand per cycle ({bess_energy_cycle:.2f} MWh). Results assume it's sufficient."
        )
    if np.max(bess_power_cycle) > bess_params["power_max"]:
        # This shouldn't happen due to calculate_grid_bess_power logic, but good to check
        general_errors.append(
            f"Warning: Calculated BESS power ({np.max(bess_power_cycle):.1f} MW) exceeds max rating ({bess_params['power_max']:.1f} MW). Check logic."
        )

    # Calculate peak cycles per day based on TOU and BESS/EAF constraints
    peak_hours = sum(
        end - start
        for start, end, rate in utility_params["tou_periods"]
        if rate == "peak"
    )
    # Max cycles based on peak hours available vs actual EAF cycle duration
    max_cycles_from_tou = (
        peak_hours / eaf_params["cycle_duration_hrs"]
        if eaf_params["cycle_duration_hrs"] > 0
        else 0
    )
    # Max cycles based on BESS energy capacity vs energy needed per cycle
    max_cycles_from_bess_energy = (
        bess_params["capacity"] / bess_energy_cycle
        if bess_energy_cycle > 0
        else float("inf")
    )
    # Max cycles based on BESS power limit (less direct, energy is usually the limiter)
    # max_cycles_from_bess_power = bess_params['capacity'] / (bess_params['power_max'] * eaf_params['cycle_duration_hrs']) # Original calc - dimensionally tricky

    # Determine limiting factor for peak cycles, also considering user-defined cycles/day
    # We assume BESS only operates during peak hours for arbitrage/peak shaving
    peak_cycles_per_day = min(
        max_cycles_from_tou, max_cycles_from_bess_energy, eaf_params["cycles_per_day"]
    )

    # Cost savings per cycle (assuming cycle happens during peak rate)
    peak_rate_mwh = utility_params["peak_rate"]
    off_peak_rate_mwh = utility_params[
        "off_peak_rate"
    ]  # Assume charging happens off-peak

    # Cost without BESS: Total EAF energy * peak rate
    eaf_energy_cycle = np.sum(eaf_power_cycle) * (time_step_min / 60)  # MWh
    cost_without_bess = eaf_energy_cycle * peak_rate_mwh

    # Cost with BESS: Grid energy * peak rate + Charging energy * off-peak rate
    cost_with_bess = (grid_energy_cycle * peak_rate_mwh) + (
        charge_energy_cycle * off_peak_rate_mwh
    )
    savings_cycle = cost_without_bess - cost_with_bess

    # Annual savings
    annual_arbitrage_savings = (
        savings_cycle * peak_cycles_per_day * eaf_params["days_per_year"]
    )
    peak_reduction = np.max(eaf_power_cycle) - np.max(
        grid_power_cycle
    )  # Peak reduction in MW
    demand_savings = (
        peak_reduction * 1000 * utility_params["demand_charge"] * 12
    )  # Convert MW to kW for charge calc
    total_annual_savings = annual_arbitrage_savings + demand_savings

    # Battery degradation and replacement costs
    cycles_per_year = peak_cycles_per_day * eaf_params["days_per_year"]
    battery_life_years = float("inf")  # Default to infinite life if no cycling
    if cycles_per_year > 0 and bess_params["cycle_life"] > 0:
        battery_life_years = bess_params["cycle_life"] / cycles_per_year

    battery_replacements = 0
    if battery_life_years < financial_params["project_lifespan"]:
        battery_replacements = np.floor(
            financial_params["project_lifespan"] / battery_life_years
        )  # Number of replacements needed
        general_errors.append(
            f"Note: BESS may need replacement approx. every {battery_life_years:.1f} years ({int(battery_replacements)} replacements projected). Financials include estimated replacement costs."
        )

    # --- Financial Calculations ---
    years = financial_params["project_lifespan"]
    wacc = financial_params["wacc"]
    inflation = financial_params["inflation_rate"]
    tax_rate = financial_params["tax_rate"]
    interest_rate = financial_params["interest_rate"]
    debt_fraction = financial_params["debt_fraction"]
    salvage_fraction = financial_params["salvage_value"]
    salvage_value_end = (
        bess_cost * salvage_fraction
    )  # Salvage value at end of project life

    # Calculate cash flows and financial metrics
    cash_flows = [-bess_cost]  # Year 0: Initial investment
    debt_amount = bess_cost * debt_fraction
    # Simplified interest calculation: Assumes constant interest payment on initial debt amount per year.
    # A more accurate model would track principal repayment.
    annual_interest_payment = debt_amount * interest_rate

    for t in range(1, years + 1):
        # Calculate savings and costs adjusted for inflation
        savings_t = total_annual_savings * (
            (1 + inflation) ** (t - 1)
        )  # Inflate based on previous year
        o_m_cost_t = o_m_cost * ((1 + inflation) ** (t - 1))

        # Calculate replacement cost (inflated) if needed in year t
        replacement_cost_t = 0
        # Replacement occurs *at the end* of the battery life year
        if (
            battery_life_years != float("inf")
            and t > battery_life_years
            and np.floor((t - 1) / battery_life_years)
            > np.floor((t - 2) / battery_life_years)
        ):
            # Replacement needed in this year t (occurs at end of year t-1 relative to start)
            replacement_cost_t = bess_cost * (
                (1 + inflation) ** (t - 1)
            )  # Inflate cost to year t

        # Earnings Before Interest and Tax (EBIT) = Savings - O&M - Replacement
        ebit = savings_t - o_m_cost_t - replacement_cost_t
        # Taxable Income = EBIT - Interest (Interest is tax-deductible)
        taxable_income = ebit - annual_interest_payment
        # Taxes paid
        taxes = taxable_income * tax_rate if taxable_income > 0 else 0
        # Net Operating Profit After Taxes (NOPAT) = EBIT * (1 - Tax Rate) - simplified if interest deduction complexity avoided
        # Net Cash Flow = Savings - O&M - Replacements - Interest - Taxes
        # A common way: Net Cash Flow = (EBIT - Interest)(1 - Tax Rate) + Interest (add back non-cash?) No, stick to:
        # Net Cash Flow = Savings_t - O&M_t - Replacement_t - Interest_t - Taxes
        # Or: Net Cash Flow = (Savings_t - O&M_t - Replacement_t - Interest_t) * (1 - Tax_Rate) if tax applies to net?
        # Let's assume tax applies after interest:
        net_income_before_tax = (
            savings_t - o_m_cost_t - replacement_cost_t - annual_interest_payment
        )
        tax_paid = max(
            0, net_income_before_tax * tax_rate
        )  # Only pay tax if positive income
        net_cash_flow = (
            savings_t
            - o_m_cost_t
            - replacement_cost_t
            - annual_interest_payment
            - tax_paid
        )

        cash_flows.append(net_cash_flow)

    # Add salvage value (after tax) to the final year's cash flow
    # Assume salvage value is taxed if it represents a gain (simplified: tax applied to full salvage)
    salvage_after_tax = salvage_value_end * (1 - tax_rate)
    cash_flows[years] += salvage_after_tax

    # Calculate financial metrics with error handling
    npv = float("nan")
    irr = float("nan")
    try:
        npv = npf.npv(wacc, cash_flows)
    except Exception as e:
        general_errors.append(f"NPV calculation failed: {e}")

    try:
        # Ensure there's at least one positive cash flow after year 0 for IRR
        if any(cf > 0 for cf in cash_flows[1:]):
            irr = npf.irr(cash_flows)
            if irr is None or np.isnan(
                irr
            ):  # Check if IRR calculation itself returned NaN
                irr = float("nan")
                # general_errors.append("IRR calculation resulted in NaN (check cash flows).") # Can be too noisy
        else:
            # general_errors.append("IRR calculation skipped (no positive cash flows after investment).")
            pass  # IRR is undefined or negative infinity if all subsequent flows are negative

    except ValueError as e:
        # npf.irr raises ValueError if no sign change or other issues
        # general_errors.append(f"IRR calculation failed: {e}")
        pass  # Keep IRR as NaN
    except Exception as e:
        general_errors.append(f"IRR calculation failed unexpectedly: {e}")

    # Calculate simple payback period (Years to recover initial investment using avg annual net savings)
    # Using average undiscounted net savings (Savings - O&M - Interest)
    avg_annual_net_savings = 0
    if years > 0:
        # Calculate average annual savings, o&m, interest over the project life (undiscounted)
        avg_savings = (
            sum(
                total_annual_savings * ((1 + inflation) ** (t - 1))
                for t in range(1, years + 1)
            )
            / years
        )
        avg_om = (
            sum(o_m_cost * ((1 + inflation) ** (t - 1)) for t in range(1, years + 1))
            / years
        )
        avg_interest = annual_interest_payment  # Simplified avg interest
        avg_annual_net_savings = avg_savings - avg_om - avg_interest

    payback_years = float("inf")
    if avg_annual_net_savings > 0:
        payback_years = bess_cost / avg_annual_net_savings

    # Calculate TCO (Total Cost of Ownership) - Discounted costs over lifespan
    tco = bess_cost  # Initial cost
    for t in range(1, years + 1):
        o_m_cost_t_discounted = (o_m_cost * ((1 + inflation) ** (t - 1))) / (
            (1 + wacc) ** t
        )
        interest_t_discounted = annual_interest_payment / (
            (1 + wacc) ** t
        )  # Discount interest cost
        replacement_cost_t_discounted = 0
        if (
            battery_life_years != float("inf")
            and t > battery_life_years
            and np.floor((t - 1) / battery_life_years)
            > np.floor((t - 2) / battery_life_years)
        ):
            replacement_cost_t = bess_cost * (
                (1 + inflation) ** (t - 1)
            )  # Inflate cost to year t
            replacement_cost_t_discounted = replacement_cost_t / ((1 + wacc) ** t)

        # Should interest be part of TCO? Often it is. Assume yes.
        tco += (
            o_m_cost_t_discounted
            + interest_t_discounted
            + replacement_cost_t_discounted
        )

    # Subtract discounted salvage value
    tco -= salvage_after_tax / ((1 + wacc) ** years)

    # --- Generate Plots ---
    # Single-cycle plot
    max_y_single = (
        max(np.max(eaf_power_cycle), eaf_params["grid_cap"]) * 1.15
        if len(eaf_power_cycle) > 0
        else 60
    )
    single_fig = go.Figure()
    # Add phase background shapes (relative to max Y)
    shapes_single = [
        dict(
            type="rect",
            x0=0,
            x1=3,
            y0=0,
            y1=max_y_single,
            fillcolor="rgba(255,255,0,0.2)",
            layer="below",
            line=dict(width=0),
        ),
        dict(
            type="rect",
            x0=3,
            x1=17,
            y0=0,
            y1=max_y_single,
            fillcolor="rgba(0,255,0,0.2)",
            layer="below",
            line=dict(width=0),
        ),
        dict(
            type="rect",
            x0=17,
            x1=20,
            y0=0,
            y1=max_y_single,
            fillcolor="rgba(255,165,0,0.2)",
            layer="below",
            line=dict(width=0),
        ),
        dict(
            type="rect",
            x0=20,
            x1=sim_cycle_duration_min,
            y0=0,
            y1=max_y_single,
            fillcolor="rgba(255,0,0,0.2)",
            layer="below",
            line=dict(width=0),
        ),
    ]
    annotations_single = [  # Place annotations relative to max Y
        dict(
            x=1.5,
            y=max_y_single * 0.95,
            text="Bore-in",
            showarrow=False,
            font=dict(color="black", size=10),
        ),
        dict(
            x=10,
            y=max_y_single * 0.95,
            text="Main Melt",
            showarrow=False,
            font=dict(color="black", size=10),
        ),
        dict(
            x=18.5,
            y=max_y_single * 0.95,
            text="End Melt",
            showarrow=False,
            font=dict(color="black", size=10),
        ),
        dict(
            x=(20 + sim_cycle_duration_min) / 2,
            y=max_y_single * 0.95,
            text="Refining",
            showarrow=False,
            font=dict(color="black", size=10),
        ),
    ]
    single_fig.add_trace(
        go.Scatter(
            x=time,
            y=eaf_power_cycle,
            mode="lines",
            name="EAF Power (No BESS)",
            line=dict(color="blue", width=2),
        )
    )
    single_fig.add_trace(
        go.Scatter(
            x=time,
            y=grid_power_cycle,
            mode="lines",
            name="Grid Power (W/ BESS)",
            line=dict(color="green", width=2),
        )
    )
    single_fig.add_trace(
        go.Scatter(
            x=time,
            y=bess_power_cycle,
            mode="lines",
            name="BESS Output",
            line=dict(color="red", width=2),
            fill="tozeroy",
        )
    )
    # Add grid cap line
    single_fig.add_shape(
        type="line",
        x0=0,
        y0=eaf_params["grid_cap"],
        x1=sim_cycle_duration_min,
        y1=eaf_params["grid_cap"],
        line=dict(color="black", width=2, dash="dash"),
    )
    single_fig.add_annotation(
        x=sim_cycle_duration_min * 0.8,
        y=eaf_params["grid_cap"] + max_y_single * 0.03,
        text=f"Grid Cap: {eaf_params['grid_cap']} MW",
        showarrow=False,
        font=dict(color="black", size=10),
    )
    single_fig.update_layout(
        title=f'Simulated EAF Cycle ({eaf_params["eaf_size"]}-ton Furnace, {sim_cycle_duration_min}-min Profile)',
        xaxis_title="Time (minutes)",
        yaxis_title="Power (MW)",
        showlegend=True,
        hovermode="x unified",
        template="plotly_white",
        shapes=shapes_single,
        annotations=annotations_single,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=40, r=20),  # Adjust margins
    )
    single_fig.update_yaxes(range=[0, max_y_single])

    # Daily schedule plot
    daily_time = np.linspace(0, 24, 1000)  # Higher resolution for daily plot
    daily_eaf_power = np.zeros_like(daily_time)
    # Simulate EAF cycles based on user's actual cycle duration
    actual_cycle_length_hrs = eaf_params["cycle_duration_hrs"]
    if actual_cycle_length_hrs > 0:
        # Distribute cycles evenly over 24 hours? Or assume they run back-to-back? Assume back-to-back for simplicity.
        num_daily_cycles = int(eaf_params["cycles_per_day"])  # Use the parameter value
        current_time_hrs = 0
        for _ in range(num_daily_cycles):
            if current_time_hrs + actual_cycle_length_hrs <= 24:
                start_idx = np.searchsorted(daily_time, current_time_hrs, side="left")
                end_idx = np.searchsorted(
                    daily_time, current_time_hrs + actual_cycle_length_hrs, side="left"
                )
                # Interpolate the simulated profile (28 min) onto the actual cycle duration within the daily timeline
                sim_times = np.linspace(
                    0, sim_cycle_duration_min, len(daily_time[start_idx:end_idx])
                )
                interp_power = np.interp(sim_times, time, eaf_power_cycle)
                daily_eaf_power[start_idx:end_idx] = interp_power
                current_time_hrs += actual_cycle_length_hrs
            else:
                break  # Stop if next cycle exceeds 24 hours

    # Calculate the corresponding daily grid and BESS power
    daily_grid_power, daily_bess_power = calculate_grid_bess_power(
        daily_eaf_power, eaf_params["grid_cap"], bess_params["power_max"]
    )
    # Create daily schedule figure
    daily_fig = go.Figure()
    max_y_daily = (
        max(np.max(daily_eaf_power), eaf_params["grid_cap"]) * 1.15
        if len(daily_eaf_power) > 0
        else 60
    )
    # Add ToU period shapes and annotations
    shapes_daily, annotations_daily = get_period_colors(
        utility_params["tou_periods"], max_y_daily
    )
    daily_fig.add_trace(
        go.Scatter(
            x=daily_time,
            y=daily_eaf_power,
            mode="lines",
            name="EAF Power",
            line=dict(color="blue", width=1.5),
        )
    )
    daily_fig.add_trace(
        go.Scatter(
            x=daily_time,
            y=daily_grid_power,
            mode="lines",
            name="Grid Power",
            line=dict(color="green", width=1.5),
        )
    )
    daily_fig.add_trace(
        go.Scatter(
            x=daily_time,
            y=daily_bess_power,
            mode="lines",
            name="BESS Output",
            line=dict(color="red", width=1.5),
            fill="tozeroy",
        )
    )
    daily_fig.add_shape(
        type="line",
        x0=0,
        y0=eaf_params["grid_cap"],
        x1=24,
        y1=eaf_params["grid_cap"],
        line=dict(color="black", width=2, dash="dash"),
    )
    daily_fig.update_layout(
        title="Simulated Daily Power Profile with ToU Periods",
        xaxis_title="Time (hours)",
        yaxis_title="Power (MW)",
        showlegend=True,
        template="plotly_white",
        shapes=shapes_daily,
        annotations=annotations_daily,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=40, r=20),  # Adjust margins
    )
    daily_fig.update_yaxes(range=[0, max_y_daily])
    daily_fig.update_xaxes(
        range=[0, 24], tickvals=list(range(0, 25, 2))
    )  # Ticks every 2 hours

    # --- Format Results ---
    # Create economic results display using cards
    results_layout = html.Div(
        [
            html.Div(
                [  # Row for plots
                    html.Div(
                        [
                            html.H4("Single-Cycle Plot", className="mt-4 text-center"),
                            dcc.Graph(figure=single_fig),
                        ],
                        className="col-md-12 mb-4",
                    ),
                    html.Div(
                        [
                            html.H4(
                                "Daily Schedule Plot", className="mt-2 text-center"
                            ),
                            dcc.Graph(figure=daily_fig),
                        ],
                        className="col-md-12 mb-4",
                    ),
                ],
                className="row",
            ),
            html.Hr(),
            html.H4("Economic Results", className="mt-2 text-center"),
            html.Div(
                [  # Row for results cards
                    # Left column for results
                    html.Div(
                        [
                            # System Parameters Summary Card
                            html.Div(
                                [
                                    html.H5(
                                        "System Summary",
                                        className="card-header bg-secondary text-white",
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                [
                                                    html.Strong("EAF Size: "),
                                                    f"{eaf_params['eaf_size']} tons",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong("BESS: "),
                                                    f"{bess_params['capacity']:.1f} MWh / {bess_params['power_max']:.1f} MW",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong("Grid Capacity: "),
                                                    f"{eaf_params['grid_cap']} MW",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong("Est. Battery Life: "),
                                                    f"{battery_life_years:.1f} years ({bess_params['cycle_life']} cycles)",
                                                ]
                                            ),
                                        ],
                                        className="card-body",
                                    ),
                                ],
                                className="card mb-4",
                            ),
                            # Energy Analysis Card
                            html.Div(
                                [
                                    html.H5(
                                        "Energy Analysis (Per Cycle)",
                                        className="card-header bg-primary text-white",
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "BESS Energy Discharged: "
                                                    ),
                                                    f"{bess_energy_cycle:.2f} MWh",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong("Grid Energy Used: "),
                                                    f"{grid_energy_cycle:.2f} MWh",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Est. Charging Energy Needed: "
                                                    ),
                                                    f"{charge_energy_cycle:.2f} MWh",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Peak Reduction Achieved: "
                                                    ),
                                                    f"{peak_reduction:.2f} MW",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Peak Cycles per Day (Utilized): "
                                                    ),
                                                    f"{peak_cycles_per_day:.2f}",
                                                ]
                                            ),
                                        ],
                                        className="card-body",
                                    ),
                                ],
                                className="card mb-4",
                            ),
                        ],
                        className="col-md-6",
                    ),
                    # Right column for results
                    html.Div(
                        [
                            # Savings Analysis Card
                            html.Div(
                                [
                                    html.H5(
                                        "Savings Analysis (Annual)",
                                        className="card-header bg-success text-white",
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Savings per Peak Cycle: "
                                                    ),
                                                    f"${savings_cycle:.2f}",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Annual Arbitrage Savings: "
                                                    ),
                                                    f"${annual_arbitrage_savings:,.2f}",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Annual Demand Charge Savings: "
                                                    ),
                                                    f"${demand_savings:,.2f}",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Total Gross Annual Savings: "
                                                    ),
                                                    f"${total_annual_savings:,.2f}",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Avg. Net Annual Savings (Undisc.): "
                                                    ),
                                                    f"${avg_annual_net_savings:,.2f}",
                                                ]
                                            ),
                                        ],
                                        className="card-body",
                                    ),
                                ],
                                className="card mb-4",
                            ),
                            # Financial Metrics Card
                            html.Div(
                                [
                                    html.H5(
                                        "Financial Metrics",
                                        className="card-header bg-info text-white",
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                [
                                                    html.Strong("BESS Initial Cost: "),
                                                    f"${bess_cost:,.2f} (${bess_params['cost_per_kwh']:.0f}/kWh)",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Annual O&M Cost (Year 1): "
                                                    ),
                                                    f"${o_m_cost:,.2f}",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Net Present Value (NPV): "
                                                    ),
                                                    (
                                                        html.Span(
                                                            f"${npv:,.2f}",
                                                            className=(
                                                                "fw-bold text-success"
                                                                if not np.isnan(npv)
                                                                and npv > 0
                                                                else "fw-bold text-danger"
                                                            ),
                                                        )
                                                        if not np.isnan(npv)
                                                        else "N/A"
                                                    ),
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Internal Rate of Return (IRR): "
                                                    ),
                                                    (
                                                        html.Span(
                                                            f"{irr*100:.2f}%",
                                                            className="fw-bold",
                                                        )
                                                        if not np.isnan(irr)
                                                        else "N/A"
                                                    ),
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Simple Payback Period: "
                                                    ),
                                                    (
                                                        f"{payback_years:.2f} years"
                                                        if payback_years != float("inf")
                                                        else "N/A (No Payback)"
                                                    ),
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Total Cost of Ownership (TCO): "
                                                    ),
                                                    f"${tco:,.2f}",
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Projected Replacements: "
                                                    ),
                                                    f"{int(battery_replacements)}",
                                                ]
                                            ),
                                        ],
                                        className="card-body",
                                    ),
                                ],
                                className="card mb-4",
                            ),
                            # Investment Summary Card (moved inside right column)
                            html.Div(
                                [
                                    html.H5(
                                        "Investment Summary",
                                        className="card-header bg-warning",
                                    ),
                                    html.Div(
                                        [
                                            html.P(
                                                [
                                                    html.Strong("Viability (@ WACC): "),
                                                    (
                                                        html.Span(
                                                            "Economically Viable",
                                                            className="text-success fw-bold",
                                                        )
                                                        if not np.isnan(npv) and npv > 0
                                                        else html.Span(
                                                            "Not Economically Viable",
                                                            className="text-danger fw-bold",
                                                        )
                                                    ),
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Risk Level (Heuristic): "
                                                    ),
                                                    (
                                                        html.Span(
                                                            "Low",
                                                            className="text-success",
                                                        )
                                                        if not np.isnan(irr)
                                                        and not np.isnan(wacc)
                                                        and payback_years < years / 2
                                                        and irr > wacc * 1.5
                                                        else (
                                                            html.Span(
                                                                "Medium",
                                                                className="text-warning",
                                                            )
                                                            if not np.isnan(irr)
                                                            and not np.isnan(wacc)
                                                            and payback_years < years
                                                            and irr > wacc
                                                            else html.Span(
                                                                "High",
                                                                className="text-danger",
                                                            )
                                                        )
                                                    ),
                                                ]
                                            ),
                                            html.P(
                                                [
                                                    html.Strong(
                                                        "Primary Benefit Driver: "
                                                    ),
                                                    f"{'Demand Charge Reduction' if demand_savings > annual_arbitrage_savings else 'Energy Arbitrage Savings'}",
                                                ]
                                            ),
                                        ],
                                        className="card-body",
                                    ),
                                ],
                                className="card",
                            ),
                        ],
                        className="col-md-6",
                    ),
                ],
                className="row",
            ),
        ]
    )

    # Prepare error message display
    error_display_style = (
        {"display": "block", "marginBottom": "20px"}
        if general_errors
        else {"display": "none"}
    )
    error_divs = [html.Div(e) for e in general_errors]

    # Return results layout and error info
    return (
        results_layout,
        error_divs,
        error_display_style,
        [],
        {"display": "none"},
    )  # Clear validation errors on successful run


# --- Run Server ---
if __name__ == "__main__":
    # You might also want to let Render set the port via environment variable
    import os
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port) # Removed debug=True