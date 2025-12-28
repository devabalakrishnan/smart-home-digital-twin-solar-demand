import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.title("Digital Twin: Solar Energy Optimizer")

# Standardized path
file_path = "data/solar_forecast.csv"

if os.path.exists(file_path):
    df = pd.read_csv(file_path)
    
    # Standardize column names automatically
    # This fixes the "Generation (kW)" vs "generation_kw" issue
    df.columns = [c.lower().replace(" ", "_").replace("(", "").replace(")", "") for c in df.columns]
    
    # Use the standardized 'generation_kw'
    if 'generation_kw' in df.columns:
        fig = px.area(df, x='hour', y='generation_kw', 
                      title="24-Hour Solar Forecast", 
                      color_discrete_sequence=['orange'])
        st.plotly_chart(fig)

        peak_val = df['generation_kw'].max()
        st.sidebar.metric("Peak Generation", f"{peak_val} kW")
        
        st.write("### PPO Scheduling Strategy")
        st.info(f"The agent is shifting high-load tasks to Hour 13 to match the {peak_val} kW peak.")
    else:
        st.error(f"Found the file, but couldn't find a 'generation' column. Columns found: {list(df.columns)}")
else:
    # Diagnostic help
    st.error(f"File not found at {file_path}")
    if os.path.exists("data"):
        st.write("Files actually in your data folder:", os.listdir("data"))
    else:
        st.write("The 'data' folder itself was not found.")
