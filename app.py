import streamlit as st
import numpy as np
import pandas as pd
import folium
import xarray as xr
from streamlit_folium import st_folium

# =========================
# ⚙️ CONFIG
# =========================
st.set_page_config(page_title="SkyAlert - EWS", layout="wide")

st.title("🌩️ SkyAlert – Early Warning System")
st.caption("Satellite-Based Explainable Meteorological EWS | Resti Maulina C.C")

# =========================
# 📘 SIDEBAR LEGEND (ILMIAH + AWAM)
# =========================
st.sidebar.header("📘 Legenda & Threshold")

st.sidebar.markdown("""
### 🚨 Status Cuaca
🟢 **Aman** → atmosfer stabil  
🟡 **Waspada** → mulai terbentuk awan hujan  
🟠 **Siaga** → potensi hujan lebat  
🔴 **Ekstrem** → hujan lebat + petir + angin kencang  

---

### 🌡️ Cloud Top Temp (CTT)
- < -70°C → awan badai (CB kuat)  
- -70 s/d -40°C → awan konvektif  

📚 NOAA / JMA  

---

### ⚡ CAPE
- < 1000 → lemah  
- 1000–2500 → sedang  
- > 2500 → kuat  

📚 WMO  

---

### 💧 Kelembapan
- > 80% → sangat lembap  

---

### 🌧️ Rain Rate
- > 50 mm/h → hujan ekstrem  
""")

# =========================
# 📦 LOAD NETCDF
# =========================
@st.cache_data(ttl=600)
def load_real_data():
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
        })

        df = df.dropna()

        # =========================
        # PARAMETER TURUNAN
        # =========================
        df["cape"] = np.interp(df["cloud_top_temp"], [-80, 20], [3000, 100])
        df["humidity"] = np.interp(df["cloud_top_temp"], [-80, 20], [95, 40])
        df["rain_rate"] = np.interp(df["cloud_top_temp"], [-80, 20], [100, 0])

        if len(df) > 2500:
            df = df.sample(2500, random_state=42)

        return df

    except Exception as e:
        st.error(f"❌ Gagal load NetCDF: {e}")
        return None

df = load_real_data()

if df is None:
    st.stop()

# =========================
# 🧮 NORMALISASI
# =========================
def norm(x, min_v, max_v):
    return np.clip((x - min_v) / (max_v - min_v), 0, 1)

# =========================
# ⚡ SCORING
# =========================
def compute_score(row):
    return (
        0.4 * norm(row["cape"], 0, 4000) +
        0.3 * norm(abs(row["cloud_top_temp"]), 0, 90) +
        0.2 * norm(row["humidity"], 0, 100) +
        0.1 * norm(row["rain_rate"], 0, 100)
    )

df["score"] = df.apply(compute_score, axis=1)

# =========================
# 🚨 CLASSIFICATION
# =========================
def classify(score):
    if score < 0.30:
        return "🟢 Aman"
    elif score < 0.60:
        return "🟡 Waspada"
    elif score < 0.80:
        return "🟠 Siaga"
    else:
        return "🔴 Ekstrem"

df["status"] = df["score"].apply(classify)

# =========================
# 🧠 EXPLAIN ENGINE (UPGRADE)
# =========================
def explain(row):
    alasan = []

    if row["cape"] > 2500:
        alasan.append("CAPE sangat tinggi → atmosfer sangat labil")
    elif row["cape"] > 1000:
        alasan.append("CAPE sedang → potensi konveksi")

    if row["cloud_top_temp"] < -70:
        alasan.append("Awan sangat tinggi (Cumulonimbus kuat)")
    elif row["cloud_top_temp"] < -40:
        alasan.append("Awan konvektif berkembang")

    if row["humidity"] > 80:
        alasan.append("Kelembapan tinggi → mendukung awan hujan")

    if row["rain_rate"] > 50:
        alasan.append("Hujan intensitas sangat lebat")

    return alasan

# =========================
# 📊 METRIC
# =========================
col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Data", len(df))
col2.metric("Ekstrem", (df["status"] == "🔴 Ekstrem").sum())
col3.metric("Siaga", (df["status"] == "🟠 Siaga").sum())
col4.metric("Aman", (df["status"] == "🟢 Aman").sum())

# =========================
# 🗺️ MAP
# =========================
st.subheader("🗺️ Peta Risiko Cuaca")

m = folium.Map(location=[-2, 118], zoom_start=5)

color_map = {
    "🟢 Aman": "green",
    "🟡 Waspada": "orange",
    "🟠 Siaga": "darkorange",
    "🔴 Ekstrem": "red"
}

for _, r in df.iterrows():
    explanation = explain(r)

    folium.CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=5,
        color=color_map[r["status"]],
        fill=True,
        fill_opacity=0.7,
        popup=folium.Popup(
            f"""
            <b>Status:</b> {r['status']}<br>
            <b>Score:</b> {r['score']:.2f}<br><br>

            CAPE: {r['cape']:.0f} J/kg<br>
            CTT: {r['cloud_top_temp']:.1f}°C<br>
            RH: {r['humidity']:.0f}%<br>
            Rain: {r['rain_rate']:.1f} mm/h<br><br>

            <b>Penjelasan:</b><br>
            {"<br>".join(explanation)}<br><br>

            <b>Kesimpulan:</b><br>
            Potensi hujan lebat disertai petir dan angin kencang.
            """,
            max_width=300
        )
    ).add_to(m)

st_folium(m, width=1200, height=520)

# =========================
# 📊 TABLE
# =========================
st.subheader("📊 Data Detail")

df["explanation"] = df.apply(explain, axis=1)

st.dataframe(df.sort_values("score", ascending=False), use_container_width=True)

# =========================
# ⏱️ AUTO REFRESH
# =========================
st.markdown("<meta http-equiv='refresh' content='600'>", unsafe_allow_html=True)
