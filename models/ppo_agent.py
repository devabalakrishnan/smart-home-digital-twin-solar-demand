import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page configuration for a wide dashboard layout
st.set_page_config(page_title="Residential Digital Twin | Optimization Portal", layout="wide")

# --- DATA LOADING & SYNCHRONIZATION ---
def load_merged_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize solar headers to ensure code compatibility
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge solar generation into the primary dataframe
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # Define appliance columns and handle potential key errors dynamically
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            # Calculate Total Demand and Net Load (Strategy Basis)
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            df_demand['net_load'] = df_demand['total_demand'] - df_demand['solar_gen']
            return df_demand, existing_apps
    return None, []

df, app_list = load_merged_data()

if df is not None:
    st.title("🌐 Digital Twin: 24-Hour Time-Sync Portal")
    
    # --- SIDEBAR CONTROLS ---
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Select Forecast Hour", 0, 23, 12)
    
    # Extract data for the selected synchronization point
    row = df.iloc[selected_hour]
    
    # --- REAL-TIME METRICS ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    m3.metric("Net Load", f"{row['net_load']:.2f} kW")

    # --- VISUALIZATION LAYOUT ---
    col_chart, col_breakdown = st.columns([2, 1])

    with col_chart:
        st.subheader(f"📊 Energy Balance at Hour {selected_hour}:00")
        fig_bar = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                         barmode='group', color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_breakdown:
        st.subheader("💡 Appliance Breakdown")
        pie_data = {app: row[app] for app in app_list}
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 24-HOUR OPERATIONAL HORIZON ---
    st.subheader("📈 24-Hour Operational Horizon")
    fig_line = px.line(df, y=['solar_gen', 'total_demand'], 
                       color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
    fig_line.add_vline(x=selected_hour, line_dash="dash", line_color="red", annotation_text="Sync Point")
    st.plotly_chart(fig_line, use_container_width=True)

    # ==========================================
    # GLOBAL OPTIMIZATION & COST SAVINGS
    # ==========================================
    st.divider()
    st.subheader("💰 24-Hour Economic Impact Analysis")

    # Time-of-Use (ToU) Grid Pricing Profile
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]

    # Calculation of Daily Costs
    baseline_cost = (df['total_demand'] * grid_prices).sum()

    # Optimized Cost: Only pay for Net Load exceeding solar generation
    df['grid_pull'] = df['net_load'].clip(lower=0)
    optimized_cost = (df['grid_pull'] * grid_prices).sum()

    savings = baseline_cost - optimized_cost
    saving_percent = (savings / baseline_cost) * 100 if baseline_cost > 0 else 0

    # Optimization Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline Daily Cost", f"${baseline_cost:.2f}")
    c2.metric("Optimized Daily Cost", f"${optimized_cost:.2f}", delta=f"-${savings:.2f}")
    c3.metric("Total Cost Savings", f"{saving_percent:.1f}%", delta="Efficiency Gain")

    # Hourly Savings Visualization (Solar Arbitrage)
    df['Hourly Savings'] = (df['total_demand'] * grid_prices) - (df['grid_pull'] * grid_prices)
    fig_savings = px.bar(df, y='Hourly Savings', title="Hourly Financial Savings (Solar Alignment Strategy)",
                         color_discrete_sequence=['green'])
    st.plotly_chart(fig_savings, use_container_width=True)

else:
    st.error("🚨 Configuration Error: Missing 'solar_forecast.csv' or 'next_day_prediction.csv' in /data folder.")
