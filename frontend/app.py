import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_signal(topic, command):
    """Sends autonomous signals to ESP32 via HiveMQ Cloud"""
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.publish(topic, command, qos=1)
        client.disconnect()
        return True
    except Exception as e:
        return False

# --- 2. DATA ENGINE ---
@st.cache_data
def load_digital_twin_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p, df_s = pd.read_csv(p_path), pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df_p['solar_gen'] = df_s['Generation (kW)'] #
        
        for col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        df_p['total_demand'] = df_p[[c for c in apps if c in df_p.columns]].sum(axis=1)
        return df_p, [c for c in apps if c in df_p.columns]
    return None, []

# Initialization
if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_digital_twin_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

# --- 3. UI DASHBOARD ---
st.set_page_config(page_title="Autonomous Digital Twin", layout="wide")
st.title("🏡 Autonomous Digital Twin: ESP32 Hardware Bridge")

if df is not None:
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # Real-time Metrics
    grid = row['total_demand'] - row['solar_gen']
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Solar Gen", f"{row['solar_gen']:.2f} kW")
    m3.metric("Grid Status", f"{abs(grid):.2f} kW", delta="Buying" if grid > 0 else "Exporting", delta_color="inverse")
    m4.metric("Efficiency", f"{(min(row['solar_gen'], row['total_demand'])/row['total_demand']*100 if row['total_demand']>0 else 100):.1f}%")

    st.divider()

    # --- 4. APPLIANCE STATUS & XAI MODULE ---
    col_app, col_xai = st.columns(2)

    with col_app:
        st.subheader("🔌 Appliance Status (ESP32 Sync)")
        status_list = []
        for app in app_list:
            # Automatic signal logic: If kW > 0, send ON
            is_on = row[app] > 0
            status_list.append({"Appliance": app, "Status": "🟢 ON" if is_on else "🔴 OFF", "Load (kW)": f"{row[app]:.2f}"})
            
            # ESP32 Communication Link
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            send_mqtt_signal(topic, "ON" if is_on else "OFF")
            
        st.table(pd.DataFrame(status_list))

    with col_xai:
        st.subheader("🔍 XAI: PPO Decision Weights")
        weights = {'Price': 1.2, 'Solar': 0.9, 'Occupancy': 0.4, 'Demand': 0.2} #
        st.bar_chart(pd.DataFrame(list(weights.items()), columns=['Factor', 'Weight']).set_index('Factor'))
        
        # High-level AI reasoning
        ai_logic = "Solar Surplus" if row['solar_gen'] > row['total_demand'] else "Grid Reliance"
        st.info(f"**AI Logic State:** {ai_logic}")

    # --- 5. AUTONOMOUS LOOP ---
    time.sleep(3) # Sync interval
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun() # Refresh and send next set of signals

else:
    st.error("🚨 Check your /data folder.")
