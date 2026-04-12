import streamlit as st
import xarray as xr
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
import json

st.title("🌩️ Early Warning System - Riau")

# =========================
# UPLOAD FILE
# =========================
uploaded_nc = st.file_uploader("Upload file Himawari (.nc)", type=["nc"])
uploaded_geo = st.file_uploader("Upload shapefile Riau (.geojson)", type=["geojson"])

if uploaded_nc and uploaded_geo:

    # =========================
    # LOAD DATA
    # =========================
    data = xr.open_dataset(uploaded_nc)

    tbb = data['tbb'].values
    lat = data['latitude'].values
    lon = data['longitude'].values

    # FILTER RIAU
    lat_min, lat_max = -1.5, 1.5
    lon_min, lon_max = 100.0, 104.5

    lat_mask = (lat >= lat_min) & (lat <= lat_max)
    lon_mask = (lon >= lon_min) & (lon <= lon_max)

    tbb = tbb[lat_mask][:, lon_mask]
    lat = lat[lat_mask]
    lon = lon[lon_mask]

    tbb = tbb - 273.15

    # GRID
    polygons = []
    temps = []

    for i in range(len(lat)-1):
        for j in range(len(lon)-1):
            poly = Polygon([
                (lon[j], lat[i]),
                (lon[j], lat[i+1]),
                (lon[j+1], lat[i+1]),
                (lon[j+1], lat[i])
            ])

            temp = tbb[i, j]

            if not np.isnan(temp):
                polygons.append(poly)
                temps.append(temp)

    df = pd.DataFrame({'temperature': temps, 'geometry': polygons})
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")

    # LOAD SHAPEFILE
    kec = gpd.read_file(uploaded_geo)

    results = []

    for _, row in kec.iterrows():
        geom = row.geometry
        name = row['NAME_3']

        inter = gdf[gdf.intersects(geom)]

        if not inter.empty:
            min_temp = inter['temperature'].min()

            if min_temp <= -70:
                status = "EKSTREM"
            elif min_temp <= -60:
                status = "WASPADA"
            else:
                status = "AMAN"

            results.append({
                "Kecamatan": name,
                "Suhu": round(min_temp, 2),
                "Status": status
            })

    df_result = pd.DataFrame(results)

    st.success("✅ Analisis selesai!")
    st.dataframe(df_result)

    # DOWNLOAD
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }

    for r in results:
        geojson["features"].append({
            "type": "Feature",
            "properties": r
        })

    st.download_button(
        "📥 Download hasil",
        json.dumps(geojson),
        file_name="riau_warning.geojson"
    )
