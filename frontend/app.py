import streamlit as st
import pandas as pd
import paho.mqtt.client as mqtt
import ssl
import time

# --- HIVEMQ CREDENTIALS ---
MQTT_HOST = "cyanqueen-29ab69cf.a01.euc1.aws.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.client.1766925863216"
MQTT_PASS = "6<9SwUoy#0D8*dl:CNir"

# PERSISTENT CLIENT: Prevents "No Messages" by staying connected
if 'mqtt_client' not in st.session_state:
    client = mqtt.Client(transport="tcp")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE) 
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start() 
        st.session_state.mqtt_client = client
        st.session_state.connected = True
    except:
        st.session_state.connected = False

# ... (Data loading code remains the same) ...

if 'df' in st.session_state and st.session_state.connected:
    idx = st.session_state.current_hr % len(st.session_state.df)
    row = st.session_state.df.iloc[idx]
    
    # BROADCAST ALL AT ONCE
    for app in st.session_state.apps:
        is_on = "ON" if row[app] > 0 else "OFF"
        topic = f"home/appliances/{app.lower().replace(' ', '_')}/command"
        st.session_state.mqtt_client.publish(topic, is_on, qos=1)
    
    st.success(f"Sent Hour {idx} data to HiveMQ!")
    
    time.sleep(5)
    st.session_state.current_hr += 1
    st.rerun()
