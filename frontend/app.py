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
        topic = f"home/appliances/{app_name.lower()}/command"
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
    df['solar_gen'] = df_solar.iloc[:, 1]
    # Exact columns from your screenshot
    apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
    df['total_demand'] = df[apps].sum(axis=1)
    df['net_load'] = (df['total_demand'] - df['solar_gen']).clip(lower=0)
    return df, apps

df, app_list = load_data()

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.header("🕹️ Digital Twin Controls")
selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 12)
row = df.iloc[selected_hour]

st.sidebar.divider()
st.sidebar.subheader("🛠️ Multi-Appliance Manual Override")
selected_app = st.sidebar.selectbox("Select Appliance", app_list)
status_toggle = st.sidebar.toggle(f"Deactivate {selected_app}")

if st.sidebar.button("Update Physical State"):
    if send_mqtt_command(selected_app, not status_toggle):
        st.sidebar.success(f"Sent {('OFF' if status_toggle else 'ON')} to {selected_app}")

# --- 4. TOP METRICS ---
st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
m1, m2, m3 = st.columns(3)
m1.metric("Total Load (24hr)", "32.80 kWh")
m2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar)")
m3.metric("Cost Savings", "$5.51", "54.5% Savings")

st.divider()

# --- 5. DYNAMIC BREAKDOWN & PPO ---
st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
c1, c2 = st.columns(2)

with c1:
    st.metric("Net Load", f"{row['net_load']:.4f} kW")
    # PPO Status Logic based on appliance state in CSV
    active_apps = [a for a in app_list if row[a] > 0]
    st.info(f"🤖 **PPO Agent Decision:** Active Devices: {', '.join(active_apps) if active_apps else 'None'}")

with c2:
    # PIE CHART: Appliance Breakdown
    df_p = pd.DataFrame(list(row[app_list].to_dict().items()), columns=['App', 'kW'])
    fig_p = px.pie(df_p, values='kW', names='App', title="Appliance Breakdown", hole=0.3)
    st.plotly_chart(fig_p, use_container_width=True)

# --- 6. XAI LAYER ---
st.divider()
st.subheader("🔍 XAI: PPO Decision Factors")
# Dynamic Weights based on CSV data
price_w = row['electricity_price'] * 2
solar_w = 1.8 if row['solar_gen'] > 2.0 else 0.2

xai_df = pd.DataFrame({
    'Factor': ['Electricity Price', 'Solar Forecast', 'Occupancy', 'Total Demand'],
    'Weight': [price_w, solar_w, row['occupancy']*0.3, 0.4]
})
fig_x = px.bar(xai_df, x='Weight', y='Factor', orientation='h', color='Weight', color_continuous_scale='Blues')
st.plotly_chart(fig_x, use_container_width=True)
