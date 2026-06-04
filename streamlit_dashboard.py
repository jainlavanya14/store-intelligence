import requests
import streamlit as st
import pandas as pd

DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_STORE_ID = "store_1076"

st.set_page_config(
    page_title="Store Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Store Intelligence Dashboard")
st.write("A browser-based view of store metrics, funnel, heatmap, anomalies, and service health.")

api_base = st.sidebar.text_input("API Base URL", DEFAULT_API_BASE)
refresh_seconds = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)

@st.cache_data(show_spinner=False)
def fetch_json(endpoint: str):
    try:
        response = requests.get(f"{api_base}{endpoint}", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}

health = fetch_json("/health")

store_options = []
if isinstance(health, dict) and "stores" in health:
    store_options = sorted(health.get("stores", {}).keys())

selected_store = st.sidebar.selectbox(
    "Store ID",
    options=store_options or [DEFAULT_STORE_ID],
    index=store_options.index(DEFAULT_STORE_ID) if DEFAULT_STORE_ID in store_options else 0,
)

st.sidebar.markdown("---")
if st.sidebar.button("Refresh now"):
    st.experimental_rerun()

if "error" in health:
    st.sidebar.error(f"Health load failed: {health['error']}")
else:
    st.sidebar.success(f"Service status: {health.get('status', 'unknown').upper()}")

col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

metrics = fetch_json(f"/stores/{selected_store}/metrics")
funnel = fetch_json(f"/stores/{selected_store}/funnel")
heatmap = fetch_json(f"/stores/{selected_store}/heatmap")
anomalies = fetch_json(f"/stores/{selected_store}/anomalies")

with col1:
    st.metric("Unique Visitors", metrics.get("unique_visitors", 0))
    st.metric("Conversion Rate", f"{metrics.get('conversion_rate', 0) * 100:.1f}%")

with col2:
    st.metric("Queue Depth", metrics.get("queue_depth", 0))
    st.metric("Avg Wait (s)", metrics.get("avg_wait_seconds", 0))

with col3:
    st.metric("Abandonment Rate", f"{metrics.get('abandonment_rate', 0) * 100:.1f}%")
    st.metric("Store ID", selected_store)

with col4:
    stale_feed = False
    if selected_store in health.get("stores", {}):
        stale_feed = health["stores"][selected_store].get("stale_feed", False)
    st.metric("Stale Feed", "Yes" if stale_feed else "No")
    st.metric("Last Event", health.get("stores", {}).get(selected_store, {}).get("last_event_timestamp", "-"))

st.markdown("---")

col5, col6 = st.columns([2, 1])

with col5:
    st.subheader("Funnel")
    if funnel.get("funnel"):
        funnel_df = pd.DataFrame(funnel["funnel"])
        st.table(funnel_df.rename(columns={"stage": "Stage", "visitors": "Visitors", "drop_off_pct": "Drop %"}))
    else:
        st.info("No funnel data available.")

with col6:
    st.subheader("Zone Heatmap")
    if heatmap.get("zones"):
        zone_df = pd.DataFrame(heatmap["zones"])
        zone_df = zone_df.sort_values(by="visits", ascending=False)
        st.bar_chart(zone_df.set_index("zone_name")["visits"])
        st.dataframe(zone_df[ ["zone_name", "visits", "normalised"] ].rename(
            columns={"zone_name": "Zone", "visits": "Visits", "normalised": "Normalized"}
        ))
    else:
        st.info("No heatmap data available.")

st.markdown("---")

st.subheader("Anomalies")
if anomalies.get("anomalies"):
    anomaly_df = pd.DataFrame(anomalies["anomalies"])
    anomaly_df = anomaly_df.rename(columns={
        "type": "Type",
        "severity": "Severity",
        "suggested_action": "Suggested Action"
    })
    st.dataframe(anomaly_df[["Type", "Severity", "Suggested Action"]])
else:
    st.success("No active anomalies.")

st.markdown("---")

st.subheader("Service Health")
if "stores" in health:
    store_health = [
        {
            "Store ID": sid,
            "Last Event": info.get("last_event_timestamp", "-"),
            "Stale Feed": "Yes" if info.get("stale_feed") else "No",
        }
        for sid, info in sorted(health["stores"].items())
    ]
    st.dataframe(pd.DataFrame(store_health))
else:
    st.warning("Health endpoint did not return store data.")

st.sidebar.markdown(f"Built for Store Intelligence API at `{api_base}`.")

if hasattr(st, "experimental_set_query_params"):
    st.experimental_set_query_params(store=selected_store, api=api_base)
