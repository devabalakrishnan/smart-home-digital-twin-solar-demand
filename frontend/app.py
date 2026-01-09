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

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    path = "data/next_day_prediction.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        # Force all data to be numeric to avoid display errors
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df.columns]
        df['total_demand'] = df[existing_apps].sum(axis=1)
        if 'solar_gen' not in df.columns:
            df['solar_gen'] = 0.0
        return df, existing_apps
    return None, []

# Initialize only once
if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_data()

# --- 3. SESSION STATE ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

df = st.session_state.df
app_list = st.session_state.apps

# --- 4. MAIN DASHBOARD UI ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)
    
    # CRITICAL: Always calculate the row based on the latest current_hr
    current_idx = st.session_state.current_hr % len(df)
    row = df.iloc[current_idx]
    
    # AI Decision
    ai_should_be_on = float(row['solar_gen']) > float(row['total_demand'])

    if st.session_state.auto_mode:
        st.sidebar.info(f"Auto-Syncing: Hour {current_idx}:00")
        st.sidebar.write(f"Decision: **{'HEATER ON' if ai_should_be_on else 'HEATER OFF'}**")
        
        # Physical Command
        send_mqtt_command(ai_should_be_on)
        
        # Advance hour and RERUN to update values
        time.sleep(2)
        st.session_state.current_hr = (current_idx + 1) % len(df)
        st.rerun() # This triggers a fresh read of the 'row' variable
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, current_idx)

    # --- 5. METRICS (These will now update properly) ---
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate daily metrics once
    solar_utilized = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2_total = solar_utilized * 0.4
    efficiency = (len(df[df['solar_gen'] > df['total_demand']]) / len(df)) * 100

    col1.metric("Demand", f"{row['total_demand']:.2f} kW")
    col2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    col3.metric("Efficiency", f"{efficiency:.1f}%")
    col4.metric("CO2 Saved", f"{co2_total:.2f} kg")

    # --- 6. CHARTS ---
    st.subheader(f"📊 Live Data at Hour {current_idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    
    st.write("### Appliance Breakdown")
    st.bar_chart(row[app_list])

else:
    st.error("🚨 CSV Data not found.")
