from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from functools import wraps
import json, os, uuid, math, requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import base64
import cv2
import numpy as np
from ultralytics import YOLO

# ==========================================
# 1. INISIALISASI MODEL YOLOv11
# ==========================================
try:
    print("⏳ Memuat model YOLO...")
    yolo_model = YOLO("yolo11n.pt") 
    print("✅ Model YOLO Berhasil Dimuat!")
except Exception as e:
    print(f"⚠️ Gagal memuat YOLO: {e}")
    yolo_model = None

# ==========================================
# 2. GOOGLE SHEETS API CONFIGURATION
# ==========================================
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets"
]
SPREADSHEET_ID = "1srzozS42VqmWjhFqhYBLBx4jlZi-yOYWgb8ee3PWWb0" 

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
    gs_client = gspread.authorize(creds)
    sheet = gs_client.open_by_key(SPREADSHEET_ID).sheet1 
    GOOGLE_API_READY = True
    print("✅ Google Sheets API Berhasil Terhubung!")
except Exception as e:
    print(f"⚠️ Peringatan: Google Sheets API gagal dimuat. Error: {e}")
    GOOGLE_API_READY = False

# ==========================================
# 3. IMGBB API CONFIGURATION
# ==========================================
IMGBB_API_KEY = "c488f76dc838a7ff1b7da732e0174a9e"

def upload_to_imgbb(base64_data):
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
            
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64_data
        }
        res = requests.post(url, data=payload)
        
        if res.status_code == 200:
            return res.json()["data"]["url"]
        else:
            print(f"ImgBB Error: {res.text}")
            return "UPLOAD_FAILED"
    except Exception as e:
        print(f"Gagal upload gambar ke ImgBB: {e}")
        return "UPLOAD_FAILED"

# ==========================================
# APP INITIALIZATION & MASTER DATA
# ==========================================
app = Flask(__name__)
app.secret_key = os.urandom(24)

DATA_FILE = "data/records.json"
LOCS_FILE = "data/driver_locs.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(DATA_FILE): json.dump([], open(DATA_FILE, "w"))
if not os.path.exists(LOCS_FILE): json.dump({}, open(LOCS_FILE, "w"))

WAREHOUSES = {
    "unilever_cibitung":  {"name": "Gudang Unilever Cibitung", "lat": -6.2841, "lng": 107.1563, "radius": 100},
    "bogasari_cilincing": {"name": "Gudang Bogasari Cilincing", "lat": -6.1088, "lng": 106.9172, "radius": 100},
    "tanjung_priok":      {"name": "Pelabuhan Tanjung Priok",  "lat": -6.1077, "lng": 106.8817, "radius": 100},
    "surabaya_port":      {"name": "Pelabuhan Tj. Perak, SBY", "lat": -7.1983, "lng": 112.7319, "radius": 100},
    "semarang_port":      {"name": "Pelabuhan Tj. Emas, SMG", "lat": -6.9458, "lng": 110.4208, "radius": 100},
    "makassar_port":      {"name": "Pelabuhan Soekarno Hatta, MKS", "lat": -5.1235, "lng": 119.4005, "radius": 100},
    "belawan_port":       {"name": "Pelabuhan Belawan, MDN", "lat": 3.7845, "lng": 98.6833, "radius": 100},
    "pontianak_port":     {"name": "Pelabuhan Dwikora, PTK", "lat": -0.0150, "lng": 109.3333, "radius": 100},
    "balikpapan_port":    {"name": "Pelabuhan Semayang, BPN", "lat": -1.2785, "lng": 116.8150, "radius": 100},
    "banjarmasin_port":   {"name": "Pelabuhan Trisakti, BJM", "lat": -3.3289, "lng": 114.5824, "radius": 100},
    "ambon_port":         {"name": "Pelabuhan Yos Sudarso, AMQ", "lat": -3.6944, "lng": 128.1783, "radius": 100},
    "jayapura_port":      {"name": "Pelabuhan Jayapura, DJJ", "lat": -2.5333, "lng": 140.7000, "radius": 100},
}

ORDERS = [
    {
        "id": "SOPT-001", "customer": "Unilever Cibitung", "route": "Cibitung → Tg. Priok", 
        "qty_plan": 224, "container": "40ft", "driver": "DRV-2041", "driver_name": "Budi Santoso", 
        "warehouse_origin": "unilever_cibitung", "warehouse_dest": "tanjung_priok", "status": "muat"
    },
    {
        "id": "SOPT-002", "customer": "Bogasari Cilincing", "route": "Cilincing → Tg. Priok", 
        "qty_plan": 180, "container": "20ft", "driver": "DRV-1055", "driver_name": "Agus Purnomo", 
        "warehouse_origin": "bogasari_cilincing", "warehouse_dest": "tanjung_priok", "status": "muat"
    },
    {
        "id": "SOPT-003", "customer": "Indofood", "route": "Tg. Priok → Surabaya", 
        "qty_plan": 312, "container": "40ft", "driver": "DRV-0877", "driver_name": "Rudi Hartono", 
        "warehouse_origin": "tanjung_priok", "warehouse_dest": "surabaya_port", "status": "muat"
    },
    {
        "id": "SOPT-004", "customer": "Wings Group", "route": "Cibitung → Semarang", 
        "qty_plan": 450, "container": "40ft HD", "driver": "DRV-3012", "driver_name": "Ahmad Dani", 
        "warehouse_origin": "unilever_cibitung", "warehouse_dest": "semarang_port", "status": "muat"
    },
    {
        "id": "SOPT-005", "customer": "Mayora", "route": "Surabaya → Makassar", 
        "qty_plan": 120, "container": "20ft", "driver": "DRV-4421", "driver_name": "Iwan Fals", 
        "warehouse_origin": "surabaya_port", "warehouse_dest": "makassar_port", "status": "muat"
    }
]

