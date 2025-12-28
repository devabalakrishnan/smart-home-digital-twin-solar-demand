import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Page Config
st.set_page_config(page_title="Residential Digital Twin | Merged Portal", layout="wide")
st.title("🌐 Integrated Digital Twin: Solar & Demand Optimizer")

# --- DATA LOADING & MERGING ---
def load_merged_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize column names to prevent ValueErrors
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge solar generation into demand dataframe based on index/hour
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # Calculate Total Demand (Summing all appliances)
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        df_demand['total_demand'] = df_demand[app_cols].sum(axis=1)
        
        # Calculate Net Load (Crucial for Scheduling Strategy)
        df_demand['net_load'] = df_demand['total_demand'] - df_demand['solar_gen']
        return df_demand
    return None

df = load_merged_data()

if df is not None:
    # --- TOP LEVEL METRICS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Peak Demand", f"{df['total_demand'].max():.2f} kW")
    m2.metric("Peak Solar", f"{df['solar_gen'].max():.2f} kW")
    m3.metric("Net Grid Reliance", f"{df['net_load'].max():.2f} kW")

    # --- ENERGY BALANCE VISUALIZATION ---
    st.subheader("☀️ Solar Generation vs. 🏠 Household Demand")
    # Plotting both to show the 'overlap'
    fig = px.area(df, x=df.index, y=['solar_gen', 'total_demand'], 
                  labels={'value': 'Power (kW)', 'index': 'Hour'},
                  color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
    st.plotly_chart(fig, use_container_width=True)

    st.success("🤖 **PPO Strategy:** Shifting flexible loads to orange peaks to minimize net grid pull.")
else:
    st.error("🚨 Missing data files in the 'data/' folder. Please check GitHub.")
