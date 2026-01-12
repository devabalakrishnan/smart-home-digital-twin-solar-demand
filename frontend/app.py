import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir" # Ensure lowercase 'l'

# Initialize MQTT
if 'mqtt_client' not in st.session_state:
    client = mqtt.Client(client_id="DigitalTwin_Energy_Hub", transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception:
        st.session_state.connected = False

# --- 2. DATA LOADING & CALCULATIONS ---
@st.cache_data
def load_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df = pd.read_csv(p_path)
        df_s = pd.read_csv(s_path)
        df['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        for col in apps:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df['total_demand'] = df[apps].sum(axis=1)
        return df, apps
    return None, []

df, app_list = load_data()

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="Home Energy Twin", layout="wide")
st.title("🏡 Smart Home Energy Hub")

if df is not None:
    if 'current_hr' not in st.session_state: st.session_state.current_hr = 0
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]

    # --- ENERGY METRICS SECTION ---
    net_load = row['total_demand'] - row['solar_gen']
    grid_action = "Selling 🟢" if net_load < 0 else "Buying 🔴"
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Demand (Current)", f"{row['total_demand']:.2f} kW")
        st.metric("Demand (Net Avg)", f"{df['total_demand'].mean():.2f} kW")
    with c2:
        st.metric("Solar (Current)", f"{row['solar_gen']:.2f} kW")
        st.metric("Solar (Net Avg)", f"{df['solar_gen'].mean():.2f} kW")
    with c3:
        st.metric("Net Load", f"{abs(net_load):.2f} kW", delta=grid_action)
        st.metric("Total Net (Day)", f"{df['total_demand'].sum() - df['solar_gen'].sum():.2f} kWh")

    # --- COST OPTIMIZATION ---
    st.divider()
    o1, o2 = st.columns(2)
    opt_val = 15.5 # Example calculation value
    o1.metric("Cost Optimization", f"{opt_val}%", delta="Current Hour")
    o2.metric("Cost Saving (Current)", f"${row['total_demand']*0.12:.2f}", delta="Net Saving")

    # --- APPLIANCE CONTROL & SYNC ---
    st.divider()
    st.subheader("Device Management")
    
    # MANUAL SLIDER TRIGGER
    sync_trigger = st.toggle("🚀 Activate Cloud Sync (Send to ESP32)")

    status_table = []
    for app in app_list:
        is_on = row[app] > 0
        status_text = "ON" if is_on else "OFF"
        topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
        
        # Send signal ONLY if slider is clicked
        mqtt_status = "Waiting..."
        if sync_trigger and st.session_state.get('connected'):
            st.session_state.mqtt_client.publish(topic, status_text, qos=1)
            time.sleep(0.1) # ESP32 Stability delay
            mqtt_status = "Sent ✅"
        elif sync_trigger:
            mqtt_status = "Error ❌"

        status_table.append({
            "Appliance": app,
            "Status": status_text,
            "HiveMQ Signal": mqtt_status,
            "Topic": topic
        })

    st.table(pd.DataFrame(status_table))

    # --- TIMING ---
    if st.button("Next Hour ➡️"):
        st.session_state.current_hr += 1
        st.rerun()

    if sync_trigger:
        st.info("Continuous Sync Active: Signals are broadcasting as the simulation progresses.")
        time.sleep(5)
        st.session_state.current_hr += 1
        st.rerun()

