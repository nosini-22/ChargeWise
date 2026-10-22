
# ⚡ ChargeWise — Workplace EV Charging Scheduler

## Overview
ChargeWise is a workplace electric vehicle charging application that compares uncontrolled charging with smart scheduling under a shared site power limit.

## Features
- Separate demo login for drivers and administrators
- Register and manage EV charging sessions
- SQLite database for storing vehicle records
- Earliest-departure-first smart charging simulation
- Adjustable site power limit
- Uncontrolled versus smart charging comparison
- Peak demand reduction and energy fulfilment metrics
- Interactive power demand chart
- CSV export of simulation results

## Technologies
- Python
- Streamlit
- SQLite
- Pandas and NumPy
- Plotly
- pytest

## Run Locally
1. Install Python 3.11 or newer.
2. Install dependencies:

   `pip install -r requirements.txt`

3. Start the application:

   `streamlit run app.py`

4. Open the local URL shown in the terminal.

## Demo Login
- Driver: `driver` / `driver123`
- Admin: `admin` / `admin123`

These credentials are for local demonstration only.

## Limitations
This is a prototype using sample vehicle sessions. The current simulation uses a 24-hour horizon and a basic earliest-departure-first scheduling policy. The results depend on the registered sessions and site power limit.
