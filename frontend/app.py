import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np
from datetime import datetime

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_signal(topic, command):
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.publish(topic, command, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 2. DATA ENGINE ---
@st.cache_data
def load_and_prep_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p, df_s = pd.read_csv(p_path), pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df_p['solar_gen'] = df_s['Generation (kW)'] 
        
        for col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in apps if c in df_p.columns]
        df_p['total_demand'] = df_p[existing_apps].sum(axis=1)
        return df_p, existing_apps
    return None, []

if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_and_prep_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="Residential Digital Twin: Global Optimization", layout="wide")

# --- TOP LAYER: GLOBAL OPTIMIZATION (24HR TOTALS) ---
st.title("🏡 Residential Digital Twin: Global Optimization")

if df is not None:
    # FINANCIAL LOGIC
    UNIT_PRICE = 0.15  # Cost per kWh
    total_load_24h = df['total_demand'].sum()
    solar_offset_24h = np.minimum(df['solar_gen'], df['total_demand']).sum()
    optimized_load_24h = total_load_24h - solar_offset_24h
    total_cost_savings = solar_offset_24h * UNIT_PRICE
    savings_percent = (total_cost_savings / (total_load_24h * UNIT_PRICE) * 100) if total_load_24h > 0 else 0

    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", f"{total_load_24h:.2f} kWh")
    g2.metric("Optimized Load", f"{optimized_load_24h:.2f} kWh", 
              delta=f"-{solar_offset_24h:.2f} kWh (Solar Offset)", delta_color="normal")
    g3.metric("Total Cost Optimization", f"${total_cost_savings:.2f}", 
              delta=f"{savings_percent:.1f}% Savings", delta_color="normal")

    st.divider()

    # --- SECTION A: CURRENT HOUR ENERGY STATE ---
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    st.subheader(f"⏱️ Energy State at Hour {idx}:00")
    
    net_load_now = max(0, row['total_demand'] - row['solar_gen'])
    eff_now = (min(row['solar_gen'], row['total_demand'])/row['total_demand']*100 if row['total_demand']>0 else 100)
    co2_now = min(row['solar_gen'], row['total_demand']) * 0.4
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Net Load (Grid)", f"{net_load_now:.2f} kW", delta="Buying" if net_load_now > 0 else "Self-Sufficient", delta_color="inverse")
    c4.metric("Live Efficiency", f"{eff_now:.1f}%")
    c5.metric("Instant CO2 Saved", f"{co2_now:.3f} kg")

    st.divider()

    # --- SECTION B: APPLIANCE CONTROL & XAI ---
    col_table, col_xai = st.columns([1, 1])

    with col_table:
        st.subheader("🔌 ESP32 Appliance Status")
        status_data = []
        for app in app_list:
            is_active = row[app] > 0
            status_data.append({"Appliance": app, "Status": "🟢 ON" if is_active else "🔴 OFF", "Load (kW)": f"{row[app]:.2f}"})
            
            # Autonomous Signal to HiveMQ
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            send_mqtt_signal(topic, "ON" if is_active else "OFF")
        st.table(pd.DataFrame(status_data))

    with col_xai:
        st.subheader("🔍 XAI: PPO Decision Factors")
        # Visualizing factors that influence cost optimization
        weights = {'Electricity Price': 1.2, 'Solar Forecast': 0.9, 'Occupancy': 0.4, 'Total Demand': 0.2} 
        st.bar_chart(pd.DataFrame(list(weights.items()), columns=['Factor', 'Weight']).set_index('Factor'))
        
        if row['solar_gen'] > row['total_demand']:
            st.success("**AI Strategy:** Profit Maximization - Using free solar power.")
        else:
            st.warning("**AI Strategy:** Cost Minimization - Grid dependency active.")

    # --- 4. AUTONOMOUS SYNC LOOP ---
    time.sleep(4) 
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun() 

else:
    st.error("🚨 Missing data files in /data directory.")
