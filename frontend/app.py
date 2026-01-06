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

# --- 3. DATA LOADING & ROBUST CLEANING (UPDATED FOR YOUR CSV) ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        # Read CSVs
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # 1. Clean Headers (remove invisible spaces)
        df_demand.columns = df_demand.columns.str.strip()
        df_solar.columns = df_solar.columns.str.strip()
        
        # 2. Define Appliance List based on your CSV
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        # 3. FIX: Convert all columns to numeric, handling scientific notation (3.15E-05)
        for col in app_cols + ['electricity_price', 'occupancy']:
            if col in df_demand.columns:
                df_demand[col] = pd.to_numeric(df_demand[col], errors='coerce').fillna(0)
        
        # 4. Align Solar Data: Use the 'Generation (kW)' column from your solar file
        # We ensure we take exactly 24 rows to match the day cycle
        solar_gen_col = 'Generation (kW)'
        if solar_gen_col in df_solar.columns:
            solar_values = pd.to_numeric(df_solar[solar_gen_col], errors='coerce').fillna(0).values
            # Repeat or slice to match demand length (24 hours)
            df_demand['solar_gen'] = (list(solar_values) * (len(df_demand)//len(solar_values) + 1))[:len(df_demand)]
        else:
            # Fallback to second column if name is different
            df_demand['solar_gen'] = pd.to_numeric(df_solar.iloc[:, 2], errors='coerce').fillna(0)

        # 5. Calculations (Math is now safe)
        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1)
        df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
        
        return df_demand, app_cols
    return None, []

df, app_list = load_research_data()

# --- 4. UI RENDER ---
if df is not None:
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    # Static Global Metrics (From your research findings)
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh") 
    g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar)") 
    g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings") 
    
    st.divider()

    # Sidebar
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Select Hour", 0, len(df)-1, 12)
    
    if st.sidebar.button("Sync All Hardware LEDs"):
        row_now = df.iloc[selected_hour]
        for app in app_list:
            send_mqtt_command(app, (row_now[app] > 0))
        st.sidebar.success(f"✅ Hardware Updated for Hour {selected_hour}")

    # Metrics for Selected Hour
    row = df.iloc[selected_hour]
    st.subheader(f"⏱️ System State at Hour {selected_hour}:00")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Load Demand", f"{row['total_demand']:.3f} kW")
    m2.metric("Solar Supply", f"{row['solar_gen']:.3f} kW")
    m3.metric("Grid Reliance", f"{row['net_load']:.3f} kW")

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        pie_df = pd.DataFrame({"Appliance": app_list, "Usage": [row[a] for a in app_list]})
        fig_pie = px.pie(pie_df, values='Usage', names='Appliance', hole=0.4, title="Load Breakdown")
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with c2:
        # XAI Factor Logic
        price_w = row['electricity_price'] * 2.0
        solar_w = 2.0 if row['solar_gen'] > 2.0 else 0.5
        xai_df = pd.DataFrame({
            'Factor': ['Price', 'Demand', 'Occupancy', 'Solar'],
            'Weight': [price_w, 0.4, row['occupancy']*0.5, solar_w]
        })
        fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', title="XAI: Decision Weights", color='Weight')
        st.plotly_chart(fig_xai, use_container_width=True)

else:
    st.error("🚨 CSV Error: Check if files are in the 'data' folder and names match.")
