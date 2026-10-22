
import sqlite3
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------- CONFIGURATION ----------------
st.set_page_config(
    page_title="ChargeWise",
    page_icon="⚡",
    layout="wide"
)

DB = Path(__file__).with_name("chargewise.db")
STEP_HOURS = 0.25
MAX_VEHICLE_KW = 6.6


# ---------------- DATABASE ----------------
def connect_db():
    return sqlite3.connect(DB)


def init_db():
    with connect_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                vehicle TEXT NOT NULL,
                arrival INTEGER NOT NULL,
                departure INTEGER NOT NULL,
                energy REAL NOT NULL,
                max_kw REAL NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
        """)

        for username, password, role in [
            ("driver", "driver123", "User"),
            ("admin", "admin123", "Admin")
        ]:
            con.execute(
                "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
                (username, hashlib.sha256(
                    password.encode()).hexdigest(), role)
            )

        count = con.execute(
            "SELECT COUNT(*) FROM vehicles"
        ).fetchone()[0]

        if count == 0:
            samples = [
                ("driver", "EV-101", 8, 17, 20, 6.6),
                ("driver", "EV-102", 9, 16, 15, 6.6),
                ("Alex", "EV-103", 8, 15, 18, 6.6),
                ("Sam", "EV-104", 10, 18, 12, 6.6),
                ("Riya", "EV-105", 11, 17, 16, 6.6),
            ]
            con.executemany("""
                INSERT INTO vehicles
                (owner, vehicle, arrival, departure, energy, max_kw)
                VALUES (?, ?, ?, ?, ?, ?)
            """, samples)


init_db()


def get_vehicles():
    with connect_db() as con:
        return pd.read_sql_query(
            "SELECT * FROM vehicles ORDER BY id DESC", con
        )


def add_vehicle(owner, vehicle, arrival, departure, energy, max_kw):
    with connect_db() as con:
        con.execute("""
            INSERT INTO vehicles
            (owner, vehicle, arrival, departure, energy, max_kw)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (owner, vehicle, arrival, departure, energy, max_kw))


# ---------------- SCHEDULER ----------------
def simulate(df, site_limit, smart=True):
    """Simulate 24 hours in 15-minute intervals."""
    times = np.arange(0, 24, STEP_HOURS)
    power = np.zeros(len(times))
    delivered = {int(row.id): 0.0 for row in df.itertuples()}
    remaining = {
        int(row.id): float(row.energy) for row in df.itertuples()
    }
    session_power = {
        int(row.id): np.zeros(len(times)) for row in df.itertuples()
    }

    for i, hour in enumerate(times):
        available = df[
            (df["arrival"] <= hour) &
            (df["departure"] > hour)
        ]

        if smart:
            # Earliest-departure-first priority
            available = available.sort_values(
                ["departure", "arrival"]
            )

        for row in available.itertuples():
            vid = int(row.id)

            if smart:
                room = max(0.0, site_limit - power[i])
                needed_kw = remaining[vid] / STEP_HOURS
                kw = min(float(row.max_kw), needed_kw, room)
            else:
                # Baseline: charges immediately without site-cap control
                needed_kw = remaining[vid] / STEP_HOURS
                kw = min(float(row.max_kw), needed_kw)

            if kw > 0:
                power[i] += kw
                energy = kw * STEP_HOURS
                delivered[vid] += energy
                remaining[vid] = max(0.0, remaining[vid] - energy)
                session_power[vid][i] = kw

    result = pd.DataFrame({
        "Hour": times,
        "Uncontrolled (kW)": np.zeros(len(times))
    })

    return power, delivered, remaining, session_power, times


