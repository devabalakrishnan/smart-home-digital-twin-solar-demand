import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np
from datetime import datetime

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_signal(topic, command):
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.publish(topic, command, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 2. DATA ENGINE ---
@st.cache_data
def load_and_prep_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p, df_s = pd.read_csv(p_path), pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df_p['solar_gen'] = df_s['Generation (kW)'] #
        
        for col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in apps if c in df_p.columns]
        df_p['total_demand'] = df_p[existing_apps].sum(axis=1)
        return df_p, existing_apps
    return None, []

if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_and_prep_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="Autonomous Digital Twin", layout="wide")
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # --- SECTION A: CURRENT STATUS (REAL-TIME) ---
    st.subheader(f"🕒 Current Status (Syncing Hour {idx}:00)")
    
    grid_now = row['total_demand'] - row['solar_gen']
    eff_now = (min(row['solar_gen'], row['total_demand'])/row['total_demand']*100 if row['total_demand']>0 else 100)
    co2_now = min(row['solar_gen'], row['total_demand']) * 0.4
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar Gen", f"{row['solar_gen']:.2f} kW")
    c3.metric("Grid Interaction", f"{abs(grid_now):.2f} kW", delta="Buying" if grid_now > 0 else "Exporting", delta_color="inverse")
    c4.metric("Live Efficiency", f"{eff_now:.1f}%")
    c5.metric("Instant CO2 Saved", f"{co2_now:.3f} kg")

    st.divider()

    # --- SECTION B: OVERALL VALUES (DAILY CUMULATIVE) ---
    st.subheader("📊 Overall Daily Performance")
    
    total_solar = df['solar_gen'].sum()
    total_demand = df['total_demand'].sum()
    cumulative_co2 = np.minimum(df['solar_gen'], df['total_demand']).sum() * 0.4
    avg_efficiency = (np.minimum(df['solar_gen'], df['total_demand']).sum() / total_demand * 100)
    
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Total Daily Demand", f"{total_demand:.2f} kWh")
    o2.metric("Total Solar Forecast", f"{total_solar:.2f} kWh")
    o3.metric("Daily Efficiency", f"{avg_efficiency:.1f}%")
    o4.metric("Total CO2 Offset", f"{cumulative_co2:.2f} kg", delta="Target Reached")

    st.divider()

    # --- SECTION C: APPLIANCE STATUS & XAI ---
    col_table, col_xai = st.columns([1, 1])

    with col_table:
        st.subheader("🔌 ESP32 Appliance Control")
        status_data = []
        for app in app_list:
            is_on = row[app] > 0
            status_data.append({"Appliance": app, "Status": "🟢 ON" if is_on else "🔴 OFF", "Load (kW)": f"{row[app]:.2f}"})
            
            # Autonomous Signal to HiveMQ
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            send_mqtt_signal(topic, "ON" if is_on else "OFF")
        st.table(pd.DataFrame(status_data))

    with col_xai:
        st.subheader("🔍 XAI: PPO Decision Factors")
        weights = {'Electricity Price': 1.2, 'Solar Forecast': 0.9, 'Occupancy': 0.4, 'Total Demand': 0.2} #
        st.bar_chart(pd.DataFrame(list(weights.items()), columns=['Factor', 'Weight']).set_index('Factor'))
        
        # Decision logic reasoning
        if row['solar_gen'] > row['total_demand']:
            st.success("**AI Logic:** High Solar Priority - Activating heavy loads.")
        else:
            st.warning("**AI Logic:** Grid Optimization - Shedding non-essential loads.")

    # --- 4. AUTONOMOUS SYNC LOOP ---
    time.sleep(4) 
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun() # Refresh all metrics and clocks

else:
    st.error("🚨 Missing data files in /data directory.")
