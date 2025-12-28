import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.title("Digital Twin: Solar Energy Optimizer")

# The path to your data file
file_path = "data/solar_forecast.csv"

if os.path.exists(file_path):
    df = pd.read_csv(file_path)
    
    # --- CRITICAL FIX: Standardize Column Names ---
    # This converts "Generation (kW)" or "Hour" to "generation_kw" and "hour"
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
    
    # Check if the required columns exist after cleaning
    if 'hour' in df.columns and 'generation_kw' in df.columns:
        # Visualization
        fig = px.area(df, x='hour', y='generation_kw', 
                      title="24-Hour Solar Forecast", 
                      color_discrete_sequence=['orange'])
        st.plotly_chart(fig)

        # Metrics
        peak_val = df['generation_kw'].max()
        st.sidebar.metric("Peak Generation", f"{peak_val} kW")
        
        st.write("### PPO Scheduling Strategy")
        st.info(f"The agent is shifting high-load tasks to Hour 13 to match the {peak_val} kW peak.")
    else:
        st.error(f"Column mismatch! Found: {list(df.columns)}. Expected: 'hour' and 'generation_kw'")
else:
    st.error(f"File not found at {file_path}. Please check your GitHub folder structure.")
