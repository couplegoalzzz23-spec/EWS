import streamlit as st
import numpy as np
import pandas as pd
import folium
import json
import streamlit.components.v1 as components
from datetime import datetime

try:
    from shapely.geometry import shape, Point
    SHAPELY_AVAILABLE = True
except:
    SHAPELY_AVAILABLE = False


# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("SkyAlert – Early Warning System")

# =========================
# LOAD GEOJSON
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
# GET PROVINCE
# =========================
@st.cache_data
def get_province(lat, lon):
    if geojson_data is None or not SHAPELY_AVAILABLE:
        return "Indonesia - Region Unknown"

    try:
        point = Point(lon, lat)
        for feature in geojson_data["features"]:
            polygon = shape(feature["geometry"])
            if polygon.contains(point):
                return feature["properties"].get("name", "Unknown Province")
    except:
        return "Indonesia - Region Unknown"

    return "Indonesia - Outer Area"


# =========================
# DATA
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

# =========================
# CLASSIFICATION (ILMIAH)
# =========================
def classify(s):
    if s < 0.30:
        return "Aman"
    elif s < 0.60:
        return "Waspada"
    elif s < 0.80:
        return "Siaga"
    else:
        return "Ekstrem"

df["status"] = df["score"].apply(classify)

# =========================
# SAMPLE + PROVINCE
# =========================
df_sample = df.sample(100).copy()
df_sample["province"] = df_sample.apply(
    lambda r: get_province(r["lat"], r["lon"]), axis=1
)

# =========================
# EXPLANATION (ILMIAH FIX)
# =========================
def explain(r):
    if r["status"] == "Ekstrem":
        return "CAPE > 2500 J/kg dan CTT < -70°C → atmosfer sangat labil, Cumulonimbus aktif"
    elif r["status"] == "Siaga":
        return "CAPE 1500–2500 J/kg → konveksi kuat, potensi hujan lebat"
    elif r["status"] == "Waspada":
        return "CAPE 500–1500 J/kg → awal pembentukan awan konvektif"
    else:
        return "Atmosfer stabil, konveksi lemah"

# =========================
# WAKTU
# =========================
now = datetime.now()
time_str = now.strftime("%Y-%m-%d %H:%M:%S")

st.info(f"Waktu Observasi: {time_str} WIB")

# =========================
# LEGENDA
# =========================
st.subheader("Legenda Status")

col1, col2, col3, col4 = st.columns(4)
col1.markdown("Aman – atmosfer stabil")
col2.markdown("Waspada – awal konveksi")
col3.markdown("Siaga – hujan lebat berpotensi")
col4.markdown("Ekstrem – badai Cumulonimbus aktif")

# =========================
# MAP (STATIC)
# =========================
st.subheader("Peta Risiko Cuaca")

def create_map(df):
    m = folium.Map(location=[-2,118], zoom_start=5)

    color = {
        "Aman":"green",
        "Waspada":"orange",
        "Siaga":"darkorange",
        "Ekstrem":"red"
    }

    for _, r in df.iterrows():
        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=5,
            color=color[r["status"]],
            fill=True,
            fill_opacity=0.7,
            popup=f"""
            Provinsi: {r['province']}<br>
            Koordinat: {r['lat']:.3f}, {r['lon']:.3f}<br>
            Status: {r['status']}<br>
            Score: {r['score']:.2f}<br>
            CAPE: {r['cape']:.0f} J/kg<br>
            CTT: {r['ctt']:.1f} °C<br><br>
            Alasan:<br>
            {explain(r)}
            """
        ).add_to(m)

    return m._repr_html_()

components.html(create_map(df_sample), height=520)

# =========================
# DATA TABLE
# =========================
st.subheader("Data Detail Lokasi")

df_display = df_sample[[
    "province", "lat", "lon", "status", "score", "cape", "ctt", "rh", "rain"
]].sort_values("score", ascending=False)

st.dataframe(df_display, use_container_width=True)

# =========================
# SUMMARY
# =========================
st.subheader("Ringkasan")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", len(df))
col2.metric("Ekstrem", (df["status"]=="Ekstrem").sum())
col3.metric("Siaga", (df["status"]=="Siaga").sum())
col4.metric("Aman", (df["status"]=="Aman").sum())
