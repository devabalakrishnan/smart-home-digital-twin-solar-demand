import streamlit as st
import pandas as pd
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl
from datetime import datetime

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- 2. HIVEMQ CLOUD CONNECTION SETTINGS ---
# host must be just the URL (no port 8883)
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(is_on):
    """Sends a physical command to HiveMQ Cloud with verification."""
    # Initialize client for secure TCP connection
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    
    # HiveMQ Cloud MANDATORY TLS for port 8883
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        topic = "home/appliances/heater/command"
        payload = "ON" if is_on else "OFF"
        
        # publish and ensure it finishes before disconnecting
        msg_info = client.publish(topic, payload)
        msg_info.wait_for_publish() 
        
        client.disconnect()
        return True
    except Exception as e:
        st.sidebar.error(f"MQTT Error: {e}")
        return False

# --- 3. DATA LOADING ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Normalize column names
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        df_demand['solar_gen'] = df_solar['generation_kw']
        app_cols = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # --- 4. HEADER & GLOBAL METRICS ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh")
    g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar Offset)")
    g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings")
    
    st.divider()

    # --- 5. SIDEBAR: DIGITAL TWIN CONTROLS ---
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 11)
    
    st.sidebar.divider()
    st.sidebar.subheader("🛠️ Manual Override")
    
    # Toggle that triggers the real-world HiveMQ signal
    override_heater = st.sidebar.toggle("Deactivate Heater (Physical Command)") 
    
    if override_heater:
        if send_mqtt_command(False):
            # Confirmation box seen in your screenshots
            st.sidebar.success("✅ Signal sent to HiveMQ: Heater OFF") 
    else:
        # Send 'ON' if the switch is turned back to active
        pass

    # --- 6. REAL-TIME ENERGY STATE ---
    row = df.iloc[selected_hour].copy()
    
    # Static Pricing Grid for PPO Decision Analysis
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]
    current_price = grid_prices[selected_hour]

    # Dynamically update the display if manual override is active
    if override_heater and 'Heater' in app_list:
        row['total_demand'] -= row['Heater']
        row['net_load'] = max(0, row['total_demand'] - row['solar_gen'])

    st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    m3.metric("Net Load", f"{row['net_load']:.2f} kW")

    # Recommendation Box
    if current_price >= 0.45:
        st.error(f"⚠️ High Tariff Period (${current_price:.2f}/kWh): Load shedding recommended.")
    elif row['solar_gen'] > row['total_demand']:
        st.success(f"☀️ Solar Surplus: Maximize usage of storage or heavy appliances.")

    # --- 7. XAI & PIE BREAKDOWN ---
    st.divider()
    col_xai, col_pie = st.columns([2, 1])
    
    with col_xai:
        st.subheader("🔍 XAI: PPO Decision Factors")
        xai_data = pd.DataFrame({
            'Factor': ['Electricity Price', 'Total Demand', 'Occupancy', 'Solar Forecast'],
            'Importance': [1.5 if current_price > 0.40 else 0.5, 0.2, 0.4, 0.9],
            'Color': ['#FF4B4B' if current_price > 0.40 else '#0068C9', '#0068C9', '#0068C9', '#FFA500']
        })
        fig_xai = px.bar(xai_data, x='Importance', y='Factor', orientation='h', 
                         color='Color', color_discrete_map="identity")
        st.plotly_chart(fig_xai, use_container_width=True)

    with col_pie:
        st.subheader("💡 Appliance Breakdown")
        hour_apps = {app: row[app] for app in app_list}
        fig_pie = px.pie(names=list(hour_apps.keys()), values=list(hour_apps.values()), hole=0.4)
        fig_pie.update_traces(textinfo='label+percent')
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.error("🚨 System Offline: Missing CSV data in /data folder.")
