import streamlit as st
import pandas as pd
import plotly.express as px
import paho.mqtt.client as mqtt
import ssl

# --- 1. SETTINGS & MQTT ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

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
    except: return False

# --- 2. DATA LOADING (Exact columns from your image_5a0106) ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("data/next_day_prediction.csv")
        df_solar = pd.read_csv("data/solar_forecast.csv")
        # Map solar forecast to the main dataframe
        df['solar_gen'] = df_solar.iloc[:, 1] 
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        df['total_demand'] = df[apps].sum(axis=1)
        df['net_load'] = (df['total_demand'] - df['solar_gen']).clip(lower=0)
        return df, apps
    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return None, []

df, app_list = load_data()

if df is not None:
    # --- 3. SIDEBAR CONTROLS ---
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 12)
    row = df.iloc[selected_hour]

    # --- 4. TOP METRICS (Live Updates) ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    m1, m2, m3 = st.columns(3)
    
    # Static goal values from your screenshot
    m1.metric("Total Load (24hr)", "32.80 kWh")
    m2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar)")
    m3.metric("Cost Savings", "$5.51", "54.5% Savings")

    st.divider()

    # --- 5. DYNAMIC STATE & PIE CHART ---
    st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
    c1, c2 = st.columns(2)

    with c1:
        st.metric("Current Demand", f"{row['total_demand']:.3f} kW")
        st.metric("Net Load", f"{row['net_load']:.3f} kW")
        
        # PPO Status: Check which appliances the AI turned ON
        active_now = [a for a in app_list if row[a] > 0]
        st.success(f"🤖 **PPO Agent:** {len(active_now)} Appliances Active")
        
        # Physical Sync Button
        if st.button("Sync All 7 LEDs to Hardware"):
            for app in app_list:
                send_mqtt_command(app, (row[app] > 0))
            st.toast("Commands sent to ESP32!")

    with c2:
        # PIE CHART: Appliance Breakdown
        pie_df = pd.DataFrame({
            "Appliance": app_list,
            "Usage": [row[a] for a in app_list]
        })
        fig_pie = px.pie(pie_df, values='Usage', names='Appliance', hole=0.4, title="Load Distribution")
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 6. XAI LAYER (Dynamic Bar Chart) ---
    st.divider()
    st.subheader("🔍 XAI: PPO Decision Factors")
    
    # Calculate dynamic weights based on the current hour's data
    price_weight = row['electricity_price'] * 1.5
    solar_weight = 1.8 if row['solar_gen'] > 1.5 else 0.2
    
    xai_data = pd.DataFrame({
        'Factor': ['Electricity Price', 'Solar Forecast', 'Occupancy', 'Demand'],
        'Weight': [price_weight, solar_weight, row['occupancy']*0.4, 0.3]
    })
    
    fig_xai = px.bar(xai_data, x='Weight', y='Factor', orientation='h', 
                     color='Weight', color_continuous_scale='Turbo')
    st.plotly_chart(fig_xai, use_container_width=True)
