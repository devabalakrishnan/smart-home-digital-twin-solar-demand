import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- DATA LOADING ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Clean headers
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        df_demand['solar_gen'] = df_solar['generation_kw']
        app_cols = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            # Optimized Load = Total Demand - Solar
            df_demand['optimized_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # 1. GLOBAL DASHBOARD (Total Load, Optimized Load, Total Savings)
    st.title("🏡 Residential Digital Twin: Dashboard")
    
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]

    total_load_val = df['total_demand'].sum()
    optimized_load_val = df['optimized_load'].sum()
    total_savings = (df['total_demand'] * grid_prices).sum() - (df['optimized_load'] * grid_prices).sum()

    st.markdown("### **System Performance Summary (24-Hour Horizon)**")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Load (24hr)", f"{total_load_val:.2f} kWh")
    c2.metric("Optimized Load", f"{optimized_load_val:.2f} kWh", f"-{(total_load_val - optimized_load_val):.2f} kWh")
    c3.metric("Total Cost Optimization", f"${total_savings:.2f}")

    st.divider()

    # 2. SMART RECOMMENDATION ENGINE (NEW & FIXED)
    st.subheader("🤖 AI Smart Recommendations")
    
    # Hour selection via Sidebar
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 19) 
    row = df.iloc[selected_hour]
    current_price = grid_prices[selected_hour]
    
    # Find top consuming appliance for this hour
    hour_app_data = {app: row[app] for app in app_list}
    top_app = max(hour_app_data, key=hour_app_data.get)
    top_app_val = hour_app_data[top_app]

    # Display Recommendation in a colored box
    with st.container():
        if current_price >= 0.40:
            st.error(f"⚠️ **High Tariff Alert at Hour {selected_hour}:00**")
            st.write(f"The grid price is high (**${current_price:.2f}/kWh**). The **{top_app}** is consuming **{top_app_val:.2f} kW**. Deactivating this appliance now would save significant costs.")
        elif row['solar_gen'] > row['total_demand']:
            st.success(f"☀️ **Solar Surplus at Hour {selected_hour}:00**")
            st.write(f"Solar generation (**{row['solar_gen']:.2f} kW**) exceeds your total demand. This is the best time to run your **{top_app}** or other heavy loads for free.")
        else:
            st.info(f"ℹ️ **Status: Normal Operation at Hour {selected_hour}:00**")
            st.write(f"Grid price is moderate (**${current_price:.2f}/kWh**). The **{top_app}** is your primary load. Total net load from grid: **{row['optimized_load']:.2f} kW**.")

    st.write("---")

    # 3. HOUR-WISE & APPLIANCE-WISE VISUALS
    col_bar, col_pie = st.columns([2, 1])
    
    with col_bar:
        st.subheader(f"📊 Energy Balance (Hour {selected_hour}:00)")
        fig_bar = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                         barmode='group', color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.subheader("💡 Appliance Breakdown")
        fig_pie = px.pie(names=list(hour_app_data.keys()), values=list(hour_app_data.values()), hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.error("🚨 System Offline: Missing Data Files.")
