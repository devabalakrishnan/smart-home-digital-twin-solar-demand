import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np

# --- 1. MQTT CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(is_on):
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        topic = "home/appliances/heater/command"
        payload = "ON" if is_on else "OFF"
        client.publish(topic, payload, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 2. DATA LOADING & INTEGRATION ---
@st.cache_data
def load_and_merge_data():
    # Use files as seen in your GitHub structure
    pred_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(pred_path) and os.path.exists(solar_path):
        df_pred = pd.read_csv(pred_path)
        df_solar = pd.read_csv(solar_path)
        df_pred.columns = df_pred.columns.str.strip()
        df_solar.columns = df_solar.columns.str.strip()
        
        # Pull 'Generation (kW)' directly
        df_pred['solar_gen'] = df_solar['Generation (kW)']
        
        # Force numeric for math
        for col in df_pred.columns:
            df_pred[col] = pd.to_numeric(df_pred[col], errors='coerce').fillna(0.0)
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df_pred.columns]
        df_pred['total_demand'] = df_pred[existing_apps].sum(axis=1)
        
        return df_pred, existing_apps
    return None, []

# Initialize state to prevent double execution
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

df, apps = load_and_merge_data()

# --- 3. UI RENDERING (Uses placeholder to prevent duplicates) ---
st.title("🏡 Autonomous Digital Twin Dashboard")
placeholder = st.empty() # THIS PREVENTS THE "TWO TYPES" BUG

if df is not None:
    # Sidebar control
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)
    
    # Calculate index and dynamic values
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # Live Calculations
    grid_val = row['total_demand'] - row['solar_gen']
    current_eff = (min(row['solar_gen'], row['total_demand']) / row['total_demand'] * 100) if row['total_demand'] > 0 else 100.0
    current_co2 = min(row['solar_gen'], row['total_demand']) * 0.4

    # Build everything inside the placeholder
    with placeholder.container():
        # Metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Demand", f"{row['total_demand']:.2f} kW")
        m2.metric("Solar", f"{row['solar_gen']:.2f} kW")
        m3.metric("Grid Status", f"{grid_val:.2f} kW", delta="Buying" if grid_val > 0 else "Exporting", delta_color="inverse")
        m4.metric("Live Efficiency", f"{current_eff:.1f}%")
        m5.metric("CO2 Offset", f"{current_co2:.3f} kg")

        # Visualization
        st.subheader(f"📊 Energy Flow Analysis at {idx}:00")
        st.line_chart(df[['solar_gen', 'total_demand']])
        st.bar_chart(row[apps])

    # Automation logic
    if st.session_state.auto_mode:
        st.sidebar.info(f"Syncing Hour {idx}:00")
        ai_on = float(row['solar_gen']) > float(row['total_demand'])
        send_mqtt_command(ai_on)
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() 
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)
else:
    st.error("🚨 Check your /data files.")
