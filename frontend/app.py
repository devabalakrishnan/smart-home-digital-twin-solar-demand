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

# --- 2. DATA LOADING (With Cache) ---
@st.cache_data
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        existing_apps = [c for c in app_cols if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
        # Check if solar_gen exists, if not, try to map it from known solar columns
        if 'solar_gen' not in df.columns:
            df['solar_gen'] = 0.0
        return df, existing_apps
    return None, []

df, app_list = load_data()

# --- 3. UI & AUTOMATION ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    if 'current_hr' not in st.session_state:
        st.session_state.current_hr = 0
    if 'auto_mode' not in st.session_state:
        st.session_state.auto_mode = False

    # Efficiency & Carbon (Daily Totals)
    solar_utilized = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2_saved = solar_utilized * 0.4
    solar_hours = len(df[df['solar_gen'] > df['total_demand']])
    efficiency_score = (solar_hours / len(df)) * 100

    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)
    
    # --- CRITICAL FIX: Update row context BEFORE the loop logic ---
    current_idx = st.session_state.current_hr % len(df)
    row = df.iloc[current_idx]
    
    # AI Decision Logic
    ai_should_be_on = float(row['solar_gen']) > float(row['total_demand'])

    if st.session_state.auto_mode:
        st.sidebar.info(f"Auto-Syncing Hour {current_idx}:00")
        st.sidebar.write(f"AI Decision: **{'HEATER ON' if ai_should_be_on else 'HEATER OFF'}**")
        
        # Trigger MQTT
        send_mqtt_command(ai_should_be_on)
        
        # Wait and increment
        time.sleep(2)
        st.session_state.current_hr = (current_idx + 1) % len(df)
        st.rerun() # Force fresh run with new index
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, st.session_state.current_hr)
        row = df.iloc[st.session_state.current_hr] # Re-sync row for manual slider

    # --- 4. REAL-TIME METRICS (Now dynamic) ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar Supply", f"{row['solar_gen']:.2f} kW")
    c3.metric("Self-Sufficiency", f"{efficiency_score:.1f}%")
    c4.metric("CO2 Saved", f"{co2_saved:.2f} kg")

    # --- 5. VISUALIZATION ---
    st.subheader(f"📈 Energy Flow at Hour {current_idx}:00")
    
    # Line chart for context
    st.line_chart(df[['solar_gen', 'total_demand']])
    
    # Highlight current hour in bar chart
    st.write("### Appliance Load Distribution")
    st.bar_chart(row[app_list])

else:
    st.error("🚨 CSV Data not found!")
