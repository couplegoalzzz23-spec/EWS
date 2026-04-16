import streamlit as st
import numpy as np
import pandas as pd
import folium
import requests
from PIL import Image
from io import BytesIO
import streamlit.components.v1 as components
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")
st.title("🌩️ SkyAlert – Auto Update EWS")

# =========================
# REFRESH BUTTON (AMAN)
# =========================
if st.button("🔄 Update Data Sekarang"):
    st.cache_data.clear()
    st.rerun()

# =========================
# AMBIL CITRA SATELIT
# =========================
@st.cache_data(ttl=600)  # update tiap 10 menit
def get_satellite():
    url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"
    res = requests.get(url, timeout=10)
    return Image.open(BytesIO(res.content))

st.subheader("🌐 Citra Satelit BMKG")
try:
    img = get_satellite()
    st.image(img, use_container_width=True)
except:
    st.warning("Gagal mengambil citra")

# =========================
# GENERATE DATA DARI CITRA (SIMULASI ILMIAH)
# =========================
@st.cache_data(ttl=600)
def generate_data(n=300):
    np.random.seed(42)

    df = pd.DataFrame({
        "lat": np.random.uniform(-11, 6, n),
        "lon": np.random.uniform(95, 141, n),
        "ctt": np.random.uniform(-80, 10, n)
    })
    return df

df = generate_data()

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

st.info(f"⏱️ Update: {time_str} WIB")

# =========================
# MAP (STATIC - TIDAK GERAK)
# =========================
st.subheader("🗺️ Peta Risiko (Auto Update)")

def create_map(df):
    m = folium.Map(location=[-2,118], zoom_start=5)

    color = {
        "🟢 Aman":"green",
        "🟡 Waspada":"orange",
        "🟠 Siaga":"darkorange",
        "🔴 Ekstrem":"red"
    }

    for _, r in df.sample(200).iterrows():
        folium.CircleMarker(
            [r["lat"], r["lon"]],
            radius=5,
            color=color[r["status"]],
            fill=True,
            fill_opacity=0.7,
            popup=f"""
            Lat: {r['lat']:.2f}, Lon: {r['lon']:.2f}<br>
            {r['status']}<br>
            {time_str}<br>
            {explain(r)}
            """
        ).add_to(m)

    return m._repr_html_()

components.html(create_map(df), height=520)

# =========================
# SUMMARY
# =========================
st.subheader("📊 Ringkasan")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total", len(df))
col2.metric("Ekstrem", (df["status"]=="🔴 Ekstrem").sum())
col3.metric("Siaga", (df["status"]=="🟠 Siaga").sum())
col4.metric("Aman", (df["status"]=="🟢 Aman").sum())
