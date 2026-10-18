import os
import math
import time
import urllib.request

# ==============================================================================
# 📌 CUKUP ISI 3 PARAMETER INI SAJA
# ==============================================================================
CENTER_LAT = -0.041365487995099995  # Latitude Tengah (dari Google Maps)
CENTER_LON = 109.31581118662814      # Longitude Tengah (dari Google Maps)

COVERAGE_KM = 50                    # Pilih: 50 (untuk 50x50 KM) atau 200 (untuk 200x200 KM)

ZOOM_LEVELS = [13, 14]              # Zoom Level (Rekomendasi: 13 & 14 untuk area 50-200km)
# ==============================================================================

# Hitung Batas Bounding Box dari Radius KM
half_side_km = COVERAGE_KM / 2.0
delta_lat = half_side_km / 111.32
delta_lon = half_side_km / (111.32 * math.cos(math.radians(CENTER_LAT)))

LAT_MIN = CENTER_LAT - delta_lat
LAT_MAX = CENTER_LAT + delta_lat
LON_MIN = CENTER_LON - delta_lon
LON_MAX = CENTER_LON + delta_lon

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

print("==================================================")
print(f"🌍 MAP DOWNLOADER - PATHFINDER PRO")
print(f"📍 Center Point : {CENTER_LAT}, {CENTER_LON}")
print(f"📐 Area Coverage: {COVERAGE_KM} x {COVERAGE_KM} KM ({COVERAGE_KM**2} km²)")
print("==================================================")

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
total_downloaded = 0

for zoom in ZOOM_LEVELS:
    x_min, y_max = deg2num(LAT_MIN, LON_MIN, zoom)
    x_max, y_min = deg2num(LAT_MAX, LON_MAX, zoom)
    
    x_start, x_end = min(x_min, x_max), max(x_min, x_max)
    y_start, y_end = min(y_min, y_max), max(y_min, y_max)
    
    total_tiles = (x_end - x_start + 1) * (y_end - y_start + 1)
    print(f"\n🌀 Processing Zoom {zoom}: Total {total_tiles} tile images...")

    for x in range(x_start, x_end + 1):
        for y in range(y_start, y_end + 1):
            folder_path = f"maps/{zoom}/{x}"
            os.makedirs(folder_path, exist_ok=True)
            file_path = f"{folder_path}/{y}.png"
            
            if os.path.exists(file_path):
                continue
                
            # Gunakan ESRI Topo Map Server (Sangat cepat & stabil)
            url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{zoom}/{y}/{x}"
            
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req) as response, open(file_path, 'wb') as out_file:
                    out_file.write(response.read())
                total_downloaded += 1
                print(f"[{total_downloaded}] Saved: {file_path}")
                time.sleep(0.05) # Delay 50ms (Super Fast)
            except Exception as e:
                print(f"❌ Error {file_path}: {e}")

print("\n==================================================")
print(f"✅ DOWNLOAD SELESAI! ({total_downloaded} tiles)")
print("👉 Langkah Selanjutnya: Jalankan 'python convert.py'")
print("==================================================")