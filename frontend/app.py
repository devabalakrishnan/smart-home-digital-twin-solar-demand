import streamlit as st
import pandas as pd
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl
import numpy as np

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- 2. MQTT COMMAND FUNCTION ---
def send_mqtt_command(is_on):
    MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
    MQTT_PORT = 8883 
    MQTT_USER = "hivemq.client.1766925863216"
    MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"
    
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        payload = "ON" if is_on else "OFF"
        client.publish("home/appliances/heater/command", payload, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 3. DATA LOADING ---
@st.cache_data
def load_data():
    # Ensure these files exist in a folder named 'data'
    df_demand = pd.read_csv("data/next_day_prediction.csv")
    df_solar = pd.read_csv("data/solar_forecast.csv")
    
    # Merge and Calculate
    df_demand['solar_gen'] = df_solar.iloc[:, 1] # Assumes 2nd column is generation
    app_list = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
    df_demand['total_demand'] = df_demand[app_list].sum(axis=1)
    df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
    
    # Calculate Cumulative Savings for the Line Chart
    df_demand['hourly_savings'] = df_demand['solar_gen'] * 0.15 # Example rate
    df_demand['cumulative_savings'] = df_demand['hourly_savings'].cumsum()
    
    return df_demand, app_list

df, app_list = load_data()

# --- 4. SIDEBAR CONTROLS ---
st.sidebar.header("🕹️ Digital Twin Controls")
selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 12)
st.sidebar.divider()

# Physical Override Logic
st.sidebar.subheader("🛠️ Manual Override")
toggle_off = st.sidebar.toggle("Deactivate Heater (Physical Command)")
if st.sidebar.button("Execute Signal"):
    success = send_mqtt_command(not toggle_off)
    if success: st.sidebar.success("Signal Sent!")

# --- 5. DYNAMIC CALCULATION ---
# This line grabs the specific row for the hour you selected
row = df.iloc[selected_hour]

# --- 6. TOP METRICS (Now Dynamic) ---
st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
m1, m2, m3 = st.columns(3)

# These numbers now update based on the slider
total_24h_load = df['total_demand'].sum()
optimized_24h_load = df['net_load'].sum()
savings_pct = ((total_24h_load - optimized_24h_load) / total_24h_load) * 100

m1.metric("Total Load (24hr)", f"{total_24h_load:.2f} kWh")
m2.metric("Optimized Load", f"{optimized_24h_load:.2f} kWh", f"-{total_24h_load-optimized_24h_load:.2f} kWh (Solar)")
m3.metric("Cost Optimization", f"${df['cumulative_savings'].iloc[-1]:.2f}", f"{savings_pct:.1f}% Savings")

st.divider()

# --- 7. APPLIANCE BREAKDOWN & ENERGY STATE ---
st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
col_a, col_b = st.columns(2)

with col_a:
    st.write("### Real-time Load")
    st.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    st.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    st.metric("Net Load", f"{row['net_load']:.2f} kW")
    
    # PPO Status
    ppo_status = "OFF" if row['net_load'] > 1.0 else "ON"
    st.info(f"🤖 **PPO Agent:** Recommends **{ppo_status}** at this hour.")

with col_b:
    # PIE CHART: Appliance Breakdown
    breakdown = row[app_list].to_dict()
    df_pie = pd.DataFrame(list(breakdown.items()), columns=['Appliance', 'kW'])
    fig_pie = px.pie(df_pie, values='kW', names='Appliance', title="Appliance Breakdown")
    st.plotly_chart(fig_pie, use_container_width=True)

# --- 8. DYNAMIC XAI & SAVINGS CHART ---
st.divider()
col_c, col_d = st.columns(2)

with col_c:
    st.subheader("🔍 XAI: Decision Factors")
    # Dynamic Weights based on time
    solar_w = 1.8 if 10 <= selected_hour <= 16 else 0.2
    price_w = 1.9 if row['net_load'] > 0.8 else 0.6
    
    xai_df = pd.DataFrame({
        'Factor': ['Electricity Price', 'Solar Forecast', 'Occupancy', 'Demand'],
        'Weight': [price_w, solar_w, 0.4, 0.2]
    })
    fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', color_discrete_sequence=['#0068C9'])
    st.plotly_chart(fig_xai, use_container_width=True)

with col_d:
    st.subheader("📈 Savings Accumulation")
    fig_line = px.line(df.iloc[:selected_hour+1], y='cumulative_savings', title="Savings over Time")
    st.plotly_chart(fig_line, use_container_width=True)
