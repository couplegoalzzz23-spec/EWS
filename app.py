import streamlit as st
import numpy as np
import pandas as pd
import folium
import xarray as xr
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# optional image
try:
    import requests
    from PIL import Image
    from io import BytesIO
    IMG_OK = True
except:
    IMG_OK = False

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="SkyAlert - EWS", layout="wide")

st.title("🌩️ SkyAlert – Early Warning System")
st.caption("Explainable Spatio-Temporal Meteorological EWS | Resti Maulina C.C")

# =========================
# SIDEBAR LEGEND
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
st.subheader("🌐 Citra Satelit BMKG")

if IMG_OK:
    try:
        url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
        res = requests.get(url, timeout=10)
        img = Image.open(BytesIO(res.content))
        st.image(img, use_container_width=True)
    except:
        st.warning("⚠️ Gagal load citra")

# =========================
# 📦 UPLOAD NETCDF
# =========================
st.subheader("📦 Data NetCDF")
uploaded_file = st.file_uploader("Upload file .nc", type=["nc"])

def load_nc(file):
    try:
        ds = xr.open_dataset(file)

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

        return df

    except Exception as e:
        st.error(f"❌ NetCDF error: {e}")
        return None

# =========================
# DATA HANDLING
# =========================
if uploaded_file:
    df = load_nc(uploaded_file)
else:
    st.warning("⚠️ Menggunakan data simulasi")
    df = pd.DataFrame({
        "lat": np.random.uniform(-11, 6, 500),
        "lon": np.random.uniform(95, 141, 500),
        "cloud_top_temp": np.random.uniform(-80, 10, 500)
    })

# =========================
# PARAMETER TURUNAN
# =========================
df["cape"] = np.interp(df["cloud_top_temp"], [-80, 20], [3000, 100])
df["humidity"] = np.interp(df["cloud_top_temp"], [-80, 20], [95, 40])
df["rain_rate"] = np.interp(df["cloud_top_temp"], [-80, 20], [100, 0])

# =========================
# NORMALISASI
# =========================
def norm(x, a, b):
    return np.clip((x - a) / (b - a), 0, 1)

# =========================
# SCORING
# =========================
df["score"] = (
    0.4 * norm(df["cape"], 0, 4000) +
    0.3 * norm(abs(df["cloud_top_temp"]), 0, 90) +
    0.2 * norm(df["humidity"], 0, 100) +
    0.1 * norm(df["rain_rate"], 0, 100)
)

# =========================
# CLASSIFICATION
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
# ⏱️ WAKTU
# =========================
now = datetime.now()

st.subheader("⏱️ Informasi Waktu")
st.info(f"Update terakhir: {now.strftime('%Y-%m-%d %H:%M:%S')} WIB")

# =========================
# STATUS DOMINAN
# =========================
dominant_status = df["status"].value_counts().idxmax()

st.subheader("🚨 Status Saat Ini")
st.success(f"{dominant_status} pada {now.strftime('%H:%M WIB')}")

# =========================
# RIWAYAT STATUS
# =========================
st.subheader("📈 Riwayat Status")

def simulate_history(df):
    history = []
    base = datetime.now()

    for i in range(4):
        temp = df.copy()
        temp["cloud_top_temp"] += np.random.uniform(-3, 3, len(temp))

        temp["score"] = (
            0.4 * norm(temp["cape"], 0, 4000) +
            0.3 * norm(abs(temp["cloud_top_temp"]), 0, 90) +
            0.2 * norm(temp["humidity"], 0, 100) +
            0.1 * norm(temp["rain_rate"], 0, 100)
        )

        temp["status"] = temp["score"].apply(classify)

        history.append({
            "Waktu": (base - timedelta(minutes=(3-i)*10)).strftime("%H:%M"),
            "Status": temp["status"].value_counts().idxmax()
        })

    return pd.DataFrame(history)

st.table(simulate_history(df))

# =========================
# MAP STABLE
# =========================
st.subheader("🗺️ Peta Risiko Cuaca")

# simpan posisi map
if "map_center" not in st.session_state:
    st.session_state.map_center = [-2, 118]

if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 5

m = folium.Map(
    location=st.session_state.map_center,
    zoom_start=st.session_state.map_zoom,
    control_scale=True
)

color_map = {
    "🟢 Aman":"green",
    "🟡 Waspada":"orange",
    "🟠 Siaga":"darkorange",
    "🔴 Ekstrem":"red"
}

for _, r in df.iterrows():
    folium.CircleMarker(
        [r["lat"], r["lon"]],
        radius=5,
        color=color_map[r["status"]],
        fill=True,
        fill_opacity=0.7,
        popup=f"""
        <b>Status:</b> {r['status']}<br>
        <b>Score:</b> {r['score']:.2f}<br>
        CAPE: {r['cape']:.0f}<br>
        CTT: {r['cloud_top_temp']:.1f}°C<br>
        RH: {r['humidity']:.0f}%<br>
        Rain: {r['rain_rate']:.1f}
        """
    ).add_to(m)

map_data = st_folium(m, width=1200, height=520)

# simpan posisi terakhir (BIAR GA LONCAT)
if map_data and map_data.get("center"):
    st.session_state.map_center = [
        map_data["center"]["lat"],
        map_data["center"]["lng"]
    ]

if map_data and map_data.get("zoom"):
    st.session_state.map_zoom = map_data["zoom"]

# =========================
# TREND
# =========================
st.subheader("⏱️ Tren Awan")
st.line_chart(df["cloud_top_temp"].rolling(50).mean())

# =========================
# TABLE
# =========================
st.subheader("📊 Data Detail")
st.dataframe(df.sort_values("score", ascending=False), use_container_width=True)
