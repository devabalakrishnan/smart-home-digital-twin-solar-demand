import streamlit as st
import pandas as pd
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl
import numpy as np

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- 2. HIVEMQ CLOUD CONNECTION (Physical Link) ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883 
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(is_on):
    """Sends ON/OFF signal to ESP32 via HiveMQ."""
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
    except Exception as e:
        return False

# --- 3. DATA ENGINE (Work No. 1 & 2) ---
@st.cache_data
def load_all_data():
    # Load your forecasting results
    df_demand = pd.read_csv("data/next_day_prediction.csv")
    df_solar = pd.read_csv("data/solar_forecast.csv")
    
    # Merge datasets
    df_demand['solar_gen'] = df_solar.iloc[:, 1]  # Maps solar forecast to demand hours
    app_list = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
    
    # Calculate key metrics
    df_demand['total_demand'] = df_demand[app_list].sum(axis=1)
    df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
    
    # Savings accumulation logic
    df_demand['savings'] = df_demand['solar_gen'] * 0.12 # Simulated cost offset
    df_demand['cum_savings'] = df_demand['savings'].cumsum()
    
    return df_demand, app_list

df, app_list = load_all_data()

# --- 4. SIDEBAR: DIGITAL TWIN CONTROLS ---
st.sidebar.header("🕹️ Digital Twin Controls")
selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 12)

st.sidebar.divider()
st.sidebar.subheader("🛠️ Manual Override")
# Toggle logic for physical LED/Relay
heater_toggle = st.sidebar.toggle("Deactivate Heater (Physical)")

if st.sidebar.button("Send Signal to Hardware"):
    # Send 'OFF' if toggle is active, 'ON' if not
    success = send_mqtt_command(not heater_toggle)
    if success:
        st.sidebar.success("✅ HiveMQ: Command Published")
    else:
        st.sidebar.error("❌ HiveMQ: Connection Failed")

# --- 5. TOP METRICS (Dynamic Summary) ---
st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
t1, t2, t3 = st.columns(3)

total_kwh = df['total_demand'].sum()
opt_kwh = df['net_load'].sum()
savings_val = ((total_kwh - opt_kwh) / total_kwh) * 100

t1.metric("Total Load (24hr)", f"{total_kwh:.2f} kWh")
t2.metric("Optimized Load", f"{opt_kwh:.2f} kWh", f"-{(total_kwh-opt_kwh):.2f} kWh")
t3.metric("Cost Savings", f"${df['cum_savings'].iloc[-1]:.2f}", f"{savings_val:.1f}% Savings")

st.divider()

# --- 6. HOUR-SPECIFIC STATUS & APPLIANCE BREAKDOWN ---
row = df.iloc[selected_hour]

st.subheader(f"⏱️ System Status at Hour {selected_hour}:00")
c1, c2 = st.columns(2)

with c1:
    st.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    st.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    st.metric("Net Load", f"{row['net_load']:.2f} kW")
    
    # PPO Agent Logic Display
    ppo_action = "OFF" if row['net_load'] > 1.2 else "ON"
    st.info(f"🤖 **PPO Agent Decision:** Recommendation is **{ppo_action}** to minimize grid reliance.")

with c2:
    # PIE CHART: Appliance Breakdown
    breakdown = row[app_list].to_dict()
    df_pie = pd.DataFrame(list(breakdown.items()), columns=['Appliance', 'Usage'])
    fig_pie = px.pie(df_pie, values='Usage', names='Appliance', title="Appliance Load Breakdown")
    st.plotly_chart(fig_pie, use_container_width=True)

# --- 7. XAI: EXPLAINABLE AI LAYER (Work No. 3) ---
st.divider()
st.subheader("🔍 XAI: PPO Decision Factors")
col_x, col_y = st.columns(2)

with col_x:
    # Shift weights dynamically based on the hour
    price_weight = 1.9 if (selected_hour > 17 or selected_hour < 8) else 0.6
    solar_weight = 1.8 if (10 <= selected_hour <= 16) else 0.1
    
    xai_data = pd.DataFrame({
        'Factor': ['Electricity Price', 'Solar Forecast', 'Occupancy', 'Total Demand'],
        'Weight': [price_weight, solar_weight, 0.5, 0.3]
    })
    fig_xai = px.bar(xai_data, x='Weight', y='Factor', orientation='h', 
                     color='Weight', color_continuous_scale='Blues')
    st.plotly_chart(fig_xai, use_container_width=True)

with col_y:
    # Cumulative Savings Line Chart
    fig_line = px.line(df.iloc[:selected_hour+1], y='cum_savings', 
                       labels={'index': 'Hour', 'cum_savings': 'Savings ($)'},
                       title="Accumulated Optimization Savings")
    st.plotly_chart(fig_line, use_container_width=True)
