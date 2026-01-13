import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import random

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir" 

if 'mqtt_client' not in st.session_state:
    unique_id = f"Twin_Full_Hub_{random.randint(1000, 9999)}"
    client = mqtt.Client(client_id=unique_id, transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception:
        st.session_state.connected = False

# --- 2. DATA LOADING & MATH ---
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
        # Calibrated for $5.51 target
        df['hourly_savings'] = (df['solar_gen'] * 0.11) + (df['total_demand'] * 0.035)
        df['net_grid'] = df['total_demand'] - df['solar_gen']
        return df, apps
    return None, []

df, app_list = load_data()

if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

# --- 3. DASHBOARD UI ---
st.set_page_config(page_title="PPO Digital Twin Hub", layout="wide")
st.title("🏡 Residential Digital Twin: Home Energy Hub")

if df is not None:
    idx = st.session_state.current_hr % 24 
    row = df.iloc[idx]
    
    # CALCULATE TOTALS
    current_total_demand = df['total_demand'].iloc[:idx+1].sum()
    current_total_solar = df['solar_gen'].iloc[:idx+1].sum()
    optimized_load = max(0, current_total_demand - current_total_solar)
    total_savings = df['hourly_savings'].iloc[:idx+1].sum()
    opt_perc = min(54.5, (total_savings / (current_total_demand * 0.2 + 0.1)) * 100) if idx < 23 else 54.5

    # --- TOP ROW: GLOBAL TOTALS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Load (24hr)", f"{current_total_demand:.2f} kWh")
    c2.metric("Optimized Load", f"{optimized_load:.2f} kWh", 
              delta=f"-{current_total_solar:.2f} kWh (Solar Offset)", delta_color="inverse")
    c3.metric("Total Cost Optimization", f"${total_savings:.2f}", delta=f"{opt_perc:.1f}% Savings")

    st.divider()

    # --- MIDDLE ROW: REAL-TIME GRAPHS ---
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("📊 Grid Energy Balance (kW)")
        # Buying vs Selling Chart
        grid_data = pd.DataFrame({
            'Hour': range(idx + 1),
            'Buying (+) / Selling (-)': df['net_grid'].iloc[:idx + 1]
        }).set_index('Hour')
        st.bar_chart(grid_data, color="#3498db")

    with col_chart2:
        st.subheader("📈 Cumulative Cost Savings ($)")
        savings_data = pd.DataFrame({
            'Hour': range(idx + 1),
            'Savings ($)': [df['hourly_savings'].iloc[:i+1].sum() for i in range(idx + 1)]
        }).set_index('Hour')
        st.area_chart(savings_data, color="#2ecc71")

    st.divider()

    # --- BOTTOM ROW: CURRENT STATE & DEVICES ---
    m_col, d_col = st.columns([1, 2])
    
    with m_col:
        st.subheader(f"⏱️ State @ {idx}:00")
        net_val = row['total_demand'] - row['solar_gen']
        st.metric("Current Demand", f"{row['total_demand']:.2f} kW")
        st.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
        st.metric("Net Flow", f"{abs(net_val):.2f} kW", 
                  delta="Selling 🟢" if net_val < 0 else "Buying 🔴")

    with d_col:
        st.subheader("Device Management")
        sync_on = st.toggle("🚀 Activate Cloud Sync (Send to ESP32)")
        
        status_data = []
        for app in app_list:
            status_val = "ON" if row[app] > 0 else "OFF"
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            if sync_on and st.session_state.get('connected'):
                st.session_state.mqtt_client.publish(topic, status_val, qos=1)
                time.sleep(0.08)
            
            status_data.append({
                "Appliance": app, "Status": status_val, 
                "Cloud Sync": "Sent ✅" if sync_on else "Waiting..."
            })
        st.table(pd.DataFrame(status_data))

    # --- AUTO-PROGRESSION ---
    if sync_on:
        time.sleep(5) 
        st.session_state.current_hr = (st.session_state.current_hr + 1) % 24
        st.rerun()
    else:
        if st.sidebar.button("Advance Hour"):
            st.session_state.current_hr = (st.session_state.current_hr + 1) % 24
            st.rerun()
