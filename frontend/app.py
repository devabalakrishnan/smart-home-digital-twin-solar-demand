import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np
import plotly.express as px

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir"

def broadcast_all_appliances(app_list, row):
    """Opens ONE connection and sends ALL appliance states."""
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) # Mandatory SSL
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() # Start background networking
        
        for app in app_list:
            is_on = row[app] > 0
            payload = "ON" if is_on else "OFF"
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # Publish with QoS 1 to ensure delivery
            client.publish(topic, payload, qos=1)
        
        time.sleep(1) # Short pause to ensure all messages leave the buffer
        client.loop_stop()
        client.disconnect()
        return True
    except Exception as e:
        st.error(f"MQTT Sync Failed: {e}")
        return False

# --- 2. DATA ENGINE ---
@st.cache_data
def load_and_prep_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p, df_s = pd.read_csv(p_path), pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df_p['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in apps if c in df_p.columns]
        for col in existing_apps:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
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
st.title("🏡 Residential Digital Twin: Global Optimization")

if df is not None:
    # --- DYNAMIC GLOBAL OPTIMIZATION ---
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    total_load_24h = df['total_demand'].sum()
    solar_offset_24h = np.minimum(df['solar_gen'], df['total_demand']).sum()
    total_cost_savings = solar_offset_24h * 0.15
    savings_percent = (solar_offset_24h / total_load_24h * 100) if total_load_24h > 0 else 0

    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", f"{total_load_24h:.2f} kWh")
    g2.metric("Optimized Load", f"{(total_load_24h - solar_offset_24h):.2f} kWh")
    g3.metric("Total Cost Optimization", f"${total_cost_savings:.2f}", f"{savings_percent:.1f}% Savings")

    st.divider()

    # --- HARDWARE SYNC & TABLE ---
    st.subheader(f"🔌 Appliance Status & Cloud Sync (Hour {idx}:00)")
    
    # TRIGGER BROADCAST
    sync_success = broadcast_all_appliances(app_list, row)
    
    status_data = []
    for app in app_list:
        is_on = row[app] > 0
        status_data.append({
            "Appliance": app,
            "Status": "🟢 ON" if is_on else "🔴 OFF",
            "Load (kW)": f"{row[app]:.2f}",
            "MQTT Topic": f"home/appliances/{app.lower().replace(' ', '_')}/command"
        })
    st.table(pd.DataFrame(status_data))

    # --- 4. AUTONOMOUS SYNC LOOP ---
    time.sleep(5) # Increased sleep to give HiveMQ time to process
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun()
