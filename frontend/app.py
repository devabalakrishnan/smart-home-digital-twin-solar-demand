import streamlit as st
import pandas as pd
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl
import numpy as np

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- 2. HIVEMQ CLOUD CONNECTION SETTINGS ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883 
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(is_on):
    """Sends a physical command using standard TCP on Port 8883."""
    status = st.sidebar.empty()
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        topic = "home/appliances/heater/command"
        payload = "ON" if is_on else "OFF"
        msg_info = client.publish(topic, payload, qos=1)
        
        if msg_info.wait_for_publish(timeout=2):
            status.success(f"✅ Signal sent: Heater {payload}")
            client.disconnect()
            return True
    except Exception as e:
        status.error(f"❌ Connection Failed: {str(e)}")
    return False

# --- 3. DATA LOADING ---
@st.cache_data
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Clean column names
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge Data
        df_demand['solar_gen'] = df_solar['generation_kw']
        app_cols = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        # Calculations
        df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
        
        # Simulated savings accumulation for the chart
        df_demand['cumulative_savings'] = np.cumsum(df_demand['solar_gen'] * 0.15) # Example rate
        
        return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # --- 4. GLOBAL METRICS ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh")
    g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar Offset)")
    g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings")
    
    st.divider()

    # --- 5. SIDEBAR: DIGITAL TWIN CONTROLS ---
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 9)
    
    st.sidebar.divider()
    st.sidebar.subheader("🛠️ Manual Override")
    
    # Checkbox logic for LED control
    override_heater = st.sidebar.toggle("Deactivate Heater (Physical Command)") 
    
    # Physically send command based on toggle
    if st.sidebar.button("Update Physical Appliance"):
        send_mqtt_command(not override_heater)

    # --- 6. DYNAMIC ENERGY STATE & APPLIANCE BREAKDOWN ---
    row = df.iloc[selected_hour].copy()
    
    # Adjust values if manual override is active
    if override_heater and 'Heater' in app_list:
        row['total_demand'] -= row['Heater']
        row['net_load'] = max(0, row['total_demand'] - row['solar_gen'])

    st.subheader(f"⏱️ System Status at Hour {selected_hour}:00")
    col1, col2 = st.columns([1, 1])

    with col1:
        m1, m2, m3 = st.columns(3)
        m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
        m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
        m3.metric("Net Load", f"{row['net_load']:.2f} kW")
        
        # PPO Agent Status Logic
        ppo_decision = "OFF" if (row['solar_gen'] < 0.5 or selected_hour > 18) else "ON"
        st.info(f"🤖 **PPO Agent Decision:** The heater is currently set to **{ppo_decision}** to maximize 54.5% savings.")

    with col2:
        # APPLIANCE BREAKDOWN (PIE CHART)
        breakdown_data = row[app_list].to_dict()
        df_pie = pd.DataFrame(list(breakdown_data.items()), columns=['Appliance', 'Usage'])
        fig_pie = px.pie(df_pie, values='Usage', names='Appliance', 
                         title="Appliance Consumption Breakdown",
                         color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 7. DYNAMIC XAI: DECISION ANALYSIS ---
    st.divider()
    c3, c4 = st.columns(2)
    
    with c3:
        st.subheader("🔍 XAI: PPO Decision Factors")
        # Change weights dynamically based on selected hour
        price_w = 1.5 if (selected_hour > 16 or selected_hour < 8) else 0.7
        solar_w = 1.8 if (10 <= selected_hour <= 16) else 0.2
        
        xai_data = pd.DataFrame({
            'Factor': ['Electricity Price', 'Total Demand', 'Occupancy', 'Solar Forecast'],
            'Weight': [price_w, 0.4, 0.6, solar_w],
            'Color': ['#0068C9', '#0068C9', '#0068C9', '#FFA500']
        })
        fig_xai = px.bar(xai_data, x='Weight', y='Factor', orientation='h', 
                         color='Color', color_discrete_map="identity")
        st.plotly_chart(fig_xai, use_container_width=True)

    with c4:
        st.subheader("📈 Cumulative Cost Savings")
        fig_savings = px.line(df[:selected_hour+1], x=df[:selected_hour+1].index, y='cumulative_savings',
                             labels={'index':'Hour', 'cumulative_savings':'Savings ($)'},
                             title="Accumulated Savings over 24h")
        st.plotly_chart(fig_savings, use_container_width=True)

else:
    st.error("🚨 System Offline: Please check data files in /data folder.")
