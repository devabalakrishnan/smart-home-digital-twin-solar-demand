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
        
        # Standardize headers to avoid KeyErrors
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge solar into demand dataframe
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # List of appliances found in your CSV
        app_cols = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            # Net Load = Demand - Solar (clamped to 0)
            df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # 1. GLOBAL DASHBOARD (Top 24-Hour Result)
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    
    # Time-of-Use pricing profile
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]

    total_load_24h = df['total_demand'].sum()
    # This reflects your research target of ~12.93 kWh
    optimized_load_24h = df['net_load'].sum() 
    total_savings = (df['total_demand'] * grid_prices).sum() - (df['net_load'] * grid_prices).sum()

    st.markdown("### **System Performance Summary (24-Hour Horizon)**")
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", f"{total_load_24h:.2f} kWh")
    g2.metric("Optimized Load", f"{optimized_load_24h:.2f} kWh", f"-{(total_load_24h - optimized_load_24h):.2f} kWh (Solar Offset)")
    g3.metric("Total Cost Optimization", f"${total_savings:.2f}", f"{(total_savings/((df['total_demand']*grid_prices).sum())*100):.1f}% Savings")

    st.divider()

    # 2. CURRENT DATA DISPLAY (Updates via Slider)
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 19) 
    row = df.iloc[selected_hour]

    st.subheader(f"⏱️ Current Hourly Status (Hour {selected_hour}:00)")
    # This section was missing or not updating in your previous screenshots
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    m3.metric("Current Net Load", f"{row['net_load']:.2f} kW")

    # 3. SMART RECOMMENDATION BOX
    current_price = grid_prices[selected_hour]
    hour_app_data = {app: row[app] for app in app_list}
    top_app = max(hour_app_data, key=hour_app_data.get)
    
    with st.container():
        if current_price >= 0.40:
            st.error(f"⚠️ **High Tariff (${current_price:.2f}/kWh):** Consider deactivating the **{top_app}** to save costs.")
        elif row['solar_gen'] > row['total_demand']:
            st.success(f"☀️ **Solar Surplus:** Run your **{top_app}** now to use free renewable energy.")
        else:
            st.info(f"ℹ️ **Stable:** Current load is managed. **{top_app}** is your main consumer.")

    # 4. XAI GRAPHS: BAR CHART & APPLIANCE BREAKDOWN
    st.write("---")
    col_bar, col_pie = st.columns([2, 1])
    
    with col_bar:
        st.subheader(f"📊 XAI Energy Balance (Hour {selected_hour}:00)")
        fig_bar = px.bar(df.iloc[[selected_hour]], 
                         y=['solar_gen', 'total_demand'], 
                         barmode='group', 
                         color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.subheader("💡 Appliance Breakdown")
        # Fixed: Ensuring names are displayed in the legend and on the chart
        fig_pie = px.pie(names=list(hour_app_data.keys()), 
                         values=list(hour_app_data.values()), 
                         hole=0.4)
        fig_pie.update_traces(textinfo='label+percent')
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.error("🚨 System Offline: Missing CSV data in the /data folder.")
