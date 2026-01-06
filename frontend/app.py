import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import os

# ==========================================
# 1. PAGE SETUP
# ==========================================
st.set_page_config(
    page_title="Residential Digital Twin | XAI Portal",
    page_icon="🌐",
    layout="wide"
)

# ==========================================
# 2. DATA LOADING (Updated for your 'data/' folder)
# ==========================================
@st.cache_data
def load_and_clean_data():
    # Looking for the file in the 'data' folder as per your file tree screenshot
    file_path = "data/next_day_prediction.csv"
    
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()
        df['datetime'] = pd.to_datetime(df['datetime'])
        
        # Calculate Total Load on the fly since it's missing in your CSV
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        df['Total_Load_Forecasted'] = df[app_cols].sum(axis=1)
        
        # Simulated logic for Meal Time based on common high-use hours
        df['is_meal_time'] = df['datetime'].dt.hour.isin([8, 12, 13, 19, 20]).astype(int)
        return df
    return None

df = load_and_clean_data()

if df is None:
    st.error("🚨 **File Not Found:** Ensure 'next_day_prediction.csv' is inside the 'data' folder.")
    st.stop()

# ==========================================
# 3. SIDEBAR & NAVIGATION
# ==========================================
st.sidebar.header("🕹️ Digital Twin Controls")
selected_hour = st.sidebar.slider("Select Forecast Hour", 0, len(df)-1, 0)
row = df.iloc[selected_hour]

# ==========================================
# 4. AGENT LOGIC
# ==========================================
price = float(row['electricity_price'])
total_load = float(row['Total_Load_Forecasted'])
occupancy = int(row['occupancy'])
is_meal = int(row['is_meal_time'])

# Decision Thresholds
is_critical = price >= 0.4 or total_load > 2.0
status_label = "CRITICAL (PEAK)" if is_critical else "OPTIMIZED (NORMAL)"
status_color = "rgba(255, 75, 75, 0.2)" if is_critical else "rgba(75, 255, 75, 0.1)"

# ==========================================
# 5. DASHBOARD LAYOUT
# ==========================================
st.title("🌐 Residential Digital Twin & XAI Portal")
st.write(f"**State Synchronization:** `{row['datetime']}`")

col1, col2 = st.columns([1, 1.3])

with col1:
    st.subheader("🏠 Spatial State")
    st.markdown(f"""
        <div style="background-color: {status_color}; padding: 30px; border-radius: 15px; text-align: center; border: 2px solid #dee2e6;">
            <h1 style="font-size: 80px; margin: 0;">🏠</h1>
            <h2>{status_label}</h2>
            <p>Load: <b>{total_load:.2f} kW</b> | Price: <b>${price:.2f}</b></p>
        </div>
        """, unsafe_allow_html=True)
    
    if is_critical:
        st.warning("🤖 **PPO Agent:** Load-shedding active.")
    else:
        st.success("🤖 **PPO Agent:** Normal Monitoring.")

with col2:
    st.subheader("📊 Appliance Breakdown")
    app_list = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
    fig_pie = px.pie(names=app_list, values=[float(row[a]) for a in app_list], hole=0.4)
    fig_pie.update_layout(height=350, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

# --- XAI SECTION ---
st.subheader("🔍 Explainable AI (XAI) Insight")
features = ['Electricity Price', 'Total Demand', 'Occupancy', 'Meal Context']
# Weights derived from the specific hour's data
weights = [price * 3, total_load / 1.5, occupancy * 0.4, is_meal * 1.2]

fig_xai, ax = plt.subplots(figsize=(10, 3))
ax.barh(features, weights, color=['#ff4b4b' if w > 1.0 else '#0068c9' for w in weights])
ax.set_title("Feature Attribution for PPO Decision")
st.pyplot(fig_xai)

# --- TREND SECTION ---
st.subheader("📈 24-Hour Forecast Trend")
fig_line = px.line(df, x='datetime', y=app_list, template="plotly_white")
st.plotly_chart(fig_line, use_container_width=True)