USERS = {
    # 1. Tim Monitoring Pusat (Bisa akses radar dan tabel matriks)
    "admin": {"password": "123", "role": "monitoring", "name": "Staf Monitoring Pusat"},
    
    # 2. Driver Armada (Bisa akses rute, wajb GPS, dan update status perjalanan)
    "drv1": {"password": "123", "role": "driver", "name": "Budi Santoso", "driver_id": "DRV-2041", "type": "driver"},
    
    # 3. Tallyman Lapangan (Bisa akses kamera AI, jepret per baris, validasi geofence)
    "tally1": {"password": "123", "role": "field", "name": "Joko Tallyman", "type": "tallyman"},
    
    # 4. Pelanggan / Customer (Bisa akses tracking barang miliknya sendiri)
    "tamu": {"password": "123", "role": "customer", "name": "Customers"}
}

# ==========================================
# HELPER FUNCTIONS & AUTH
# ==========================================
def load_records():
    try: return json.load(open(DATA_FILE))
    except: return []

def save_records(records):
    json.dump(records, open(DATA_FILE, "w"), indent=2)

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000 
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json if request.is_json else request.form
        username = data.get("username")
        password = data.get("password")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["user_id"] = username
            session["role"] = user["role"]
            session["name"] = user["name"]
            if "driver_id" in user: session["driver_id"] = user["driver_id"]
            return jsonify({"success": True, "role": user["role"], "redirect": "/"})
        return jsonify({"success": False, "error": "Username atau Password salah!"}), 401
    return render_template("Login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    role = session.get("role")
    if role == "monitoring": 
        return render_template("Dashboard_Monitoring.html", user=session)
    elif role == "driver":   # <-- Tambahan rute untuk mengarahkan ke dashboard khusus Driver
        return render_template("Dashboard_Driver.html", user=session) 
    elif role == "field":    # <-- Role field sekarang didedikasikan untuk Tallyman/Pengawas Lapangan
        return render_template("Dashboard_Field.html", user=session) 
    elif role == "customer": 
        return render_template("Dashboard_Customer.html", user=session) 
    return "Akses ditolak", 403

# ==========================================
# API ENDPOINTS
# ==========================================
@app.route("/api/submit_record", methods=["POST"])
@login_required
def submit_record():
    if session.get("role") not in ["monitoring", "field", "driver"]: # <-- Izin Driver ditambah untuk update trip status
        return jsonify({"error": "Unauthorized"}), 403
        
    d = request.json
    wh = WAREHOUSES.get(d.get("warehouse_id"))
    geofence_ok, dist = False, None
    if wh and d.get("lat") and d.get("lng"):
        dist = haversine(d["lat"], d["lng"], wh["lat"], wh["lng"])
        geofence_ok = dist <= wh["radius"]
        
    record_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat()
    submitter = d.get("driver_name", session["name"])
    
    cv_counts = d.get("cv_counts", {})
    best_photo_b64 = None
    photo_link = "TIDAK_ADA_FOTO"
    
    cv_log_clean = {}
    if cv_counts:
        for state, data in cv_counts.items():
            cv_log_clean[state] = {
                "count": data.get("count"), "confidence": data.get("confidence"),
                "anomaly": data.get("anomaly"), "notes": data.get("notes")
            }
            if data.get("photo"): best_photo_b64 = data.get("photo")
                
    if best_photo_b64:
        photo_link = upload_to_imgbb(best_photo_b64)

    row_data = [
        timestamp, record_id, d["order_id"], d["type"].upper(), submitter,
        wh["name"] if wh else "Unknown", "VALID" if geofence_ok else "INVALID",
        round(dist) if dist else 0, d["qty"], str(cv_log_clean), photo_link
    ]
    
    if GOOGLE_API_READY:
        try: sheet.append_row(row_data)
        except Exception as e: print(f"Error insert ke Sheets: {e}")

    record = {
        "id": record_id, "order_id": d["order_id"], "type": d["type"], "qty": d["qty"],
        "submitter": submitter, "cv_counts": cv_counts, "lat": d.get("lat"), "lng": d.get("lng"),
        "geofence_verified": geofence_ok, "geofence_distance": round(dist) if dist else None,
        "warehouse": wh["name"] if wh else None, "notes": d.get("notes", ""),
        "photo_link": photo_link, "timestamp": timestamp, "locked": True,
    }
    records = load_records()
    records.append(record)
    save_records(records)
    
    return jsonify({"success": True, "record": record})

@app.route("/api/count_boxes", methods=["POST"])
def count_boxes():
    d = request.json
    image_b64 = d.get("image", "")
    state_label = d.get("state", "?")
    order_id    = d.get("order_id", "")
    qty_plan    = d.get("qty_plan", 0)

    if not image_b64:
        return jsonify({"error": "No image provided"}), 400
        
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    if yolo_model is None:
        return jsonify({"count": qty_plan, "confidence": "rendah", "notes": "YOLO Offline, pakai estimasi manual", "anomaly": False, "state": state_label})

    try:
        # Konversi Base64 ke format OpenCV
        img_bytes = base64.b64decode(image_b64)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Inferensi YOLO
        results = yolo_model.predict(source=img, conf=0.25, save=False, show=False, verbose=False)
        boxes = results[0].boxes
        detected_count = len(boxes)
        
        # Gambar Bounding Box & Convert ke Base64
        annotated_img = results[0].plot()  # YOLO menggambar kotak di sini
        _, buffer = cv2.imencode('.jpg', annotated_img)
        annotated_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Analisis Anomali
        is_anomaly = False
        notes = f"YOLO mendeteksi {detected_count} objek."
        if detected_count == 0:
            is_anomaly = True
            notes = "Peringatan: Tidak ada objek yang terdeteksi!"

        return jsonify({
            "count": detected_count,
            "confidence": "tinggi" if detected_count > 0 else "rendah",
            "notes": notes,
            "anomaly": is_anomaly,
            "state": state_label,
            "order_id": order_id,
            "annotated_image": annotated_b64
        })

    except Exception as e:
        print(f"Error YOLO: {e}")
        return jsonify({"count": qty_plan, "confidence": "rendah", "notes": f"Error analisis gambar", "anomaly": True, "state": state_label})

@app.route("/api/warehouses")
def api_warehouses(): return jsonify(WAREHOUSES)

@app.route("/api/orders")
def api_orders():
    records = load_records()
    orders = []
    for o in ORDERS:
        recs = [r for r in records if r["order_id"] == o["id"]]
        muat    = next((r for r in recs if r["type"] == "muat"), None)
        bongkar = next((r for r in recs if r["type"] == "bongkar"), None)
        selisih = (muat["qty"] - bongkar["qty"]) if muat and bongkar else None
        orders.append({**o, "record_muat": muat, "record_bongkar": bongkar, "selisih": selisih})
    return jsonify(orders)

@app.route("/api/records", methods=["GET"])
def api_records():
    try: return jsonify(load_records())
    except: return jsonify([])

@app.route("/api/driver_locations", methods=["GET"])
def get_driver_locations():
    try: return jsonify(json.load(open(LOCS_FILE)))
    except: return jsonify({})

@app.route("/api/driver_location", methods=["POST"])
def update_driver_location():
    d = request.json
    try: locs = json.load(open(LOCS_FILE))
    except: locs = {}
    locs[d["driver_id"]] = {
        "driver_name": d.get("driver_name"), "order_id": d.get("order_id"),
        "lat": d["lat"], "lng": d["lng"], "speed": d.get("speed", 0),
        "gps_active": True, "updated": datetime.now().isoformat(),
    }
    json.dump(locs, open(LOCS_FILE, "w"), indent=2)
    return jsonify({"success": True})

@app.route("/api/track/<order_id>")
def track_order(order_id):
    order = next((o for o in ORDERS if o["id"] == order_id), None)
    if not order: return jsonify({"error": "Order tidak ditemukan"}), 404

    try: locs = json.load(open(LOCS_FILE))
    except: locs = {}
    
    driver_loc = locs.get(order["driver"])
    dest_wh = WAREHOUSES.get(order["warehouse_dest"])
    
    eta_minutes = None
    dist_km = None
    
    if driver_loc and dest_wh:
        dist_meters = haversine(driver_loc["lat"], driver_loc["lng"], dest_wh["lat"], dest_wh["lng"])
        dist_km = dist_meters / 1000
        speed_kmh = driver_loc.get("speed", 0)
        if speed_kmh <= 5: speed_kmh = 30 
        waktu_jam = dist_km / speed_kmh
        eta_minutes = round(waktu_jam * 60)
        
    records = load_records()
    history = [r for r in records if r["order_id"] == order_id]
    
    return jsonify({
        "order": order, "driver_location": driver_loc,
        "distance_km": round(dist_km, 2) if dist_km else None,
        "eta_minutes": eta_minutes,
        "eta_timestamp": (datetime.now() + timedelta(minutes=eta_minutes)).isoformat() if eta_minutes else None,
        "history": sorted(history, key=lambda x: x["timestamp"], reverse=True)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
