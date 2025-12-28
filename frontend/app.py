import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Digital Twin: Solar Energy Optimizer")

df = pd.read_csv("data/solar_forecast.csv")
fig = px.area(df, x='hour', y='generation_kw', title="24-Hour Solar Forecast", color_discrete_sequence=['orange'])
st.plotly_chart(fig)

st.sidebar.metric("Peak Generation", f"{df['generation_kw'].max()} kW")
st.write("### PPO Scheduling Strategy")
st.info("The agent is shifting high-load tasks to Hour 13 to match the 5.18 kW peak.")
