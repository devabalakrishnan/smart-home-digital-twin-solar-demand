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

# --- 2. DATA LOADING (With Column Mapping) ---
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip() # Clean hidden spaces
        
        # Convert all columns to numeric
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # FIX: Find the Solar Column automatically
        solar_options = ['solar_gen', 'Solar', 'solar', 'Generation', 'Solar_kW']
        found_solar = next((c for c in solar_options if c in df.columns), None)
        
        if found_solar:
            df['solar_gen_final'] = df[found_solar]
        else:
            # If still not found, try to use the first column that isn't an appliance
            df['solar_gen_final'] = 0.0
            st.warning("⚠️ Could not find a solar column. Please check CSV headers.")

        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
            
        return df, existing_apps
    return None, []

df, apps = load_data()

# --- 3. SESSION STATE ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

# --- 4. DASHBOARD LOGIC ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    # Get current row and metrics
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # Calculate Impact Metrics using the final solar column
    solar_util = np.minimum(df['solar_gen_final'], df['total_demand']).sum()
    co2_val = solar_util * 0.4
    solar_hours = len(df[df['solar_gen_final'] > df['total_demand']])
    eff_val = (solar_hours / len(df)) * 100

    # SIDEBAR
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)

    # METRICS DISPLAY
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{row['solar_gen_final']:.2f} kW") # Now mapped correctly
    c3.metric("Efficiency", f"{eff_val:.1f}%")
    c4.metric("CO2 Saved", f"{co2_val:.2f} kg")

    if st.session_state.auto_mode:
        st.sidebar.info(f"Syncing Hour {idx}:00")
        ai_on = float(row['solar_gen_final']) > float(row['total_demand'])
        send_mqtt_command(ai_on)
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() 
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)

    # CHARTS
    st.subheader(f"📊 Energy Flow at Hour {idx}:00")
    st.line_chart(df[['solar_gen_final', 'total_demand']])
    st.bar_chart(row[apps])
