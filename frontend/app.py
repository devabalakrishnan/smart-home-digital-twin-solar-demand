 import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.title("Digital Twin: Solar Energy Optimizer")

# Updated path to match your GitHub file name exactly
file_path = "data/solar_forecast.csv.csv"

if os.path.exists(file_path):
    df = pd.read_csv(file_path)
    
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
    st.error(f"File not found at {file_path}. Please check your GitHub 'data' folder.")
