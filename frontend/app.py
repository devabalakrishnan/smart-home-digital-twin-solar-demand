import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time
import os

# --- HIVEMQ CONFIGURATION ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir" 

if 'mqtt_client' not in st.session_state:
    client = mqtt.Client(client_id="DigitalTwin_Streamlit", transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except Exception as e:
        st.session_state.connected = False

# --- UI & DATA ---
st.title("🏡 Digital Twin: Full Appliance Sync")

# Appliance list matching your dashboard
app_list = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']

# --- UPDATED BROADCAST LOOP ---
if st.session_state.get('connected'):
    # Assume 'row' is your current hour data from the CSV
    for app in app_list:
        status = "ON" # Replace with: "ON" if row[app] > 0 else "OFF"
        topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
        
        # Publish with QoS 1 for guaranteed delivery
        st.session_state.mqtt_client.publish(topic, status, qos=1)
        
        # 0.1s gap is critical for ESP32 stability
        time.sleep(0.1) 
    
    st.success("✅ All 7 signals sent to cloud.")
