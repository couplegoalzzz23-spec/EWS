import streamlit as st
import numpy as np
import pandas as pd
import folium
import xarray as xr
from streamlit_folium import st_folium
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("🌩️ SkyAlert – Early Warning System")

# =========================
# UPLOAD NETCDF
# =========================
uploaded_file = st.file_uploader("📦 Upload Data NetCDF (.nc)", type=["nc"])

def load_nc(file):
    try:
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

        df = pd.DataFrame({
            "lat": lat_grid.flatten(),
            "lon": lon_grid.flatten(),
            "ctt": tbb.flatten()
        }).dropna()

        return df

    except:
        return None

# =========================
# DATA
# =========================
if uploaded_file:
    df = load_nc(uploaded_file)
else:
    st.info("Menggunakan data simulasi")
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
    return np.clip((x - a)/(b-a), 0, 1)

df["score"] = (
    0.4*norm(df["cape"],0,4000) +
    0.3*norm(abs(df["ctt"]),0,90) +
    0.2*norm(df["rh"],0,100) +
    0.1*norm(df["rain"],0,100)
)

def classify(s):
    if s < 0.30: return "🟢 Aman"
    elif s < 0.60: return "🟡 Waspada"
    elif s < 0.80: return "🟠 Siaga"
    else: return "🔴 Ekstrem"

df["status"] = df["score"].apply(classify)

# =========================
# ⏱️ WAKTU
# =========================
now = datetime.now()
time_str = now.strftime("%Y-%m-%d %H:%M:%S")

st.subheader("⏱️ Waktu Observasi")
st.info(time_str + " WIB")

# =========================
# STATUS DOMINAN
# =========================
dominant = df["status"].value_counts().idxmax()

st.subheader("🚨 Status Saat Ini")
st.success(f"{dominant} (pukul {now.strftime('%H:%M WIB')})")

# =========================
# MAP (STABLE)
# =========================
st.subheader("🗺️ Peta Risiko Cuaca")

@st.cache_resource
def create_map(df, time_str):

    m = folium.Map(location=[-2,118], zoom_start=5)

    color = {
        "🟢 Aman":"green",
        "🟡 Waspada":"orange",
        "🟠 Siaga":"darkorange",
        "🔴 Ekstrem":"red"
    }

    # kurangi titik biar mudah diklik
    df_sample = df.sample(min(len(df), 300))

    for _, r in df_sample.iterrows():
        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=5,
            color=color[r["status"]],
            fill=True,
            fill_opacity=0.7,
            popup=f"""
            <b>Status:</b> {r['status']}<br>
            <b>Waktu:</b> {time_str}<br>
            <b>Score:</b> {r['score']:.2f}
            """
        ).add_to(m)

    return m

map_object = create_map(df, time_str)
st_folium(map_object, width=1100, height=500)

# =========================
# DATA RINGKAS
# =========================
st.subheader("📊 Ringkasan Data")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Data", len(df))
col2.metric("Ekstrem", (df["status"]=="🔴 Ekstrem").sum())
col3.metric("Siaga", (df["status"]=="🟠 Siaga").sum())
col4.metric("Aman", (df["status"]=="🟢 Aman").sum())

# =========================
# TABLE (OPSIONAL)
# =========================
with st.expander("📋 Lihat Data Detail"):
    st.dataframe(df.head(100))
