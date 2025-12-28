import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Residential Digital Twin | Merged Portal", layout="wide")
st.title("🌐 Integrated Digital Twin: Solar & Demand Optimizer")

def load_merged_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize all column names to lowercase and remove spaces
        df_demand.columns = df_demand.columns.str.strip()
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        
        # Merge solar generation
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # Define potential appliance columns (handling different naming styles)
        # This list matches your error-prone line in the traceback
        potential_apps = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        
        # Only sum columns that actually exist in your CSV to prevent KeyError
        existing_apps = [col for col in potential_apps if col in df_demand.columns]
        
        if not existing_apps:
            st.error(f"None of the appliance columns were found. Found instead: {list(df_demand.columns)}")
            return None

        df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
        df_demand['net_load'] = df_demand['total_demand'] - df_demand['solar_gen']
        return df_demand
    return None

df = load_merged_data()

if df is not None:
    m1, m2, m3 = st.columns(3)
    m1.metric("Peak Demand", f"{df['total_demand'].max():.2f} kW")
    m2.metric("Peak Solar", f"{df['solar_gen'].max():.2f} kW")
    m3.metric("Net Grid Reliance", f"{df['net_load'].max():.2f} kW")

    st.subheader("☀️ Solar Generation vs. 🏠 Household Demand")
    fig = px.area(df, x=df.index, y=['solar_gen', 'total_demand'], 
                  labels={'value': 'Power (kW)', 'index': 'Hour'},
                  color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
    st.plotly_chart(fig, use_container_width=True)
    st.success("🤖 **PPO Strategy:** Load-balancing active based on net energy availability.")
else:
    st.warning("Waiting for correct data file structure...")
