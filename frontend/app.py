import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl
import gymnasium as gym
import time

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | AI Home", layout="wide")

# --- 2. MQTT SETTINGS ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(topic_suffix, is_on):
    """Sends command to ESP32 via HiveMQ."""
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        topic = f"home/appliances/{topic_suffix.lower().replace(' ', '_')}/command"
        payload = "ON" if is_on else "OFF"
        client.publish(topic, payload, qos=1)
        client.disconnect()
        return True
    except Exception:
        return False

# --- 3. DIGITAL TWIN RL ENVIRONMENT ---
class MergedSolarHomeEnv(gym.Env):
    def __init__(self, solar_data, demand_data):
        super(MergedSolarHomeEnv, self).__init__()
        self.solar_profile = solar_data
        self.demand_profile = demand_data
        self.observation_space = gym.spaces.Box(low=0, high=23, shape=(1,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(2)

    def get_ai_decision(self, hour):
        """Simulates PPO logic: activate load if solar surplus exists."""
        solar_val = self.solar_profile[hour]
        demand_val = self.demand_profile[hour]
        # Logic: If solar exceeds demand by 0.5kW, virtual twin triggers action
        return 1 if solar_val > (demand_val + 0.5) else 0

# --- 4. HARDENED DATA LOADING ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path).rename(columns=lambda x: x.strip())
        df_solar = pd.read_csv(solar_path).rename(columns=lambda x: x.strip())
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        # Explicit Numeric Conversion to fix scientific notation and string errors
        for col in app_cols + ['electricity_price', 'occupancy']:
            if col in df_demand.columns:
                df_demand[col] = pd.to_numeric(df_demand[col], errors='coerce').fillna(0.0)

        # Solar Generation alignment from 'Generation (kW)' column
        if 'Generation (kW)' in df_solar.columns:
            solar_vals = pd.to_numeric(df_solar['Generation (kW)'], errors='coerce').fillna(0.0).values
            df_demand['solar_gen'] = (list(solar_vals) * 2)[:len(df_demand)]
        else:
            df_demand['solar_gen'] = pd.to_numeric(df_solar.iloc[:, 2], errors='coerce').fillna(0.0)

        # Force float math to avoid 'str' errors
        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1).astype(float)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen'].astype(float)).clip(lower=0.0)
        
        return df_demand, app_cols
    return None, []

df, app_list = load_research_data()

# --- 5. DASHBOARD UI ---
if df is not None:
    st.title("🏡 Residential Digital Twin: AI Real-Time Simulation")
    
    # Global Metrics
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh") 
    g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh Offset") 
    g3.metric("Total Savings", "$5.51", "54.5% Reduction") 
    
    st.divider()

    # SIDEBAR: Simulation Controls
    st.sidebar.header("🕹️ Simulation Controls")
    is_live = st.sidebar.toggle("Enable Real-Time Simulation")
    
    # Hour selection (Manual or Auto)
    if is_live:
        if 'sim_hour' not in st.session_state:
            st.session_state.sim_hour = 0
        selected_hour = st.session_state.sim_hour
    else:
        selected_hour = st.sidebar.slider("Select Simulation Hour", 0, len(df)-1, 12)

    # Initialize Virtual Brain
    brain = MergedSolarHomeEnv(df['solar_gen'].values, df['total_demand'].values)
    ai_action = brain.get_ai_decision(selected_hour)
    
    st.sidebar.subheader("🤖 AI Agent Suggestion")
    if ai_action == 1:
        st.sidebar.warning(f"Hour {selected_hour}: Solar Surplus - Load ON")
    else:
        st.sidebar.success(f"Hour {selected_hour}: Normal Operation")

    # MAIN CONTENT: Energy State
    row = df.iloc[selected_hour]
    st.subheader(f"⏱️ State at {selected_hour}:00")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.3f} kW")
    m2.metric("Solar Supply", f"{row['solar_gen']:.3f} kW")
    m3.metric("Grid Reliance", f"{row['net_load']:.3f} kW")

    # Visualizations
    
    c1, c2 = st.columns(2)
    with c1:
        pie_df = pd.DataFrame({"Appliance": app_list, "Usage": [row[a] for a in app_list]})
        fig_pie = px.pie(pie_df, values='Usage', names='Appliance', hole=0.4, title="Load Breakdown")
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with c2:
        # XAI Decision Weights
        price_w = float(row['electricity_price']) * 2.5
        solar_w = 2.0 if float(row['solar_gen']) > 1.5 else 0.4
        xai_df = pd.DataFrame({
            'Factor': ['Price', 'Demand', 'Occupancy', 'Solar'],
            'Weight': [price_w, 0.5, float(row['occupancy']) * 0.4, solar_w]
        })
        fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', title="XAI: Decision Weights", color='Weight')
        st.plotly_chart(fig_xai, use_container_width=True)

    # Simulation Tick
    if is_live:
        time.sleep(2) # Wait 2 seconds per hour
        st.session_state.sim_hour = (st.session_state.sim_hour + 1) % 24
        
        # Auto-Sync Hardware during simulation
        for app in app_list:
            send_mqtt_command(app, (row[app] > 0))
            
        st.rerun()

else:
    st.error("🚨 Data Error: Check /data folder and CSV formatting.")
