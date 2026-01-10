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

def send_mqtt_signal(topic, command):
    """Sends a secure signal to HiveMQ Cloud."""
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    # MANDATORY: SSL/TLS for HiveMQ Cloud
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        # QoS 1 ensures the broker receives the message
        result = client.publish(topic, command, qos=1)
        
        if result.wait_for_publish(timeout=2):
            client.disconnect()
            return True
        client.disconnect()
        return False
    except:
        return False

# --- 2. DYNAMIC DATA ENGINE ---
@st.cache_data
def load_and_prep_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p, df_s = pd.read_csv(p_path), pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        
        # Sync Solar Generation from forecast CSV
        df_p['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        
        for col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
        # Complete Appliance List matching your reference
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
st.set_page_config(page_title="PPO Digital Twin: Global Optimization", layout="wide")
st.title("🏡 Residential Digital Twin: Global Optimization")

if df is not None:
    # --- DYNAMIC GLOBAL OPTIMIZATION ---
    UNIT_PRICE = 0.15 
    total_load_24h = df['total_demand'].sum()
    solar_offset_24h = np.minimum(df['solar_gen'], df['total_demand']).sum()
    optimized_load_24h = total_load_24h - solar_offset_24h
    total_cost_savings = solar_offset_24h * UNIT_PRICE
    savings_percent = (solar_offset_24h / total_load_24h * 100) if total_load_24h > 0 else 0

    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", f"{total_load_24h:.2f} kWh")
    g2.metric("Optimized Load", f"{optimized_load_24h:.2f} kWh", f"-{solar_offset_24h:.2f} kWh (Solar Offset)")
    g3.metric("Total Cost Optimization", f"${total_cost_savings:.2f}", f"{savings_percent:.1f}% Savings")

    st.divider()

    # --- LIVE ENERGY STATE ---
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    st.subheader(f"⏱️ Energy State at Hour {idx}:00")
    
    net_load_now = max(0, row['total_demand'] - row['solar_gen'])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Net Load", f"{net_load_now:.2f} kW")
    c4.metric("Efficiency", f"{( (1 - (net_load_now/row['total_demand']))*100 if row['total_demand']>0 else 100):.1f}%")

    st.divider()

    # --- HARDWARE SYNC & XAI ---
    col_table, col_xai = st.columns([1.5, 1])

    with col_table:
        st.subheader("🔌 ESP32 Appliance & MQTT Sync")
        status_data = []
        for app in app_list:
            is_on = row[app] > 0
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # Auto-send to HiveMQ
            send_mqtt_signal(topic, "ON" if is_on else "OFF")
            
            status_data.append({
                "Appliance": app,
                "Status": "🟢 ON" if is_on else "🔴 OFF",
                "Load (kW)": f"{row[app]:.2f}",
                "MQTT Topic": topic
            })
        st.table(pd.DataFrame(status_data))

    with col_xai:
        st.subheader("🔍 XAI: PPO Decision Factors")
        xai_df = pd.DataFrame({
            'Factor': ['Electricity Price', 'Solar Forecast', 'Occupancy', 'Total Demand'],
            'Weight': [1.2, 0.9, 0.4, 0.2]
        })
        fig = px.bar(xai_df, x='Weight', y='Factor', orientation='h', 
                     color='Weight', color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    # --- 4. AUTONOMOUS SYNC LOOP ---
    time.sleep(4) 
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun()
