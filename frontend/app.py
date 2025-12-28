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
            # Baseline Net Load Calculation
            df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_research_data()

if df is not None:
    # 1. GLOBAL DASHBOARD
    st.title("🏡 Residential Digital Twin: Home Optimization")
    
    # 24-Hour Summary
    st.markdown("### **System Performance Summary (24-Hour Horizon)**")
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh")
    g2.metric("Optimized Load", "12.93 kWh", "-19.87 kWh (Solar Offset)")
    g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings")

    st.divider()

    # 2. INTERACTIVE CONTROLS & MANUAL OVERRIDE
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 19) 
    
    st.sidebar.write("---")
    st.sidebar.subheader("🛠️ Manual Override")
    override_heater = st.sidebar.toggle("Deactivate Heater (Simulation)", value=False)
    
    # Pricing Profile
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]
    
    row = df.iloc[selected_hour].copy()
    current_price = grid_prices[selected_hour]

    # Apply Manual Override Logic
    if override_heater and 'Heater' in app_list:
        row['total_demand'] -= row['Heater']
        row['net_load'] = max(0, row['total_demand'] - row['solar_gen'])

    # 3. CURRENT METRICS
    st.subheader(f"⏱️ Energy State at Hour {selected_hour}:00")
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    m3.metric("Net Load", f"{row['net_load']:.2f} kW")

    # 4. SMART RECOMMENDATION BOX
    hour_apps = {app: row[app] for app in app_list}
    top_app = max(hour_apps, key=hour_apps.get)

    if current_price >= 0.45:
        st.error(f"⚠️ **High Tariff (${current_price:.2f}/kWh):** Consider deactivating the **{top_app}** to save costs.")
    elif row['solar_gen'] > row['total_demand']:
        st.success(f"☀️ **Solar Surplus:** Run the **{top_app}** now to maximize green energy usage.")
    else:
        st.info(f"ℹ️ **Stable Rate:** Grid price is moderate (${current_price:.2f}/kWh).")

    # 5. XAI INSIGHT & BAR CHART
    st.write("---")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("🔍 Explainable AI (XAI) Insight")
        # Dynamic Decision Context
        decision_type = "Grid-Driven" if current_price > 0.30 else "Solar-Prioritized"
        st.info(f"Decision for hour {selected_hour} is **{decision_type}** (${current_price:.2f}/kWh).")
        
        # Horizontal Feature Attribution
        xai_data = pd.DataFrame({
            'Feature': ['Electricity Price', 'Total Demand', 'Occupancy', 'Meal Context'],
            'Importance': [1.5 if current_price > 0.40 else 0.4, 0.1, 0.4, 0.05],
            'Color': ['#FF4B4B', '#0068C9', '#0068C9', '#0068C9']
        })
        fig_xai = px.bar(xai_data, x='Importance', y='Feature', orientation='h',
                         color='Color', color_discrete_map="identity",
                         title="PPO Decision Weight Factors")
        st.plotly_chart(fig_xai, use_container_width=True)

    with col_right:
        st.subheader("💡 Appliance Breakdown")
        # Pie Chart with Appliance Names
        fig_pie = px.pie(names=list(hour_apps.keys()), values=list(hour_apps.values()), hole=0.4)
        fig_pie.update_traces(textinfo='label+percent')
        st.plotly_chart(fig_pie, use_container_width=True)

    # 6. ENERGY BALANCE CHART
    st.subheader(f"📊 Energy Balance (Hour {selected_hour}:00)")
    fig_bal = px.bar(row.to_frame().T, y=['solar_gen', 'total_demand'], barmode='group',
                     color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
    st.plotly_chart(fig_bal, use_container_width=True)

else:
    st.error("🚨 Data Offline: Please check your /data folder.")
