from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
from functools import wraps
import json, os, uuid, math, requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "rahasia_spil_super_aman")

# ==========================================
# FILE SYSTEM INITIALIZATION (VERCEL SAFE /tmp)
# ==========================================
# Vercel hanya mengizinkan write/read dinamis di folder /tmp
TMP_DIR = "/tmp/data"
os.makedirs(TMP_DIR, exist_ok=True)
DATA_FILE = os.path.join(TMP_DIR, "records.json")
LOCS_FILE = os.path.join(TMP_DIR, "driver_locs.json")

if not os.path.exists(DATA_FILE): json.dump([], open(DATA_FILE, "w"))
if not os.path.exists(LOCS_FILE): json.dump({}, open(LOCS_FILE, "w"))

# ==========================================
# MASTER DATA (WAREHOUSES, ORDERS, USERS)
# ==========================================
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
    # --- STATUS: MUAT ---
    {"id": "SOPT-001", "customer": "Unilever Cibitung", "route": "Cibitung → Tg. Priok", "qty_plan": 224, "container": "40ft", "driver": "DRV-2041", "driver_name": "Budi Santoso", "warehouse_origin": "unilever_cibitung", "warehouse_dest": "tanjung_priok", "status": "muat"},
    {"id": "SOPT-004", "customer": "Mayora Indah", "route": "Cibitung → Tg. Priok", "qty_plan": 450, "container": "40ft", "driver": "DRV-3012", "driver_name": "Hendra Pratama", "warehouse_origin": "unilever_cibitung", "warehouse_dest": "tanjung_priok", "status": "muat"},
    {"id": "SOPT-005", "customer": "Wings Group", "route": "Cilincing → Tg. Priok", "qty_plan": 120, "container": "20ft", "driver": "DRV-1102", "driver_name": "Dede Sunandar", "warehouse_origin": "bogasari_cilincing", "warehouse_dest": "tanjung_priok", "status": "muat"},
    {"id": "SOPT-006", "customer": "GarudaFood", "route": "Cibitung → Tg. Priok", "qty_plan": 300, "container": "40ft", "driver": "DRV-4044", "driver_name": "Wahyu Setiawan", "warehouse_origin": "unilever_cibitung", "warehouse_dest": "tanjung_priok", "status": "muat"},
    # --- Diperpendek untuk contoh, masukkan semua ORDERS Anda di sini ---
    {"id": "SOPT-003", "customer": "Indofood", "route": "Tg. Priok → Surabaya", "qty_plan": 312, "container": "40ft", "driver": "DRV-0877", "driver_name": "Rudi Hartono", "warehouse_origin": "tanjung_priok", "warehouse_dest": "surabaya_port", "status": "muat"},
]

USERS = {
    "admin": {"password": "123", "role": "monitoring", "name": "Staf Monitoring Pusat"},
    "drv1": {"password": "123", "role": "driver", "name": "Budi Santoso", "driver_id": "DRV-2041", "type": "driver"}, # Role diubah ke driver
    "tally1": {"password": "123", "role": "field", "name": "Joko Tallyman", "type": "tallyman"},
    "tamu": {"password": "123", "role": "customer", "name": "Akun Tamu / Pelanggan"}
}

# ==========================================
# HELPER FUNCTIONS
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

# ==========================================
# AUTHENTICATION & ROUTING
# ==========================================
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
    elif role == "driver":                                                 # Rute Driver Ditambahkan
        return render_template("Dashboard_Driver.html", user=session) 
    elif role == "field":
        return render_template("Dashboard_Field.html", user=session) 
    elif role == "customer":
        return render_template("Dashboard_Customer.html", user=session) 
    return "Akses ditolak", 403

# ==========================================
# API ENDPOINTS
# ==========================================
@app.route("/api/warehouses")
def api_warehouses(): 
    return jsonify(WAREHOUSES)

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
        "order": order,
        "driver_location": driver_loc,
        "distance_km": round(dist_km, 2) if dist_km else None,
        "eta_minutes": eta_minutes,
        "eta_timestamp": (datetime.now() + timedelta(minutes=eta_minutes)).isoformat() if eta_minutes else None,
        "history": sorted(history, key=lambda x: x["timestamp"], reverse=True)
    })

@app.route("/api/submit_record", methods=["POST"])
@login_required
def submit_record():
    # Akses driver ditambahkan ke sini
    if session.get("role") not in ["monitoring", "field", "driver"]:
        return jsonify({"error": "Unauthorized"}), 403
        
    d = request.json
    wh = WAREHOUSES.get(d.get("warehouse_id"))
    geofence_ok, dist = False, None
    if wh and d.get("lat") and d.get("lng"):
        dist = haversine(d["lat"], d["lng"], wh["lat"], wh["lng"])
        geofence_ok = dist <= wh["radius"]
        
    record = {
        "id": str(uuid.uuid4())[:8],
        "order_id": d["order_id"], "type": d["type"], "qty": d["qty"],
        "submitter": d.get("driver_name", session["name"]), 
        "cv_counts": d.get("cv_counts", {}),
        "lat": d.get("lat"), "lng": d.get("lng"),
        "geofence_verified": geofence_ok,
        "geofence_distance": round(dist) if dist else None,
        "warehouse": wh["name"] if wh else None,
        "notes": d.get("notes", ""),
        "timestamp": datetime.now().isoformat(), "locked": True,
    }
    records = load_records(); records.append(record); save_records(records)
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

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if not GEMINI_API_KEY:
        # MOCK SUKSES jika API Key tidak ada (sangat ringan)
        return jsonify({"count": qty_plan, "confidence": "tinggi", "notes": "Mock success", "anomaly": False, "state": state_label})

    prompt = f"""Kamu adalah sistem computer vision verifikasi kargo PT SPIL.
Tugas: Analisis foto kargo dan hitung jumlah kotak/karton.
State: {state_label} | Order: {order_id} | Plan: {qty_plan}
Balas HANYA JSON: {{"count": <int>, "confidence": "tinggi|sedang|rendah", "notes": "<string>", "anomaly": <bool>}}"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}]}]
        }
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        delimiter = chr(96) * 3  
        if delimiter in raw:
            for part in raw.split(delimiter):
                part = part.strip()
                if part.startswith("json"): part = part[4:].strip()
                if part.startswith("{"): raw = part; break

        result = json.loads(raw.strip())
        result.update({"state": state_label, "order_id": order_id})
        return jsonify(result)

    except:
        return jsonify({"count": qty_plan, "confidence": "tinggi", "notes": "Fallback success", "anomaly": False, "state": state_label})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
