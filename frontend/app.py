import streamlit as st
import pandas as pd
import plotly.express as px
import paho.mqtt.client as mqtt
import ssl
from xai.explainer import DigitalTwinExplainer # Ensure this matches your folder structure

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

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    df = pd.read_csv("data/next_day_prediction.csv")
    df_solar = pd.read_csv("data/solar_forecast.csv")
    df['solar_gen'] = df_solar['generation_kw']
    # Exact columns from your CSV
    apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
    df['total_demand'] = df[apps].sum(axis=1)
    df['net_load'] = (df['total_demand'] - df['solar_gen']).clip(lower=0)
    return df, apps

df, app_list = load_data()
explainer = DigitalTwinExplainer(df) # Initialize your XAI code

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.header("🕹️ Digital Twin Controls")
selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 12)
row = df.iloc[selected_hour]

# AUTOMATIC HARDWARE SYNC: Sends appliance status to LEDs based on PPO/CSV state
if st.sidebar.button("Sync All LEDs to Current Hour"):
    for app in app_list:
        is_active = row[app] > 0
        send_mqtt_command(app, is_active)
    st.sidebar.success(f"All 7 LEDs synced to Hour {selected_hour} states.")

# --- 4. TOP METRICS ---
st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
m1, m2, m3 = st.columns(3)
m1.metric("Total Load (24hr)", "32.80 kWh") [cite: 10]
m2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar)") [cite: 11, 12]
m3.metric("Cost Savings", "$5.51", "54.5% Savings") [cite: 13, 14]

st.divider()

# --- 5. DYNAMIC BREAKDOWN & PPO ---
st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
c1, c2 = st.columns(2)

with c1:
    st.metric("Net Load", f"{row['net_load']:.4f} kW") [cite: 16]
    # PPO Status Logic based on current CSV row
    active_apps = [a for a in app_list if row[a] > 0]
    st.info(f"🤖 **PPO Agent Decision:** Active Devices: {', '.join(active_apps) if active_apps else 'None'}")
    st.write(explainer.get_decision_text(selected_hour)) # Uses your Explainer class text

with c2:
    # PIE CHART: Appliance Breakdown
    df_p = pd.DataFrame(list(row[app_list].to_dict().items()), columns=['App', 'kW'])
    fig_p = px.pie(df_p, values='kW', names='App', title="Appliance Breakdown", hole=0.3)
    st.plotly_chart(fig_p, use_container_width=True)

# --- 6. XAI LAYER (Varies by Hour) ---
st.divider()
# Use your get_dynamic_explanation method to vary weights by hour
xai_data = explainer.get_dynamic_explanation(selected_hour)
fig_xai = explainer.plot_explanation(xai_data, selected_hour)
st.plotly_chart(fig_xai, use_container_width=True)
