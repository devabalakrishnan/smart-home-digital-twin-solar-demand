def get_xai_insight(hour, solar_val):
    if solar_val > 4.0:
        return f"Hour {hour}: Decision driven by high solar availability."
    return f"Hour {hour}: Decision driven by grid cost minimization."