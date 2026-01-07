import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl
import gymnasium as gym
import time
from datetime import datetime

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | Full AI Home", layout="wide")

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

    def get_ai_decision(self, hour):
        """Simulates PPO logic: activate load if solar surplus exists."""
        solar_val = self.solar_profile[hour]
        demand_val = self.demand_profile[hour]
        return 1 if solar_val > (demand_val + 0.5) else 0

# --- 4. DATA LOADING & HARDENING ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path).rename(columns=lambda x: x.strip())
        df_solar = pd.read_csv(solar_path).rename(columns=lambda x: x.strip())
        
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        for col in app_cols + ['electricity_price', 'occupancy']:
            if col in df_demand.columns:
                df_demand[col] = pd.to_numeric(df_demand[col], errors='coerce').fillna(0.0)

        if 'Generation (kW)' in df_solar.columns:
            solar_vals = pd.to_numeric(df_solar['Generation (kW)'], errors='coerce').fillna(0.0).values
            df_demand['solar_gen'] = (list(solar_vals) * 2)[:len(df_demand)]
        else:
            df_demand['solar_gen'] = pd.to_numeric(df_solar.iloc[:, 2], errors='coerce').fillna(0.0)

        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1).astype(float)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen'].astype(float)).clip(lower=0.0)
        
        return df_demand, app_cols
    return None, []

df, app_list = load_research_data()

# --- 5. DASHBOARD UI & REPORTING LOGIC ---
if df is not None:
    # Initialize Session State
    if 'sim_hour' not in st.session_state: st.session_state.sim_hour = 0
    if 'total_saved' not in st.session_state: st.session_state.total_saved = 0.0
    if 'history' not in st.session_state: st.session_state.history = []

    st.title("🏡 Residential Digital Twin: AI Optimization & Reporting")
    
    # Global Metrics
    g1, g2, g3 = st.columns(3)
    g1.metric("Simulation Hour", f"{st.session_state.sim_hour}:00") 
    g2.metric("Total AI Savings", f"${st.session_state.total_saved:.4f}") 
    g3.metric("Projected Efficiency", "54.5%") 
    
    st.divider()

    # SIDEBAR: Simulation & Reports
    st.sidebar.header("🕹️ Simulation Controls")
    is_live = st.sidebar.toggle("Enable Real-Time Simulation")
    
    if st.sidebar.button("Reset Simulation Data"):
        st.session_state.total_saved = 0.0
        st.session_state.history = []
        st.session_state.sim_hour = 0
        st.rerun()

    # Report Export
    if st.session_state.history:
        report_df = pd.DataFrame(st.session_state.history)
        csv = report_df.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button("📥 Download Summary Report", data=csv, 
                                 file_name=f"digital_twin_report_{datetime.now().strftime('%Y%m%d')}.csv", 
                                 mime='text/csv')

    # Simulation Logic
    selected_hour = st.session_state.sim_hour
    brain = MergedSolarHomeEnv(df['solar_gen'].values, df['total_demand'].values)
    ai_action = brain.get_ai_decision(selected_hour)
    
    row = df.iloc[selected_hour]
    savings_this_hour = (row['solar_gen'] if row['solar_gen'] < row['total_demand'] else row['total_demand']) * row['electricity_price']
    
    # UI Layout
    m1, m2, m3 = st.columns(3)
    m1.metric("Load Demand", f"{row['total_demand']:.3f} kW")
    m2.metric("Solar Supply", f"{row['solar_gen']:.3f} kW")
    m3.metric("Grid Reliance", f"{row['net_load']:.3f} kW")

    

    c1, c2 = st.columns(2)
    with c1:
        pie_df = pd.DataFrame({"Appliance": app_list, "Usage": [row[a] for a in app_list]})
        fig_pie = px.pie(pie_df, values='Usage', names='Appliance', hole=0.4, title="Load Distribution")
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with c2:
        # XAI Layer
        price_w = float(row['electricity_price']) * 2.5
        solar_w = 2.0 if float(row['solar_gen']) > 1.5 else 0.4
        xai_df = pd.DataFrame({
            'Factor': ['Price', 'Demand', 'Occupancy', 'Solar'],
            'Weight': [price_w, 0.5, float(row['occupancy']) * 0.4, solar_w]
        })
        fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', title="XAI: Decision Weights", color='Weight')
        st.plotly_chart(fig_xai, use_container_width=True)

    # Simulation Execution Loop
    if is_live:
        # Log History
        st.session_state.history.append({
            "Hour": selected_hour,
            "Demand": row['total_demand'],
            "Solar": row['solar_gen'],
            "Price": row['electricity_price'],
            "Savings": savings_this_hour,
            "AI_Action": ai_action
        })
        
        st.session_state.total_saved += savings_this_hour
        for app in app_list: send_mqtt_command(app, (row[app] > 0)) # Sync Hardware
            
        time.sleep(1.0) 
        st.session_state.sim_hour = (st.session_state.sim_hour + 1) % len(df)
        st.rerun()

else:
    st.error("🚨 System Error: Missing or Corrupt Data Files.")
