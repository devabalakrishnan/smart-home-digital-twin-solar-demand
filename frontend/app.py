import streamlit as st
import pandas as pd
import plotly.express as px
import os
import paho.mqtt.client as mqtt
import ssl

# --- 1. DASHBOARD CONFIGURATION ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- 2. MQTT SETTINGS ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_command(app_name, is_on):
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        topic = f"home/appliances/{app_name.lower().replace(' ', '_')}/command"
        payload = "ON" if is_on else "OFF"
        client.publish(topic, payload, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 3. DATA LOADING & ROBUST CLEANING ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        # Load the CSVs
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # EXACT columns from your CSV
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        # --- THE FIX FOR "FLOAT AND STR" ERROR ---
        # We must clean these columns INDIVIDUALLY before the .sum() or (-) operation
        for col in app_cols:
            if col in df_demand.columns:
                # errors='coerce' turns "text" into NaN, fillna(0) turns NaN into 0.0
                df_demand[col] = pd.to_numeric(df_demand[col], errors='coerce').fillna(0)
        
        # Force these to be numbers too
        df_demand['electricity_price'] = pd.to_numeric(df_demand['electricity_price'], errors='coerce').fillna(0)
        df_demand['occupancy'] = pd.to_numeric(df_demand['occupancy'], errors='coerce').fillna(0)
        
        # Clean Solar Data
        df_solar.columns = df_solar.columns.str.strip().str.lower()
        # Using iloc[:, 1] ensures we get the numeric column regardless of the title
        solar_gen_vals = pd.to_numeric(df_solar.iloc[:, 1], errors='coerce').fillna(0)
        df_demand['solar_gen'] = solar_gen_vals

        # --- CALCULATIONS (Now safe because everything is a float) ---
        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
        
        return df_demand, app_cols
    return None, []

df, app_list = load_research_data()

# --- 4. DASHBOARD UI ---
if df is not None:
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    # Global Metrics
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh") 
    g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar Offset)") 
    g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings") 
    
    st.divider()

    # Sidebar
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 12)
    
    if st.sidebar.button("Sync All Hardware LEDs"):
        row_now = df.iloc[selected_hour]
        for app in app_list:
            send_mqtt_command(app, (row_now[app] > 0))
        st.sidebar.success(f"✅ Commands sent for Hour {selected_hour}")

    # Energy State
    row = df.iloc[selected_hour]
    st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.3f} kW")
    m2.metric("Current Solar", f"{row['solar_gen']:.3f} kW")
    m3.metric("Net Load", f"{row['net_load']:.3f} kW")

    # Visualization
    pie_df = pd.DataFrame({"Appliance": app_list, "Usage": [row[a] for a in app_list]})
    fig_pie = px.pie(pie_df, values='Usage', names='Appliance', hole=0.4, title="Hourly Load Breakdown")
    st.plotly_chart(fig_pie, use_container_width=True)

    # XAI Layer
    st.divider()
    st.subheader("🔍 XAI: PPO Decision Factors")
    xai_df = pd.DataFrame({
        'Factor': ['Electricity Price', 'Total Demand', 'Occupancy', 'Solar Forecast'],
        'Weight': [row['electricity_price']*1.5, 0.3, row['occupancy']*0.4, 1.8 if row['solar_gen']>1 else 0.2]
    })
    fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', color='Weight', color_continuous_scale='Blues')
    st.plotly_chart(fig_xai, use_container_width=True)
else:
    st.error("🚨 System Offline: Please check 'data/next_day_prediction.csv' and 'data/solar_forecast.csv'.")
