import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set wide layout for the research dashboard
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- DATA LOADING ---
def load_research_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize headers
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge data
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # Appliance columns list
        app_cols = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            df_demand['optimized_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # =========================================================
    # 1. GLOBAL DASHBOARD (Top Metrics)
    # =========================================================
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
    c2.metric("Optimized Load", f"{optimized_load_val:.2f} kWh", f"-{(total_load_val - optimized_load_val):.2f} kWh (Solar Offset)")
    c3.metric("Total Cost Optimization", f"${total_savings:.2f}", f"{(total_savings/((df['total_demand'] * grid_prices).sum())*100):.1f}% Savings")

    st.divider()

    # =========================================================
    # 2. HOUR-WISE & APPLIANCE-WISE DETAILS (Interactive)
    # =========================================================
    st.sidebar.header("🕹️ Digital Twin Controls")
    # This slider controls the details below
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 19) 
    row = df.iloc[selected_hour]

    col_bar, col_pie = st.columns([2, 1])

    with col_bar:
        st.subheader(f"📊 Energy State at Hour {selected_hour}:00")
        # Bar chart showing Solar vs Demand at that specific hour
        fig_bar = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                         barmode='group', labels={'value': 'kW', 'variable': 'Category'},
                         color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.subheader("💡 Appliance Breakdown")
        # Pie chart showing how much each appliance contributes at that hour
        pie_data = {app: row[app] for app in app_list}
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), hole=0.4)
        fig_pie.update_layout(showlegend=True, height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

    # =========================================================
    # 3. XAI INSIGHT (Contextual Logic)
    # =========================================================
    st.subheader("🔍 XAI Insight")
    current_price = grid_prices[selected_hour]
    if row['solar_gen'] > row['total_demand']:
        st.success(f"Hour {selected_hour}: Load is fully covered by Solar energy ({row['solar_gen']:.2f} kW). Grid dependency is 0.")
    else:
        st.info(f"Hour {selected_hour}: Decision is Grid-Driven due to high tariff (${current_price:.2f}/kWh). Recommendation: Shift non-essential loads.")

else:
    st.error("🚨 Data files missing. Check your /data folder.")
