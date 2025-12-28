import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Set page configuration for a wide dashboard layout
st.set_page_config(page_title="Residential Digital Twin | Home", layout="wide")

# --- DATA LOADING & SYNCHRONIZATION ---
def load_merged_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv" #
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize solar headers for consistency
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge solar generation into the demand dataset
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # List of appliance columns for demand calculation
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            # Calculate Total Demand and Net Load
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            df_demand['net_load'] = df_demand['total_demand'] - df_demand['solar_gen']
            return df_demand, existing_apps
    return None, []

df, app_list = load_merged_data()

if df is not None:
    st.title("🌐 Residential Digital Twin & XAI Portal")
    st.write("---")

    # ==========================================
    # 1. GLOBAL SUMMARY METRICS (HOME SCREEN)
    # ==========================================
    # Mock Time-of-Use Grid Pricing Profile
    grid_prices = [0.15, 0.15, 0.15, 0.15, 0.15, 0.25, 0.35, 0.45, 0.30, 0.25, 
                   0.20, 0.20, 0.20, 0.20, 0.25, 0.30, 0.40, 0.50, 0.55, 0.50, 
                   0.40, 0.30, 0.20, 0.15]

    # Global Calculations
    total_load_24h = df['total_demand'].sum()
    df['grid_pull'] = df['net_load'].clip(lower=0)
    optimized_load_24h = df['grid_pull'].sum()
    
    baseline_cost = (df['total_demand'] * grid_prices).sum()
    optimized_cost = (df['grid_pull'] * grid_prices).sum()
    total_cost_optimization = baseline_cost - optimized_cost

    # Display the three requested home screen metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Load (24hr)", f"{total_load_24h:.2f} kWh", help="Baseline energy demand without solar optimization.")
    m2.metric("Optimized Load", f"{optimized_load_24h:.2f} kWh", f"-{(total_load_24h - optimized_load_24h):.2f} kWh (Solar Offset)")
    m3.metric("Total Cost Optimization", f"${total_cost_optimization:.2f}", f"{(total_cost_optimization/baseline_cost*100):.1f}% Savings", delta_color="normal")

    st.write("---")

    # ==========================================
    # 2. INTERACTIVE CONTROLS & XAI
    # ==========================================
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Select Forecast Hour", 0, 23, 12)
    row = df.iloc[selected_hour]

    col_viz, col_xai = st.columns([2, 1])

    with col_viz:
        st.subheader(f"📊 Hourly Energy Balance (Hour {selected_hour}:00)")
        fig_bar = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                         barmode='group', color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_xai:
        st.subheader("🔍 XAI Insight")
        # Logic derived from explainer service
        if row['solar_gen'] > 4.0:
            insight = f"Decision for Hour {selected_hour} is driven by high solar availability ({row['solar_gen']:.2f} kW)."
        else:
            insight = f"Decision for Hour {selected_hour} is driven by grid cost minimization (${grid_prices[selected_hour]:.2f}/kWh)."
        st.info(insight)
        
        # Appliance breakdown for the selected hour
        st.write("**Appliance Contribution:**")
        pie_data = {app: row[app] for app in app_list}
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), hole=0.4)
        fig_pie.update_layout(showlegend=False, height=250, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 24-HOUR TREND SECTION ---
    st.subheader("📈 24-Hour Operational Horizon")
    fig_line = px.line(df, y=['solar_gen', 'total_demand'], 
                       color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
    fig_line.add_vline(x=selected_hour, line_dash="dash", line_color="red")
    st.plotly_chart(fig_line, use_container_width=True)

else:
    st.error("🚨 Configuration Error: Data files not found in the 'data/' folder.")
