import streamlit as st
import numpy as np
import pandas as pd
import folium
import xarray as xr
from streamlit_folium import st_folium
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

st.title("🌩️ SkyAlert – Early Warning System")

# =========================
# UPLOAD DATA
# =========================
uploaded_file = st.file_uploader("Upload NetCDF (.nc)", type=["nc"])

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

if uploaded_file:
    df = load_nc(uploaded_file)
else:
    st.warning("Menggunakan data simulasi")
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

st.subheader("⏱️ Informasi Waktu")
st.info(f"Update: {now.strftime('%Y-%m-%d %H:%M:%S')} WIB")

# =========================
# STATUS DOMINAN + WAKTU
# =========================
dominant = df["status"].value_counts().idxmax()

st.subheader("🚨 Status Saat Ini")
st.success(f"{dominant} terjadi pada {now.strftime('%H:%M WIB')}")

# =========================
# RIWAYAT WAKTU STATUS
# =========================
st.subheader("📈 Waktu Perubahan Status")

history = []
for i in range(4):
    waktu = now - timedelta(minutes=(3-i)*10)
    history.append({
        "Waktu": waktu.strftime("%H:%M"),
        "Status": dominant
    })

hist_df = pd.DataFrame(history)
st.table(hist_df)

# =========================
# MAP (STABIL)
# =========================
st.subheader("🗺️ Peta Risiko")

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
        Status: {r['status']}<br>
        Waktu: {now.strftime('%H:%M')}<br>
        Score: {r['score']:.2f}
        """
    ).add_to(m)

st_folium(m, width=1100, height=500)

# =========================
# DATA
# =========================
st.subheader("📊 Data")
st.dataframe(df.head(100))
