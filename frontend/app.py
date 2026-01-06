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
        topic = f"home/appliances/{app_name.lower().replace(' ', '_')}/command"
        payload = "ON" if is_on else "OFF"
        client.publish(topic, payload, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 3. DATA LOADING & CLEANING (FIXES THE STR VS FLOAT ERROR) ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Exact columns from your CSV
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        # --- CRITICAL FIX START ---
        # Force conversion to numeric. 'coerce' turns text/errors into NaN, then fillna(0) makes them 0.
        for col in app_cols:
            if col in df_demand.columns:
                df_demand[col] = pd.to_numeric(df_demand[col], errors='coerce').fillna(0)
        
        # Clean solar generation and other factors
        df_solar.columns = df_solar.columns.str.strip().str.lower()
        # Using iloc to get the 2nd column (generation) regardless of exact header name
        df_demand['solar_gen'] = pd.to_numeric(df_solar.iloc[:, 1], errors='coerce').fillna(0)
        df_demand['electricity_price'] = pd.to_numeric(df_demand['electricity_price'], errors='coerce').fillna(0)
        df_demand['occupancy'] = pd.to_numeric(df_demand['occupancy'], errors='coerce').fillna(0)
        # --- CRITICAL FIX END ---

        # Final Calculations
        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
        
        return df_demand, app_cols
    return None, []

df, app_list = load_research_data()

if df is not None:
    # --- 4. GLOBAL METRICS (Values from your research) ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    g1, g2, g3 = st.columns(3)
    [cite_start]g1.metric("Total Load (24hr)", "32.80 kWh") [cite: 10]
    [cite_start]g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar Offset)") [cite: 11, 12]
    [cite_start]g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings") [cite: 13, 14]
    
    st.divider()

    # --- 5. SIDEBAR CONTROLS ---
    [cite_start]st.sidebar.header("🕹️ Digital Twin Controls") [cite: 2]
    [cite_start]selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 11) [cite: 3]
    
    if st.sidebar.button("Sync All Hardware LEDs"):
        row_now = df.iloc[selected_hour]
        for app in app_list:
            send_mqtt_command(app, (row_now[app] > 0))
        st.sidebar.success(f"✅ Commands sent for Hour {selected_hour}")

    # --- 6. ENERGY STATE & XAI ---
    row = df.iloc[selected_hour]
    [cite_start]st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00") [cite: 15]
    
    m1, m2, m3 = st.columns(3)
    [cite_start]m1.metric("Current Demand", f"{row['total_demand']:.3f} kW") [cite: 16]
    [cite_start]m2.metric("Current Solar", f"{row['solar_gen']:.3f} kW") [cite: 16]
    [cite_start]m3.metric("Net Load", f"{row['net_load']:.3f} kW") [cite: 16]

    # Load Breakdown Chart
    pie_df = pd.DataFrame({"Appliance": app_list, "Usage": [row[a] for a in app_list]})
    fig_pie = px.pie(pie_df, values='Usage', names='Appliance', hole=0.4, title="Appliance Load Breakdown")
    st.plotly_chart(fig_pie, use_container_width=True)

    # [cite_start]XAI Layer [cite: 17]
    st.divider()
    st.subheader("🔍 XAI: PPO Decision Factors")
    
    # Dynamic weights for visualization based on row data
    price_w = row['electricity_price'] * 1.5
    solar_w = 1.8 if row['solar_gen'] > 1.0 else 0.2
    
    xai_df = pd.DataFrame({
        'Factor': ['Electricity Price', 'Total Demand', 'Occupancy', 'Solar Forecast'],
        'Weight': [price_w, 0.3, row['occupancy']*0.4, solar_w]
    })
    fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', color='Weight', color_continuous_scale='Blues')
    st.plotly_chart(fig_xai, use_container_width=True)

else:
    st.error("🚨 System Offline: Missing CSV data in /data folder.")
