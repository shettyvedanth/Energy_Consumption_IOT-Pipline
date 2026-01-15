import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

API_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="HLT200 Supervisor", layout="wide")
st.title("🏭 HLT200 Digital Supervisor")

def get_data(e):
    try:
        r = requests.get(f"{API_URL}{e}", timeout=5)
        return r.json() if r.status_code == 200 else None
    except: 
        return None

metrics = get_data("/live/analysis")
stats = get_data("/stats/accumulated")
history = get_data("/live/history")

if metrics and "machine_state" in metrics:
    st.markdown("### 📡 Live Telemetry")
    burn = metrics.get('money_burn_rate_hr', 0.0)
    
    # 🟢 FIXED: Use 3 columns instead of 4
    c1, c2, c3 = st.columns(3)
    
    c1.metric("Machine State", metrics.get('machine_state'))
    c1.metric("Power Consumption", f"{metrics.get('actual_kw', 0.0):.2f} kW")
    
    c2.metric("Discharge Pressure", f"{metrics.get('discharge_pressure_bar', 0.0):.2f} bar")
    
    c3.metric("Instant Burn Rate", f"₹ {burn:.2f} / hr", delta=f"-{burn}", delta_color="inverse")

    st.divider()
    st.subheader("💰 Financial Impact")
    loss = stats.get('total_loss_today', 0.0) if stats else 0.0
    
    f1, f2, f3 = st.columns(3)
    f1.metric("💸 Realized Loss (Today)", f"₹ {loss:.2f}")
    f2.metric("📉 Projected Daily Loss", f"₹ {loss + (burn * 7):.2f}")
    f3.metric("🏚️ Total Accumulated Loss", f"₹ {loss:.2f}")

    # 🟢 Display Active Alerts
    alerts = metrics.get('active_alerts', [])
    if alerts:
        st.divider()
        st.subheader("🚨 Active Alerts")
        for alert in alerts:
            with st.expander(f"🔴 {alert['title']} — ₹{alert['cost_impact']:.2f}/hr"):
                st.write(f"**Reason:** {alert['reason']}")
                st.write(f"**Action:** {alert['action']}")

    # 🟢 30-Minute Historical Trends
    if history:
        df = pd.DataFrame(history)
        st.divider()
        st.subheader("📉 30-Minute Trends")
        g1, g2 = st.columns(2)
        
        g1.plotly_chart(
            px.line(df, x="_time", y="actual_kw", title="Power Consumption (kW)"),
            use_container_width=True
        )
        g2.plotly_chart(
            px.line(df, x="_time", y="discharge_pressure_bar", title="Discharge Pressure (Bar)"),
            use_container_width=True
        )
    
    if st.button("🔄 Refresh"): 
        st.rerun()
else: 
    st.warning("⏳ Waiting for API...")