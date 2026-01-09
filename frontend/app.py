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

# --- 2. DATA LOADING & MERGING ---
@st.cache_data
def load_data():
    pred_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(pred_path) and os.path.exists(solar_path):
        df_p = pd.read_csv(pred_path)
        df_s = pd.read_csv(solar_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        
        # Syncing generation column
        df_p['solar_gen'] = df_s['Generation (kW)']
        
        # Ensure numeric for calculations
        for col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing = [c for c in apps if c in df_p.columns]
        df_p['total_demand'] = df_p[existing].sum(axis=1)
        
        return df_p, existing
    return None, []

# Initialize Session Data
if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = False

df = st.session_state.df

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="PPO Autonomous Digital Twin", layout="wide")
st.title("🏡 Autonomous Digital Twin Dashboard")

if df is not None:
    # Current State Calculation
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # --- METRICS (Current Status) ---
    # Grid Status: Positive = Buying, Negative = Exporting
    grid_val = row['total_demand'] - row['solar_gen']
    current_eff = (min(row['solar_gen'], row['total_demand']) / row['total_demand'] * 100) if row['total_demand'] > 0 else 100.0
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    m3.metric("Grid Status", f"{abs(grid_val):.2f} kW", delta="Buying" if grid_val > 0 else "Exporting", delta_color="inverse")
    m4.metric("Efficiency", f"{current_eff:.1f}%")
    m5.metric("CO2 Saved (Total)", f"{(np.minimum(df['solar_gen'], df['total_demand']).sum() * 0.4):.2f} kg")

    st.divider()

    # --- 4. XAI MODULE: PPO DECISION FACTORS ---
    st.subheader("🔍 XAI: PPO Decision Factors")
    
    # Mock Weights based on your requested design
    xai_weights = {
        'Electricity Price': 1.2,
        'Solar Forecast': 0.9,
        'Occupancy': 0.4,
        'Total Demand': 0.2
    }
    xai_df = pd.DataFrame(list(xai_weights.items()), columns=['Factor', 'Weight'])
    
    c_xai1, c_xai2 = st.columns([2, 1])
    with c_xai1:
        st.bar_chart(xai_df.set_index('Factor'), color="#1f77b4") # Mimicking PPO Factors
    
    with c_xai2:
        ai_on = float(row['solar_gen']) > float(row['total_demand'])
        st.info("**AI Reasoning Engine**")
        if ai_on:
            st.write("Decision: **HEATER ON**")
            st.write("Primary Driver: **Solar Forecast**")
            st.write("Logic: High solar availability outweighs current demand costs.")
        else:
            st.write("Decision: **HEATER OFF**")
            st.write("Primary Driver: **Electricity Price**")
            st.write("Logic: Low solar generation; grid prices are the dominant factor.")

    # --- 5. AUTOMATION & VISUALS ---
    st.sidebar.header("🤖 Control Center")
    st.session_state.auto_mode = st.sidebar.toggle("Enable AI Auto-Control", value=st.session_state.auto_mode)

    if st.session_state.auto_mode:
        st.sidebar.info(f"Syncing Hour {idx}:00")
        send_mqtt_command(ai_on)
        time.sleep(2)
        st.session_state.current_hr = (idx + 1) % len(df)
        st.rerun() # Refresh all UI and XAI weights
    else:
        st.session_state.current_hr = st.sidebar.slider("Select Hour", 0, len(df)-1, idx)

    st.subheader(f"📊 Live Data at Hour {idx}:00")
    st.line_chart(df[['solar_gen', 'total_demand']])
    st.bar_chart(row[st.session_state.apps])

else:
    st.error("🚨 Check your /data folder for CSV files.")