def run_comparison(df, limit):
    base_power, base_delivered, base_remaining, _, times = simulate(
        df, limit, smart=False
    )
    smart_power, smart_delivered, smart_remaining, smart_sessions, _ = (
        simulate(df, limit, smart=True)
    )

    chart = pd.DataFrame({
        "Hour": times,
        "Uncontrolled charging": base_power,
        "Smart scheduling": smart_power
    })

    base_peak = float(base_power.max()) if len(base_power) else 0
    smart_peak = float(smart_power.max()) if len(smart_power) else 0

    requested = float(df["energy"].sum())
    smart_energy = float(sum(smart_delivered.values()))
    base_energy = float(sum(base_delivered.values()))

    details = df[[
        "id", "owner", "vehicle", "arrival", "departure", "energy"
    ]].copy()
    details["Smart energy delivered (kWh)"] = details["id"].map(
        smart_delivered
    )
    details["Unmet energy (kWh)"] = details["id"].map(
        smart_remaining
    )
    details["Status"] = np.where(
        details["Unmet energy (kWh)"] < 0.01,
        "Requirement met", "Partially served"
    )

    return {
        "chart": chart,
        "base_peak": base_peak,
        "smart_peak": smart_peak,
        "base_energy": base_energy,
        "smart_energy": smart_energy,
        "requested": requested,
        "details": details,
        "base_power": base_power,
        "smart_power": smart_power,
        "times": times,
    }


# ---------------- STYLING ----------------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #edf4ff, #f7efff, #effff8);
}
h1, h2, h3 { color: #344b85; }
div.stButton > button {
    border-radius: 10px;
    min-height: 42px;
}
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.8);
    padding: 15px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("⚡ ChargeWise")
st.sidebar.caption("Workplace EV Charging Scheduler")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""


# ---------------- LOGIN ----------------
st.title("⚡ ChargeWise")
st.caption("Smarter Charging. Lower Peak Demand.")

