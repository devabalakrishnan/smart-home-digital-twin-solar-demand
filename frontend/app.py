import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="Residential Digital Twin | Time Portal", layout="wide")

# --- DATA LOADING & MERGING ---
def load_merged_data():
    demand_path = "data/next_day_prediction.csv"
    solar_path = "data/solar_forecast.csv"
    
    if os.path.exists(demand_path) and os.path.exists(solar_path):
        df_demand = pd.read_csv(demand_path)
        df_solar = pd.read_csv(solar_path)
        
        # Standardize solar headers
        df_solar.columns = df_solar.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        df_demand.columns = df_demand.columns.str.strip()
        
        # Merge
        df_demand['solar_gen'] = df_solar['generation_kw']
        
        # Appliance column check to prevent KeyError
        app_cols = ['Fridge', 'Heater', 'Fans', 'Lights', 'TV', 'Microwave', 'Washing_Machine']
        existing_apps = [col for col in app_cols if col in df_demand.columns]
        
        if existing_apps:
            df_demand['total_demand'] = df_demand[existing_apps].sum(axis=1)
            df_demand['net_load'] = df_demand['total_demand'] - df_demand['solar_gen']
            return df_demand, existing_apps
    return None, []

df, app_list = load_merged_data()

if df is not None:
    st.title("🌐 Digital Twin: 24-Hour Time-Sync Portal")
    
    # ==========================================
    # HOUR CHANGER SLIDER
    # ==========================================
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Select Forecast Hour", 0, 23, 12) # Default to Noon
    
    # Get data for the specific hour selected
    row = df.iloc[selected_hour]
    
    # Metrics for the selected hour
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Demand", f"{row['total_demand']:.2f} kW")
    m2.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
    m3.metric("Net Load", f"{row['net_load']:.2f} kW")

    # Layout for Charts
    col_chart, col_breakdown = st.columns([2, 1])

    with col_chart:
        st.subheader(f"📊 Energy Balance at Hour {selected_hour}:00")
        fig = px.bar(df.iloc[[selected_hour]], y=['solar_gen', 'total_demand'], 
                     barmode='group', color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
        st.plotly_chart(fig, use_container_width=True)

    with col_breakdown:
        st.subheader("💡 Appliance Breakdown")
        pie_data = {app: row[app] for app in app_list}
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Visualization of the full 24h trend with a vertical line for the selected hour
    st.subheader("📈 24-Hour Operational Horizon")
    fig_line = px.line(df, y=['solar_gen', 'total_demand'], 
                       color_discrete_map={"solar_gen": "orange", "total_demand": "blue"})
    # Add a vertical indicator for the slider position
    fig_line.add_vline(x=selected_hour, line_dash="dash", line_color="red", annotation_text="Selected Hour")
    st.plotly_chart(fig_line, use_container_width=True)

else:
    st.error("🚨 Data files missing or corrupted. Please check your /data folder.")
