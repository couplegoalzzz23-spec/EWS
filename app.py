import streamlit as st
import numpy as np
import pandas as pd
import folium
import xarray as xr
import streamlit.components.v1 as components
from datetime import datetime
from geopy.geocoders import Nominatim
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("🌩️ SkyAlert – Ultra EWS")

# =========================
# LOAD DATA
# =========================
uploaded_file = st.file_uploader("Upload NetCDF (.nc)", type=["nc"])

def load_nc(file):
    ds = xr.open_dataset(file)
    var = list(ds.data_vars)[0]
    data = ds[var]

    if "time" in data.dims:
        data = data.isel(time=0)

    lat = ds[[c for c in ds.coords if "lat" in c.lower()][0]].values
    lon = ds[[c for c in ds.coords if "lon" in c.lower()][0]].values

    tbb = data.values
    if np.nanmean(tbb) > 200:
        tbb = tbb - 273.15

    lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')

    return pd.DataFrame({
        "lat": lat_grid.flatten(),
        "lon": lon_grid.flatten(),
        "ctt": tbb.flatten()
    }).dropna()

if uploaded_file:
    df = load_nc(uploaded_file)
else:
    df = pd.DataFrame({
        "lat": np.random.uniform(-11, 6, 200),
        "lon": np.random.uniform(95, 141, 200),
        "ctt": np.random.uniform(-80, 10, 200)
    })

# =========================
# PARAMETER
# =========================
df["cape"] = np.interp(df["ctt"], [-80, 20], [3000, 100])
df["rh"] = np.interp(df["ctt"], [-80, 20], [95, 40])
df["rain"] = np.interp(df["ctt"], [-80, 20], [100, 0])

def norm(x,a,b): return np.clip((x-a)/(b-a),0,1)

df["score"] = (
    0.4*norm(df["cape"],0,4000)+
    0.3*norm(abs(df["ctt"]),0,90)+
    0.2*norm(df["rh"],0,100)+
    0.1*norm(df["rain"],0,100)
)

def classify(s):
    if s < 0.3: return "🟢 Aman"
    elif s < 0.6: return "🟡 Waspada"
    elif s < 0.8: return "🟠 Siaga"
    else: return "🔴 Ekstrem"

df["status"] = df["score"].apply(classify)

# =========================
# GEOLOCATION (KOTA)
# =========================
geolocator = Nominatim(user_agent="skyalert")

@st.cache_data
def get_city(lat, lon):
    try:
        loc = geolocator.reverse(f"{lat},{lon}", language="id", timeout=10)
        return loc.raw["address"].get("city", 
               loc.raw["address"].get("town","Unknown"))
    except:
        return "Unknown"

df_sample = df.sample(min(len(df), 50))
df_sample["city"] = df_sample.apply(lambda r: get_city(r["lat"], r["lon"]), axis=1)

# =========================
# EXPLANATION
# =========================
def explain(r):
    alasan = []
    if r["cape"] > 2500: alasan.append("CAPE sangat tinggi")
    if r["ctt"] < -70: alasan.append("Awan CB kuat")
    if r["rh"] > 80: alasan.append("Kelembapan tinggi")
    return ", ".join(alasan)

# =========================
# WAKTU
# =========================
now = datetime.now()
time_str = now.strftime("%Y-%m-%d %H:%M:%S")

st.info(f"⏱️ {time_str} WIB")

# =========================
# MAP (STATIC)
# =========================
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
            popup=f"""
            📍 {r['city']}<br>
            Lat: {r['lat']:.2f}, Lon: {r['lon']:.2f}<br>
            🚨 {r['status']}<br>
            ⏱️ {time_str}<br>
            🧠 {explain(r)}
            """
        ).add_to(m)

    return m._repr_html_()

components.html(create_map(df_sample), height=500)

# =========================
# PDF REPORT
# =========================
def generate_pdf(df):
    doc = SimpleDocTemplate("ews_report.pdf")
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph("Laporan Early Warning System", styles["Title"]))
    content.append(Spacer(1,10))

    for _, r in df.iterrows():
        text = f"""
        Lokasi: {r['city']} ({r['lat']:.2f},{r['lon']:.2f})<br/>
        Status: {r['status']}<br/>
        Waktu: {time_str}<br/>
        Alasan: {explain(r)}<br/><br/>
        """
        content.append(Paragraph(text, styles["Normal"]))

    doc.build(content)

generate_pdf(df_sample)

with open("ews_report.pdf", "rb") as f:
    st.download_button("📄 Download Laporan PDF", f, "EWS_Report.pdf")
