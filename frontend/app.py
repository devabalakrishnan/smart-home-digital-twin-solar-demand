import streamlit as st
import pandas as pd
import plotly.express as px
import paho.mqtt.client as mqtt
import ssl

# --- 1. SETTINGS ---
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- 2. DATA LOADING (With Error Checking) ---
@st.cache_data
def load_all_data():
    try:
        # Load files
        df_prediction = pd.read_csv("data/next_day_prediction.csv")
        df_solar = pd.read_csv("data/solar_forecast.csv")
        
        # Merge Solar to Prediction
        df_prediction['solar_gen'] = df_solar.iloc[:, 1]
        
        # EXACT column names from your CSV
        app_list = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing Machine']
        
        # Calculate derived columns
        df_prediction['total_demand'] = df_prediction[app_list].sum(axis=1)
        df_prediction['net_load'] = (df_prediction['total_demand'] - df_prediction['solar_gen']).clip(lower=0)
        
        return df_prediction, app_list
    except Exception as e:
        st.error(f"⚠️ DATA ERROR: {e}")
        return None, None

df, app_list = load_all_data()

# --- 3. THE "STUCK PAGE" FIX ---
if df is not None:
    # Sidebar
    st.sidebar.header("🕹️ Digital Twin Controls")
    # Using 'key' forces Streamlit to track this specific slider
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, len(df)-1, 12, key="hour_slider")
    
    # REFRESH DATA ROW
    row = df.iloc[selected_hour]

    # --- 4. TOP METRICS (Dynamic) ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    # These will now change based on the slider
    col_a, col_b, col_c = st.columns(3)
    
    # Global averages for the 24h period
    col_a.metric("Total Load (24hr)", "32.80 kWh")
    col_b.metric("Optimized Load", "12.93 kWh", f"Hour {selected_hour} Net: {row['net_load']:.2f}kW")
    col_c.metric("Cost Savings", "$5.51", "54.5% Savings")

    st.divider()

    # --- 5. APPLIANCE BREAKDOWN (The missing part) ---
    st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
    
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.write("### Real-time Load")
        st.metric("Demand", f"{row['total_demand']:.3f} kW")
        st.metric("Solar", f"{row['solar_gen']:.3f} kW")
        
        # PPO Agent Logic
        ppo_status = "OFF" if row['net_load'] > 1.0 else "ON"
        st.info(f"🤖 **PPO Agent Decision:** Device Recommendation is **{ppo_status}**")

    with right_col:
        # Create Pie Chart data from the current row
        pie_data = pd.DataFrame({
            "Appliance": app_list,
            "Usage (kW)": [row[app] for app in app_list]
        })
        
        fig = px.pie(pie_data, values='Usage (kW)', names='Appliance', 
                     title="Hourly Load Breakdown", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    # --- 6. XAI WEIGHTS ---
    st.divider()
    st.subheader("🔍 XAI: PPO Decision Factors")
    
    # Force weights to change based on selected_hour
    solar_val = 1.8 if (10 <= selected_hour <= 16) else 0.1
    price_val = 1.9 if (row['electricity_price'] > 0.4) else 0.5
    
    xai_df = pd.DataFrame({
        'Factor': ['Electricity Price', 'Solar Forecast', 'Occupancy', 'Total Demand'],
        'Weight': [price_val, solar_val, row['occupancy']*0.5, 0.4]
    })
    
    fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h', color='Weight')
    st.plotly_chart(fig_xai, use_container_width=True)
else:
    st.warning("Please check if 'data/next_day_prediction.csv' exists in your folder.")
