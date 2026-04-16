import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import xarray as xr
import numpy as np
from datetime import datetime

# ==============================
# CONFIG
# ==============================
st.set_page_config(page_title="EWS Satelit & Rason", layout="wide")

st.title("🌩️ Early Warning System (EWS)")
st.caption("Integrasi Satelit Himawari, NetCDF, dan Rason - BMKG")

# ==============================
# AUTO REFRESH (10 menit)
# ==============================
st.markdown(
    """
    <meta http-equiv="refresh" content="600">
    """,
    unsafe_allow_html=True
)

# ==============================
# AMBIL DATA SATELIT BMKG (PNG)
# ==============================
st.subheader("🌐 Citra Satelit Real-Time (BMKG)")

url = "https://inderaja.bmkg.go.id/IMAGE/HIMA/H08_EH_Indonesia.png"

try:
    response = requests.get(url, timeout=10)
    img = Image.open(BytesIO(response.content))
    st.image(img, use_container_width=True)
    st.success("✅ Data satelit berhasil dimuat")
except:
    st.error("❌ Gagal mengambil citra satelit")

# ==============================
# LOAD NETCDF (TBB)
# ==============================
st.subheader("📦 Analisis NetCDF (TBB)")

try:
    ds = xr.open_dataset("sample.nc")  # GANTI NAMA FILE

    # Sesuaikan nama variabel (cek print(ds))
    var_name = list(ds.data_vars)[0]
    tbb = ds[var_name]

    tbb_min = float(tbb.min().values)
    tbb_mean = float(tbb.mean().values)

    col1, col2 = st.columns(2)
    col1.metric("TBB Minimum (K)", f"{tbb_min:.2f}")
    col2.metric("TBB Rata-rata (K)", f"{tbb_mean:.2f}")

except Exception as e:
    st.warning("⚠️ NetCDF belum tersedia / error")
    tbb_min = 250  # fallback aman

# ==============================
# INPUT DATA RASON
# ==============================
st.subheader("🎈 Data Radiosonde (Rason)")

col3, col4 = st.columns(2)

CAPE = col3.number_input("CAPE (J/kg)", value=1000)
LI = col4.number_input("Lifted Index (LI)", value=-3)

# ==============================
# LOGIKA EWS
# ==============================
st.subheader("🚨 Status Early Warning System")

def ews_status(tbb, cape, li):
    if (tbb < 203) and (cape > 1000) and (li < -3):
        return "SIAGA 🔴", "Potensi konveksi kuat (CB / hujan lebat)"
    elif (tbb < 220) or (cape > 500):
        return "WASPADA 🟡", "Potensi awan konvektif"
    else:
        return "AMAN 🟢", "Kondisi relatif stabil"

status, desc = ews_status(tbb_min, CAPE, LI)

st.markdown(f"## {status}")
st.info(desc)

# ==============================
# INFO TAMBAHAN
# ==============================
st.subheader("📊 Informasi Sistem")

st.write(f"""
- **Sumber Satelit:** BMKG Himawari  
- **Analisis:** Brightness Temperature (TBB)  
- **Rason:** CAPE & Lifted Index  
- **Update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")

# ==============================
# FOOTER
# ==============================
st.markdown("---")
st.caption("Developed for Meteorological Early Warning System Research")
