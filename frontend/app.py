import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# ... (Keep your existing MQTT and Data Loading functions) ...

if df is not None:
    # --- GLOBAL METRICS (Static) ---
    st.title("🏡 Residential Digital Twin: Global Optimization Dashboard")
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Load (24hr)", "32.80 kWh") [cite: 10]
    g2.metric("Optimized Load", "12.93 kWh") [cite: 11]
    g3.metric("Total Cost Optimization", "$5.51", "54.5% Savings") [cite: 13, 14]

    # --- SIDEBAR (Input) ---
    st.sidebar.header("🕹️ Digital Twin Controls")
    selected_hour = st.sidebar.slider("Synchronize Hour", 0, 23, 2) [cite: 2, 3]

    # --- DYNAMIC DATA FETCHING (Crucial Step) ---
    # This line ensures the 'row' updates every time you move the slider
    row = df.iloc[selected_hour].copy()

    st.subheader(f"⏱️ System Status at Hour {selected_hour}:00")
    col1, col2 = st.columns(2)

    with col1:
        # Metrics update based on 'row'
        st.metric("Current Demand", f"{row['total_demand']:.2f} kW")
        st.metric("Current Solar", f"{row['solar_gen']:.2f} kW")
        st.metric("Net Load", f"{row['net_load']:.2f} kW") [cite: 16]

    with col2:
        # APPLIANCE BREAKDOWN (Dynamic Pie Chart)
        df_pie = pd.DataFrame(list(row[app_list].to_dict().items()), columns=['Appliance', 'Usage'])
        fig_pie = px.pie(df_pie, values='Usage', names='Appliance', title="Usage Breakdown")
        st.plotly_chart(fig_pie)

    # --- DYNAMIC XAI WEIGHTS ---
    st.divider()
    st.subheader("🔍 XAI: PPO Decision Factors")
    
    # Logic to shift weights based on time
    solar_weight = 1.8 if (10 <= selected_hour <= 16) else 0.2 [cite: 18]
    price_weight = 1.9 if (row['net_load'] > 1.0) else 0.5 [cite: 21]

    xai_df = pd.DataFrame({
        'Factor': ['Electricity Price', 'Total Demand', 'Occupancy', 'Solar Forecast'],
        'Weight': [price_weight, 0.4, 0.6, solar_weight]
    })
    fig_xai = px.bar(xai_df, x='Weight', y='Factor', orientation='h') [cite: 1]
    st.plotly_chart(fig_xai)

    # --- CUMULATIVE SAVINGS CHART ---
    st.subheader("📈 Cumulative Cost Savings Progress")
    # Only show data up to the selected hour
    fig_savings = px.line(df.iloc[:selected_hour+1], y='cumulative_savings', title="Accumulated Savings")
    st.plotly_chart(fig_savings)
