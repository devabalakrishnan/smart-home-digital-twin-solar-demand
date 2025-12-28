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
        
        df_demand['solar_gen'] = df_solar['generation_kw']
        app_cols = ['Heater', 'Microwave', 'Fridge', 'Lights', 'Fans', 'TV']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            df_demand['optimized_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # 1. GLOBAL DASHBOARD (Top Metrics)
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

    # 2. INTERACTIVE CONTROLS (Slider)
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 19) 
    row = df.iloc[selected_hour]

    # 3. AI RECOMMENDATION BOX
    st.subheader("🤖 Smart Home Recommendations")
    current_price = grid_prices[selected_hour]
    
    # Logic for finding the highest consuming appliance
    hour_app_data = {app: row[app] for app in app_list}
    top_app = max(hour_app_data, key=hour_app_data.get)
    
    rec_col1, rec_col2 = st.columns([1, 2])
    
    if current_price >= 0.40:
        with rec_col1:
            st.error("🔴 CRITICAL: High Tariff Window")
        with rec_col2:
            st.warning(f"Grid cost is high (${current_price:.2f}/kWh). Consider deactivating the **{top_app}** to save on energy costs.")
    elif row['solar_gen'] > row['total_demand']:
        with rec_col1:
            st.success("🟢 OPTIMAL: Solar Surplus")
        with rec_col2:
            st.info(f"Solar generation ({row['solar_gen']:.2f} kW) exceeds demand. You can safely run heavy appliances now.")
    else:
        with rec_col1:
            st.info("🟡 NEUTRAL: Balanced Load")
        with rec_col2:
            st.write(f"Energy consumption is steady. The **{top_app}** is currently your largest load.")

    # 4. HOUR-WISE & APPLIANCE-WISE CHARTS
    col_bar, col_pie = st.columns([2, 1])
    with col_bar:
        st.subheader(f"📊 Energy State at Hour {selected_hour}:00")
        fig_bar = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                         barmode='group', color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.subheader("💡 Appliance Breakdown")
        fig_pie = px.pie(names=list(hour_app_data.keys()), values=list(hour_app_data.values()), hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

else:
    st.error("🚨 Data files missing. Check your /data folder.")