if not st.session_state.logged_in:
    st.subheader("Welcome to ChargeWise")
    st.write(
        "Coordinate workplace electric vehicle charging, "
        "respect the site's power limit, and track energy delivery."
    )

    login_tab, demo_tab = st.tabs(["Login", "Demo accounts"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            password_hash = hashlib.sha256(
                password.encode()
            ).hexdigest()

            with connect_db() as con:
                account = con.execute("""
                    SELECT username, role FROM users
                    WHERE username=? AND password_hash=?
                """, (username, password_hash)).fetchone()

            if account:
                st.session_state.logged_in = True
                st.session_state.username = account[0]
                st.session_state.role = account[1]
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with demo_tab:
        st.info(
            "Driver demo: username `driver`, password `driver123`\n\n"
            "Admin demo: username `admin`, password `admin123`"
        )

    st.stop()


# ---------------- NAVIGATION ----------------
role = st.session_state.role
username = st.session_state.username

st.sidebar.success(f"{role}: {username}")

if role == "Admin":
    page_options = [
        "Dashboard", "Vehicle Management", "Charging Simulation"
    ]
else:
    page_options = ["My Dashboard", "Register Vehicle"]

page = st.sidebar.radio("Navigation", page_options)

if st.sidebar.button("Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

vehicles = get_vehicles()

if role == "User":
    vehicles = vehicles[vehicles["owner"] == username]


# ---------------- USER PAGES ----------------
if page == "My Dashboard":
    st.header("👤 Driver Dashboard")
    st.write(f"Welcome, **{username}**!")

    st.metric("Registered vehicles", len(vehicles))
    if not vehicles.empty:
        st.dataframe(
            vehicles[[
                "vehicle", "arrival", "departure", "energy", "max_kw"
            ]],
            use_container_width=True,
            hide_index=True
        )
        st.caption(
            "Arrival and departure use 24-hour clock hours. "
            "Example: 8 means 8:00 AM."
        )
    else:
        st.info("Register a vehicle to get started.")

elif page == "Register Vehicle":
    st.header("🚘 Register a Vehicle")
    st.write("Enter your vehicle's charging requirements.")

    with st.form("vehicle_form"):
        vehicle = st.text_input("Vehicle ID", placeholder="EV-201")
        arrival = st.number_input(
            "Arrival hour (0–23)", min_value=0, max_value=23, value=8
        )
        departure = st.number_input(
            "Departure hour (1–24)", min_value=1, max_value=24, value=17
        )
        energy = st.number_input(
            "Required energy (kWh)", min_value=1.0, max_value=150.0,
            value=20.0, step=1.0
        )
        max_kw = st.selectbox(
            "Maximum charging power", [3.3, 6.6, 7.2, 11.0]
        )
        saved = st.form_submit_button("Save Vehicle")

    if saved:
        if not vehicle.strip():
            st.error("Enter a vehicle ID.")
        elif departure <= arrival:
            st.error("Departure must be after arrival.")
        else:
            add_vehicle(
                username, vehicle.strip(), int(arrival), int(departure),
                float(energy), float(max_kw)
            )
            st.success("Vehicle saved to the SQLite database!")
            st.rerun()


# ---------------- ADMIN PAGES ----------------
elif page == "Dashboard":
    st.header("📊 Admin Dashboard")
    st.write("Overview of registered EV charging requirements.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Vehicles", len(vehicles))
    c2.metric(
        "Requested energy",
        f"{vehicles['energy'].sum():.1f} kWh" if not vehicles.empty else "0 kWh"
    )
    c3.metric("Site power limit", "20 kW")

    if not vehicles.empty:
        st.dataframe(vehicles, use_container_width=True, hide_index=True)
    else:
        st.info("No vehicles registered yet.")

elif page == "Vehicle Management":
    st.header("🚗 Vehicle Management")
    st.write("View and manage all charging sessions.")

    if vehicles.empty:
        st.info("No vehicles found.")
    else:
        st.dataframe(vehicles, use_container_width=True, hide_index=True)
        csv = vehicles.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download vehicle data (CSV)",
            csv,
            file_name="chargewise_vehicles.csv",
            mime="text/csv"
        )

        selected_id = st.selectbox(
            "Select vehicle record ID to delete",
            vehicles["id"].astype(int).tolist()
        )
        if st.button("Delete selected record"):
            with connect_db() as con:
                con.execute(
                    "DELETE FROM vehicles WHERE id=?", (int(selected_id),)
                )
            st.success("Vehicle record deleted.")
            st.rerun()

elif page == "Charging Simulation":
    st.header("⚡ Smart Charging Simulation")
    st.write(
        "Compare uncontrolled charging against earliest-departure-first "
        "scheduling under a shared site power limit."
    )

    site_limit = st.slider(
        "Maximum site power (kW)", 5, 100, 20, step=5
    )

    if vehicles.empty:
        st.warning("Add vehicle sessions before running the simulation.")
    else:
        results = run_comparison(vehicles, site_limit)
        chart = results["chart"]

        peak_reduction = (
            (results["base_peak"] - results["smart_peak"])
            / results["base_peak"] * 100
            if results["base_peak"] > 0 else 0
        )
        fulfillment = (
            results["smart_energy"] / results["requested"] * 100
            if results["requested"] > 0 else 100
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Uncontrolled peak", f"{results['base_peak']:.1f} kW")
        m2.metric("Smart peak", f"{results['smart_peak']:.1f} kW")
        m3.metric("Peak reduction", f"{peak_reduction:.1f}%")
        m4.metric("Energy fulfilled", f"{fulfillment:.1f}%")

        st.subheader("Power Demand Comparison")
        fig = px.line(
            chart, x="Hour",
            y=["Uncontrolled charging", "Smart scheduling"],
            labels={"value": "Power (kW)", "Hour": "Hour of day"},
            title="Site power demand over 24 hours"
        )
        fig.add_hline(
            y=site_limit, line_dash="dash",
            annotation_text="Site power limit"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Energy Fulfilment by Vehicle")
        st.dataframe(
            results["details"], use_container_width=True, hide_index=True
        )

        st.caption(
            "The uncontrolled baseline can exceed the site power limit. "
            "Smart scheduling respects the limit; unmet energy is reported "
            "when available charging time or capacity is insufficient."
        )

        st.subheader("Download Results")
        st.download_button(
            "Download simulation results (CSV)",
            results["details"].to_csv(index=False).encode("utf-8"),
            file_name="chargewise_simulation.csv",
            mime="text/csv"
        )

st.divider()
st.caption(
    "ChargeWise | Workplace EV Charging Scheduler | "
    "Educational prototype — demo credentials only"
)
