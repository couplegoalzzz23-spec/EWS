import streamlit as st
import numpy as np
import pandas as pd
import folium
import json
import streamlit.components.v1 as components
from datetime import datetime

# OPTIONAL (AMAN)
try:
    from shapely.geometry import shape, Point
    SHAPELY_AVAILABLE = True
except:
    SHAPELY_AVAILABLE = False

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("🌩️ SkyAlert – Early Warning System")

# =========================
# LOAD GEOJSON (SAFE)
# =========================
@st.cache_data
def load_geojson():
    try:
        with open("indonesia_province.geojson") as f:
            return json.load(f)
    except:
        return None

geojson_data = load_geojson()

# =========================
# GET PROVINCE (SAFE)
# =========================
@st.cache_data
def get_province(lat, lon):
    if geojson_data is None or not SHAPELY_AVAILABLE:
        return "Indonesia"

    try:
        point = Point(lon, lat)
        for feature in geojson_data["features"]:
            polygon = shape(feature["geometry"])
            if polygon.contains(point):
                return feature["properties"].get("name", "Unknown")
    except:
        return "Indonesia"

    return "Luar Indonesia"

# =========================
# DATA (SIMULASI AMAN)
# =========================
np.random.seed(42)

df = pd.DataFrame({
    "lat": np.random.uniform(-11, 6, 300),
    "lon": np.random.uniform(95, 141, 300),
    "ctt": np.random.uniform(-80, 10, 300)
})

# =========================
# PARAMETER
# =========================
df["cape"] = np.interp(df["ctt"], [-80, 20], [3000, 100])
df["rh"] = np.interp(df["ctt"], [-80, 20], [95, 40])
df["rain"] = np.interp(df["ctt"], [-80, 20], [100, 0])

def norm(x, a, b):
    return np.clip((x - a) / (b - a), 0, 1)

df["score"] = (
    0.4 * norm(df["cape"], 0, 4000) +
    0.3 * norm(abs(df["ctt"]), 0, 90) +
    0.2 * norm(df["rh"], 0, 100) +
    0.1 * norm(df["rain"], 0, 100)
)

def classify(s):
    if s < 0.3: return "🟢 Aman"
    elif s < 0.6: return "🟡 Waspada"
    elif s < 0.8: return "🟠 Siaga"
    else: return "🔴 Ekstrem"

df["status"] = df["score"].apply(classify)

# =========================
# SAMPLE + PROVINCE
# =========================
df_sample = df.sample(100).copy()
df_sample["province"] = df_sample.apply(
    lambda r: get_province(r["lat"], r["lon"]), axis=1
)

# =========================
# EXPLANATION
# =========================
def explain(r):
    alasan = []
    if r["cape"] > 2500: alasan.append("CAPE tinggi")
    if r["ctt"] < -70: alasan.append("CB kuat")
    if r["rh"] > 80: alasan.append("Lembap")
    return ", ".join(alasan)

# =========================
# WAKTU
# =========================
now = datetime.now()
time_str = now.strftime("%Y-%m-%d %H:%M:%S")

st.info(f"⏱️ {time_str} WIB")

# =========================
# LEGENDA
# =========================
st.subheader("📘 Legenda Status")

col1, col2, col3, col4 = st.columns(4)
col1.markdown("🟢 **Aman**  \nAtmosfer stabil")
col2.markdown("🟡 **Waspada**  \nAwal konveksi")
col3.markdown("🟠 **Siaga**  \nPotensi hujan lebat")
col4.markdown("🔴 **Ekstrem**  \nBadai / CB kuat")

# =========================
# MAP (STATIC - ANTI GERAK)
# =========================
st.subheader("🗺️ Peta Risiko Cuaca")

def create_map(df):
    m = folium.Map(location=[-2,118], zoom_start=5)

    color = {
        "🟢 Aman":"green",
        "🟡 Waspada":"orange",
        "🟠 Siaga":"darkorange",
        "🔴 Ekstrem":"red"
    }

    for _, r in df.iterrows():
        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=5,
            color=color[r["status"]],
            fill=True,
            fill_opacity=0.7,
            popup=f"""
            📍 {r['province']}<br>
            Lat: {r['lat']:.2f}, Lon: {r['lon']:.2f}<br>
            🚨 {r['status']}<br>
            ⏱️ {time_str}<br>
            📊 Score: {r['score']:.2f}<br>
            CAPE: {r['cape']:.0f}<br>
            CTT: {r['ctt']:.1f}°C<br>
            🧠 {explain(r)}
            """
        ).add_to(m)

    return m._repr_html_()

components.html(create_map(df_sample), height=520)

# =========================
# DATA TABLE
# =========================
st.subheader("📊 Data Detail Lokasi")

df_display = df_sample[[
    "province", "lat", "lon", "status", "score", "cape", "ctt", "rh", "rain"
]].copy()

df_display = df_display.sort_values("score", ascending=False)

st.dataframe(df_display, use_container_width=True)

# =========================
# SUMMARY
# =========================
st.subheader("📊 Ringkasan")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", len(df))
col2.metric("Ekstrem", (df["status"]=="🔴 Ekstrem").sum())
col3.metric("Siaga", (df["status"]=="🟠 Siaga").sum())
col4.metric("Aman", (df["status"]=="🟢 Aman").sum())
