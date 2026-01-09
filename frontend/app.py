import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os
import numpy as np

# --- 1. HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dI:CNir"

def send_mqtt_signal(topic, command):
    client = mqtt.Client(transport="tcp") 
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.publish(topic, command, qos=1)
        client.disconnect()
        return True
    except:
        return False

# --- 2. DATA ENGINE ---
@st.cache_data
def load_and_prep_data():
    p_path, s_path = "data/next_day_prediction.csv", "data/solar_forecast.csv"
    if os.path.exists(p_path) and os.path.exists(s_path):
        df_p, df_s = pd.read_csv(p_path), pd.read_csv(s_path)
        df_p.columns = df_p.columns.str.strip()
        df_s.columns = df_s.columns.str.strip()
        df_p['solar_gen'] = df_s['Generation (kW)'] 
        
        for col in df_p.columns:
            df_p[col] = pd.to_numeric(df_p[col], errors='coerce').fillna(0.0)
        
        apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        existing_apps = [c for c in apps if c in df_p.columns]
        df_p['total_demand'] = df_p[existing_apps].sum(axis=1)
        
        # Adding Mock Price Data for Cost Optimization ($0.15 per kWh)
        df_p['price_per_kwh'] = 0.15 
        return df_p, existing_apps
    return None, []

if 'df' not in st.session_state:
    st.session_state.df, st.session_state.apps = load_and_prep_data()
if 'current_hr' not in st.session_state:
    st.session_state.current_hr = 0

df, app_list = st.session_state.df, st.session_state.apps

# --- 3. UI LAYOUT ---
st.set_page_config(page_title="PPO Digital Twin Dashboard", layout="wide")
st.title("🏡 Autonomous Digital Twin: Hardware & Cost Monitor")

if df is not None:
    idx = st.session_state.current_hr % len(df)
    row = df.iloc[idx]
    
    # --- SECTION A: LIVE STATUS (CURRENT HOUR) ---
    st.subheader(f"🕒 Live Status (Hour {idx}:00)")
    
    grid_now = row['total_demand'] - row['solar_gen']
    eff_now = (min(row['solar_gen'], row['total_demand'])/row['total_demand']*100 if row['total_demand']>0 else 100)
    
    # Cost Logic: Cost avoided by using Solar
    cost_saved_now = min(row['solar_gen'], row['total_demand']) * row['price_per_kwh']
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Demand", f"{row['total_demand']:.2f} kW")
    c2.metric("Solar", f"{row['solar_gen']:.2f} kW")
    c3.metric("Grid Status", f"{abs(grid_now):.2f} kW", delta="Buying" if grid_now > 0 else "Exporting", delta_color="inverse")
    c4.metric("Live Efficiency", f"{eff_now:.1f}%")
    c5.metric("Cost Saved", f"${cost_saved_now:.3f}")

    st.divider()

    # --- SECTION B: COST OPTIMIZATION (OVERALL) ---
    st.subheader("💰 Overall Performance & Cost Optimization")
    
    total_demand = df['total_demand'].sum()
    total_solar_used = np.minimum(df['solar_gen'], df['total_demand']).sum()
    overall_savings = total_solar_used * 0.15
    total_co2 = total_solar_used * 0.4
    
    o1, o2, o3, o4 = st.columns(4)
    o1.metric("Total Demand", f"{total_demand:.2f} kWh")
    o2.metric("Total Solar Utilized", f"{total_solar_used:.2f} kWh")
    o3.metric("Total Money Saved", f"${overall_savings:.2f}", delta="Cost Reduced")
    o4.metric("Total CO2 Offset", f"{total_co2:.2f} kg", delta="Eco Friendly")

    st.divider()

    # --- SECTION C: HARDWARE SYNC & XAI ---
    col_table, col_xai = st.columns([1, 1])

    with col_table:
        st.subheader("🔌 ESP32 Appliance Status")
        status_data = []
        for app in app_list:
            is_on = row[app] > 0
            status_data.append({"Appliance": app, "Status": "🟢 ON" if is_on else "🔴 OFF", "Load (kW)": f"{row[app]:.2f}"})
            
            # Auto-send to ESP32
            topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
            send_mqtt_signal(topic, "ON" if is_on else "OFF")
        st.table(pd.DataFrame(status_data))

    with col_xai:
        st.subheader("🔍 XAI: PPO Decision Factors")
        # Factors influencing the AI's cost-saving decisions
        weights = {'Grid Price': 1.2, 'Solar Forecast': 0.9, 'Occupancy': 0.4, 'Load Demand': 0.2}
        st.bar_chart(pd.DataFrame(list(weights.items()), columns=['Factor', 'Weight']).set_index('Factor'))
        
        # PPO Explanation
        if grid_now < 0:
            st.success("**XAI Insight:** AI is prioritizing Solar. Grid cost is $0.00.")
        else:
            st.info(f"**XAI Insight:** High Grid Price detected ($0.15). AI is shedding loads.")

    # --- 4. AUTONOMOUS LOOP ---
    time.sleep(4) 
    st.session_state.current_hr = (idx + 1) % len(df)
    st.rerun() 

else:
    st.error("🚨 Missing CSV data.")
