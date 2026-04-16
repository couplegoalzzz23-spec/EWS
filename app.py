import streamlit as st
import numpy as np
import pandas as pd
import folium
import xarray as xr
from streamlit_folium import st_folium

# OPTIONAL IMPORT (ANTI ERROR)
try:
    import requests
    from PIL import Image
    from io import BytesIO
    IMG_OK = True
except:
    IMG_OK = False

# =========================
# ⚙️ CONFIG
# =========================
st.set_page_config(page_title="SkyAlert - EWS", layout="wide")

st.title("🌩️ SkyAlert – Early Warning System")
st.caption("Explainable Satellite-Based Meteorological EWS | Resti Maulina C.C")

# =========================
# 📘 SIDEBAR LEGEND
# =========================
st.sidebar.header("📘 Legenda")

st.sidebar.markdown("""
🟢 Aman → atmosfer stabil  
🟡 Waspada → awal konveksi  
🟠 Siaga → hujan lebat  
🔴 Ekstrem → badai kuat  

---

🌡️ CTT < -70°C → awan CB kuat  
⚡ CAPE > 2500 → sangat labil  
💧 RH > 80% → lembap  
🌧️ Rain > 50 mm/h → ekstrem  
""")

# =========================
# 🌐 SATELIT BMKG
# =========================
st.subheader("🌐 Citra Satelit BMKG (Real-Time)")

if IMG_OK:
    try:
        url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
        res = requests.get(url, timeout=10)
        img = Image.open(BytesIO(res.content))
        st.image(img, use_container_width=True)
    except:
        st.warning("⚠️ Gagal load citra BMKG")
else:
    st.info("ℹ️ Library gambar tidak tersedia")

# =========================
# 📦 LOAD NETCDF
# =========================
@st.cache_data(ttl=600)
def load_nc():
    try:
        ds = xr.open_dataset("H09_B07_Indonesia_202604140020.nc")

        var_name = list(ds.data_vars)[0]
        data = ds[var_name]

        if "time" in data.dims:
            data = data.isel(time=0)

        lat_name = [c for c in ds.coords if "lat" in c.lower()][0]
        lon_name = [c for c in ds.coords if "lon" in c.lower()][0]

        lat = ds[lat_name].values
        lon = ds[lon_name].values

        tbb = data.values

        if np.nanmean(tbb) > 200:
            tbb = tbb - 273.15

        lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')

        df = pd.DataFrame({
            "lat": lat_grid.flatten(),
            "lon": lon_grid.flatten(),
            "cloud_top_temp": tbb.flatten()
        }).dropna()

        # parameter turunan
        df["cape"] = np.interp(df["cloud_top_temp"], [-80, 20], [3000, 100])
        df["humidity"] = np.interp(df["cloud_top_temp"], [-80, 20], [95, 40])
        df["rain_rate"] = np.interp(df["cloud_top_temp"], [-80, 20], [100, 0])

        if len(df) > 2500:
            df = df.sample(2500, random_state=42)

        return df

    except Exception as e:
        st.error(f"❌ NetCDF error: {e}")
        return None

df = load_nc()
if df is None:
    st.stop()

# =========================
# 🎈 RASON AUTO (SAFE)
# =========================
st.subheader("🎈 Radiosonde (Estimasi Operasional)")

def get_rason():
    try:
        cape = float(np.mean(df["cape"]))
        li = - (cape / 1000)
        return cape, li
    except:
        return 1000, -2

cape_real, li_real = get_rason()

c1, c2 = st.columns(2)
c1.metric("CAPE (J/kg)", f"{cape_real:.0f}")
c2.metric("Lifted Index", f"{li_real:.1f}")

# =========================
# 🧮 NORMALISASI
# =========================
def norm(x, a, b):
    return np.clip((x - a) / (b - a), 0, 1)

# =========================
# ⚡ SCORING
# =========================
df["score"] = (
    0.4 * norm(df["cape"], 0, 4000) +
    0.3 * norm(abs(df["cloud_top_temp"]), 0, 90) +
    0.2 * norm(df["humidity"], 0, 100) +
    0.1 * norm(df["rain_rate"], 0, 100)
)

# =========================
# 🚨 STATUS
# =========================
def classify(s):
    if s < 0.30:
        return "🟢 Aman"
    elif s < 0.60:
        return "🟡 Waspada"
    elif s < 0.80:
        return "🟠 Siaga"
    else:
        return "🔴 Ekstrem"

df["status"] = df["score"].apply(classify)

# =========================
# 🧠 EXPLAIN
# =========================
def explain(r):
    alasan = []

    if r["cape"] > 2500:
        alasan.append("Atmosfer sangat labil")
    if r["cloud_top_temp"] < -70:
        alasan.append("Awan Cumulonimbus kuat")
    if r["humidity"] > 80:
        alasan.append("Udara sangat lembap")
    if r["rain_rate"] > 50:
        alasan.append("Hujan sangat lebat")

    return alasan

# =========================
# 📊 METRICS
# =========================
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total", len(df))
col2.metric("Ekstrem", (df["status"]=="🔴 Ekstrem").sum())
col3.metric("Siaga", (df["status"]=="🟠 Siaga").sum())
col4.metric("Aman", (df["status"]=="🟢 Aman").sum())

# =========================
# 🗺️ MAP
# =========================
st.subheader("🗺️ Peta Risiko")

m = folium.Map(location=[-2,118], zoom_start=5)

color_map = {
    "🟢 Aman":"green",
    "🟡 Waspada":"orange",
    "🟠 Siaga":"darkorange",
    "🔴 Ekstrem":"red"
}

for _, r in df.iterrows():
    folium.CircleMarker(
        [r["lat"], r["lon"]],
        radius=4,
        color=color_map[r["status"]],
        fill=True,
        fill_opacity=0.7,
        popup=f"""
        Status: {r['status']}<br>
        Score: {r['score']:.2f}<br>
        CAPE: {r['cape']:.0f}<br>
        CTT: {r['cloud_top_temp']:.1f}°C<br>
        RH: {r['humidity']:.0f}%<br>
        Rain: {r['rain_rate']:.1f}<br>
        """
    ).add_to(m)

st_folium(m, width=1200, height=520)

# =========================
# ⏱️ TEMPORAL TRACK
# =========================
st.subheader("⏱️ Tren Awan")

trend = df["cloud_top_temp"].rolling(50).mean()
st.line_chart(trend)

# =========================
# 📊 TABLE
# =========================
st.subheader("📊 Data Detail")

df["explanation"] = df.apply(explain, axis=1)
st.dataframe(df.sort_values("score", ascending=False), use_container_width=True)

# =========================
# AUTO REFRESH
# =========================
st.markdown("<meta http-equiv='refresh' content='600'>", unsafe_allow_html=True)
