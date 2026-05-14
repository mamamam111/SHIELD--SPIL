# SPIL e-POD System — CV Edition (Gemini Vision)

## Cara Menjalankan

### 1. Install Python (jika belum ada)
Download dari https://python.org (versi 3.9+)

### 2. Extract ZIP
Extract file ZIP ke folder mana saja, misalnya `C:\spil-epod\`

### 3. Install dependencies
```
cd spil-epod-clean
pip install flask requests
```

### 4. Dapatkan API Key Gemini (GRATIS)
1. Buka https://aistudio.google.com
2. Klik "Get API Key" → "Create API Key"
3. Copy API key-nya (format: `AIzaSy...`)

### 5. Masukkan API Key ke app.py
Buka file `app.py`, cari baris:
```python
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
```
Ganti jadi:
```python
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyXXXXXXXXXXXXXXXX")
```

### 6. Jalankan
```
python app.py
```

### 7. Buka di browser
```
http://localhost:5000
```

---

## Fitur
- 📍 Geofence check-in (GPS + simulasi slider + Leaflet map)
- 📷 Kamera watermark (GPS + timestamp + user ID otomatis)
- 🤖 CV Hitung Kotak (Gemini 1.5 Flash Vision, 5 state: 0/20/50/70/100%)
- 📋 Form e-POD (submit & kunci data)
- 🗺️ BYOD Tracker (klik peta untuk update posisi driver)
- 📊 Dashboard monitoring
- 🗂️ Riwayat kargo dengan CV count

## Catatan
- Data tersimpan di folder `data/` dalam format JSON
- Fitur CV memerlukan koneksi internet dan Gemini API key (gratis)
- Gemini 1.5 Flash gratis hingga 15 request/menit, 1500 request/hari
