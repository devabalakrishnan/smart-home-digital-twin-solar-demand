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

# --- 2. DATA LOADING (Targeting your specific columns) ---
def load_data():
    # Use your specific data paths from GitHub
    pred_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(pred_path) and os.path.exists(solar_path):
        df_pred = pd.read_csv(pred_path)
        df_solar = pd.read_csv(solar_path)
        
        # Clean column names
        df_pred.columns = df_pred.columns.str.strip()
        df_solar.columns = df_solar.columns.str.strip()
        
        # FIX: Explicitly use 'Generation (kW)' as your solar source
        if 'Generation (kW)' in df_solar.columns:
            df_pred['solar_gen'] = df_solar['Generation (kW)']
        else:
            # Fallback if the column name varies slightly
            df_pred['solar_gen'] = 0.0
            st.error("⚠️ Could not find 'Generation (kW)' in solar_forecast.csv")

        # Convert to numeric to ensure math works
        for col in df_pred.columns:
            df_pred[col] = pd.to_numeric(df_pred[col], errors='coerce').fillna(0.0)
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in app_cols if c in df_pred.columns]
        df_pred['total_demand'] = df_pred[existing_apps].sum(axis=1)
            
        return df_pred, existing_apps
    return None, []

df, apps = load_data()

# --- 3. SESSION STATE ---
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

# --- 4. DASHBOARD UI ---
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    # Get dynamic row based on time
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # Calculate Impact Metrics
    solar_util = np.minimum(df['solar_gen'], df['total_demand']).sum()
    co2_val = solar_util * 0.4
    solar_hours = len(df[df['solar_gen'] > df['total_demand']])
    eff_val = (solar_hours / len(df)) * 100

    # SIDEBAR
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)

    # METRICS DISPLAY (Now using correct data)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Efficiency", f"{eff_val:.1f}%")
    c4.metric("CO2 Saved", f"{co2_val:.2f} kg")

    if st.session_state.auto_mode:
        st.sidebar.info(f"Syncing Hour {idx}:00")
        ai_on = float(row['solar_gen']) > float(row['total_demand'])
        send_mqtt_command(ai_on)
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() 
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)

    # VISUALIZATION
    st.subheader(f"📊 Live Data at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    st.bar_chart(row[apps])
else:
    st.error("🚨 Check your CSV files in the data/ folder.")
