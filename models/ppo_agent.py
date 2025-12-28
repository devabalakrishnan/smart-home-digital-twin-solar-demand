import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page configuration for a wide dashboard layout
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- DATA LOADING & SYNCHRONIZATION LAYER ---
def load_merged_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize headers to prevent KeyErrors
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge datasets
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # Identify available appliance columns
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            # Net Load = What we still need from the grid after using solar
            df_demand['net_load'] = (df_demand['total_demand'] - df_demand['solar_gen']).clip(lower=0)
            return df_demand, existing_apps
    return None, []

df, app_list = load_merged_data()

if df is not None:
    st.title("🏡 Residential Digital Twin: Optimization Home")
    st.markdown("### **System Performance Summary (24-Hour Horizon)**")

    # ==========================================
    # 1. GLOBAL METRICS (TOP OF HOME SCREEN)
    # ==========================================
    # ToU Pricing Profile (Standard Peak/Off-Peak)
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]

    # Global Calculations for Research Metrics
    total_load_24h = df['total_demand'].sum()
    optimized_load_24h = df['net_load'].sum() # The actual load pulled from the grid
    
    baseline_cost = (df['total_demand'] * grid_prices).sum()
    optimized_cost = (df['net_load'] * grid_prices).sum()
    total_cost_saving = baseline_cost - optimized_cost

    # Layout for the Home Screen Metrics
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.metric(label="Total Load (24hr)", value=f"{total_load_24h:.2f} kWh")
        st.caption("Baseline demand without optimization")

    with m2:
        # Highlighting your specific result of 29.15 kWh
        st.metric(label="Optimized Load", value=f"{optimized_load_24h:.2f} kWh", 
                  delta=f"-{(total_load_24h - optimized_load_24h):.2f} kWh Offset")
        st.caption("Remaining grid dependency after solar use")

    with m3:
        st.metric(label="Total Cost Optimization", value=f"${total_cost_saving:.2f}", 
                  delta=f"{(total_cost_saving/baseline_cost*100):.1f}% Savings")
        st.caption("Economic benefit of PPO-driven scheduling")

    st.write("---")

    # ==========================================
    # 2. INTERACTIVE ANALYSIS (SLIDER SECTION)
    # ==========================================
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 12)
    row = df.iloc[selected_hour]

    col_viz, col_breakdown = st.columns([2, 1])

    with col_viz:
        st.subheader(f"📊 Energy State: Hour {selected_hour}:00")
        fig_bar = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                         barmode='group', labels={'value': 'kW', 'variable': 'Type'},
                         color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_breakdown:
        st.subheader("💡 Load Composition")
        pie_data = {app: row[app] for app in app_list}
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), hole=0.4)
        fig_pie.update_layout(showlegend=False, height=250, margin=dict(t=0, b=0, l=10, r=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    # ==========================================
    # 3. LONGITUDINAL TRENDS
    # ==========================================
    st.subheader("📈 24-Hour Optimization Horizon")
    fig_line = px.line(df, y=['solar_gen', 'total_demand', 'net_load'], 
                       labels={'value': 'kW', 'index': 'Hour'},
                       color_discrete_map={"solar_gen": "orange", "total_demand": "blue", "net_load": "green"})
    fig_line.add_vline(x=selected_hour, line_dash="dash", line_color="red")
    st.plotly_chart(fig_line, use_container_width=True)

else:
    st.error("🚨 Data Link Error: Please ensure 'solar_forecast.csv' and 'next_day_prediction.csv' are in the /data folder.")
