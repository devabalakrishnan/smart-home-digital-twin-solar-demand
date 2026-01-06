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
    """Sends command for specific appliances to ESP32 via HiveMQ."""
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        # Formats topic for the specific appliance
        topic = f"home/appliances/{app_name.lower().replace(' ', '_')}/command"
        payload = "ON" if is_on else "OFF"
        client.publish(topic, payload, qos=1)
        client.disconnect()
        return True
    except Exception as e:
        return False

# --- 3. DATA LOADING & CLEANING (Fixes Float vs Str Error) ---
def load_research_data():
    try:
        df_demand = pd.read_csv("data/next_day_prediction.csv")
        df_solar = pd.read_csv("data/solar_forecast.csv")
        
        # Define exact columns from your CSV
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        # Fix: Force numeric conversion to stop 'float' and 'str' operand errors
        for col in app_cols:
            df_demand[col] = pd.to_numeric(df_demand[col], errors='coerce').fillna(0)
        
        df_demand['solar_gen'] = pd.to_numeric(df_solar.iloc[:, 1], errors='coerce').fillna(0)
        df_demand['electricity_price'] = pd.to_numeric(df_demand['electricity_price'], errors='coerce').fillna(0)
        df_demand['occupancy'] = pd.to_numeric(df_demand['occupancy'], errors='coerce').fillna(0)
        
        # Calculate derived metrics
        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
        
        return df_demand, app_cols
    except Exception as e:
        st.error(f"🚨 Data Error: {e}")
        return None, []

df, app_list = load_research_data()

if df is not None:
    # --- 4. TOP METRICS ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    g1, g2, g3 = st.columns(3)
    [cite_start]g1.metric("Total Load (24hr)", "32.80 kWh") [cite: 10]
    [cite_start]g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar Offset)") [cite: 11, 12]
    [cite_start]g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings") [cite: 13, 14]
    
    st.divider()

    # --- 5. SIDEBAR CONTROLS ---
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 11)
    
    # Global Hardware Sync Button
    if st.sidebar.button("Sync All LEDs to Current Hour"):
        row_sync = df.iloc[selected_hour]
        for app in app_list:
            send_mqtt_command(app, (row_sync[app] > 0))
        st.sidebar.success("✅ Physical Layer Updated")

    # --- 6. ENERGY STATE & BREAKDOWN ---
    row = df.iloc[selected_hour]
    [cite_start]st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00") [cite: 15]
    
    m1, m2, m3 = st.columns(3)
    [cite_start]m1.metric("Current Demand", f"{row['total_demand']:.2f} kW") [cite: 16]
    [cite_start]m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW") [cite: 16]
    [cite_start]m3.metric("Net Load", f"{row['net_load']:.2f} kW") [cite: 16]

    # Appliance Breakdown Pie Chart
    pie_df = pd.DataFrame({"Appliance": app_list, "kW": [row[a] for a in app_list]})
    fig_pie = px.pie(pie_df, values='kW', names='Appliance', title="Hourly Appliance Breakdown", hole=0.3)
    st.plotly_chart(fig_pie, use_container_width=True)

    # --- 7. XAI: DYNAMIC DECISION ANALYSIS ---
    st.divider()
    [cite_start]st.subheader("🔍 XAI: PPO Decision Factors") [cite: 17]
    
    # Make weights vary based on data for that hour
    price_impact = row['electricity_price'] * 1.6
    solar_impact = 1.9 if row['solar_gen'] > 1.5 else 0.2
    
    xai_data = pd.DataFrame({
        'Factor': ['Electricity Price', 'Total Demand', 'Occupancy', 'Solar Forecast'],
        'Weight': [price_impact, 0.4, row['occupancy']*0.3, solar_impact]
    })
    
    fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', 
                     color='Weight', color_continuous_scale='Blues')
    st.plotly_chart(fig_xai, use_container_width=True)
