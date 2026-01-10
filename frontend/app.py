import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
# Ensure this password uses the lowercase 'l' (lima)
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir" 

# Initialize persistent MQTT connection in session state
if 'mqtt_client' not in st.session_state:
    client = mqtt.Client(client_id="Digital_Twin_Broadcaster", transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() # Start background thread for networking
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception as e:
        st.session_state.connected = False
        st.error(f"MQTT Connection Failed: {e}")

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df = pd.read_csv(p_path)
        df_s = pd.read_csv(s_path)
        df.columns = df.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df['solar_gen'] = pd.to_numeric(df_s['Generation (kW)'], errors='coerce').fillna(0.0)
        
        # Define all 7 appliances
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in apps if c in df.columns]
        for col in existing_apps:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        df['total_demand'] = df[existing_apps].sum(axis=1)
        return df, existing_apps
    return None, []

# --- 3. UI INITIALIZATION ---
st.set_page_config(page_title="PPO Digital Twin Sync", layout="wide")
st.title("🏡 Residential Digital Twin: Multi-Appliance Sync")

if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

if df is not None:
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # Display Current Simulation Metrics
    st.subheader(f"⏱️ Simulating Hour {idx}:00")
    c1, c2 = st.columns(2)
    c1.metric("Total Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar Gen", f"{row['solar_gen']:.2f} kW")

    st.divider()

    # --- 4. THE PACED BROADCAST LOOP ---
    if st.session_state.get('connected'):
        st.info("📡 Broadcasting appliance states to HiveMQ Cloud...")
        status_data = []
        
        for app in app_list:
            status = "ON" if row[app] > 0 else "OFF"
            # Format topic to match ESP32 code expectations
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            
            # Publish to HiveMQ
            st.session_state.mqtt_client.publish(topic, status, qos=1)
            
            # --- CRITICAL: Pacing delay for ESP32 stability ---
            time.sleep(0.1) 
            
            status_data.append({
                "Appliance": app, 
                "Status": status, 
                "Topic": topic,
                "Sync": "🟢 Active"
            })
        
        # Display the real-time status table
        st.table(pd.DataFrame(status_data))
        st.success(f"✅ Hour {idx} broadcast complete. All signals sent to buffer.")
    else:
        st.error("❌ Cloud Sync Offline. Please check credentials.")

    # --- SIMULATION STEP TIMER ---
    # 10 second pause before next hour to allow cloud processing
    time.sleep(10) 
    st.session_state.current_hr += 1
    st.rerun()
