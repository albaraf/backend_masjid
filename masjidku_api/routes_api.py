from fastapi import APIRouter, UploadFile, File
from datetime import datetime
from pydantic import BaseModel
import requests
import base64
import firebase_admin
from firebase_admin import credentials, firestore
import io
from PIL import Image
import pytesseract
import sys
from bs4 import BeautifulSoup
import re
from collections import Counter
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import midtransclient
import time
from threading import Thread
import schedule

# ==============================================================================
# INITIALIZATION
# ==============================================================================
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()
router = APIRouter()

class DonasiRequest(BaseModel):
    amount: int
    user_id: str

# Inisialisasi Midtrans CoreApi di tingkat modul agar bisa diakses oleh fungsi eksternal
core = midtransclient.CoreApi(
    is_production=False,
    server_key='MIDTRANS_SERVER_KEY',
    client_key='MIDTRANS_SERVER_KEY'
)

def auto_check_status():
    while True:
        try:
            # Memastikan mengecek status transaksi yang pending
            pending_donations = db.collection('donations').where('status', '==', 'pending').stream()

            for doc in pending_donations:
                order_id = doc.id
                status_response = core.transactions.status(order_id)
                transaction_status = status_response.get('transaction_status')

                if transaction_status in ['settlement', 'capture']:
                    doc.reference.update({'status': 'success'})
                    print(f"Transaksi {order_id} otomatis sukses!")
        except Exception as e:
            print(f"Error pada auto_check_status: {e}")
        time.sleep(60)

# Jalankan thread pengecekan status otomatis
Thread(target=auto_check_status, daemon=True).start()

# ==============================================================================
# ENDPOINTS UTAMA (LOG, SINKRONISASI & DONASI)
# ==============================================================================

def job_berita():
    print("Mulai crawling berita terbaru...")
    # ... masukkan kode crawling berita kamu di sini ...
    print("Crawling berita selesai!")

# Buat thread untuk menjalankan schedule berita (Alternative selain APScheduler)
def run_scheduler():
    schedule.every().day.at("01:00").do(job_berita) # Set jam 1 pagi
    while True:
        schedule.run_pending()
        time.sleep(1)

Thread(target=run_scheduler, daemon=True).start()

@router.post("/sync-google")
async def sync_google(data: dict):
    name = data.get("name")
    email = data.get("email")
    activity_type = data.get("activity", "Registrasi Akun Baru Berhasil")

    if not email:
        return {"status": "error", "message": "Email tidak boleh kosong"}

    log_data = {
        "email": email,
        "activity": activity_type,
        "timestamp": datetime.now(),
        "details": f"User {name if name else 'Tanpa Nama'} melakukan: {activity_type}"
    }
    db.collection('logs').add(log_data)
    return {"status": "success"}

@router.post("/log-activity")
async def log_activity(data: dict):
    email = data.get("email")
    action = data.get("action")
    if not email or not action:
        return {"status": "error", "message": "Email dan action harus diisi"}

    db.collection('logs').add({
        "email": email,
        "activity": action,
        "timestamp": datetime.now(),
        "details": f"User {email} melakukan tindakan: {action}"
    })
    return {"status": "success"}

@router.get("/logs")
async def get_logs():
    docs = db.collection('logs').order_by("timestamp", direction="DESCENDING").limit(10).stream()
    log_list = []
    for doc in docs:
        d = doc.to_dict()
        if "timestamp" in d and d["timestamp"]:
            d["timestamp"] = d["timestamp"].isoformat()
        log_list.append(d)
    return log_list

@router.post("/donasi")
async def create_donation(request: DonasiRequest):
    try:
        MIDTRANS_SERVER_KEY = "MIDTRANS_SERVER_KEY"
        clean_user_id = request.user_id.split('@')[0]
        order_id = f"DONASI-{clean_user_id}-{int(datetime.now().timestamp() * 1000)}"

        payload = {
            "transaction_details": {"order_id": order_id, "gross_amount": request.amount},
            "credit_card": {"secure": True}
        }

        auth_string = base64.b64encode(f"{MIDTRANS_SERVER_KEY}:".encode()).decode()
        response = requests.post(
            "https://app.sandbox.midtrans.com/snap/v1/transactions",
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Basic {auth_string}"}
        )

        midtrans_data = response.json()

        if response.status_code == 201:
            db.collection('donations').document(order_id).set({
                "user_id": request.user_id, 
                "amount": request.amount, 
                "status": "pending",
                "snap_token": midtrans_data.get("token"), 
                "redirect_url": midtrans_data.get("redirect_url"), 
                "timestamp": datetime.now()
            })
            db.collection('logs').add({
                "email": request.user_id, 
                "activity": f"Inisiasi Donasi Rp{request.amount}",
                "timestamp": datetime.now(), 
                "details": f"Donasi baru ID: {order_id}"
            })
            return {
                "status": "success", 
                "token": midtrans_data.get("token"), 
                "redirect_url": midtrans_data.get("redirect_url")
            }
        else:
            return {"status": "error", "message": midtrans_data.get("error_messages")}
    except Exception as e:
        return {"status": "error", "message": f"Terjadi kesalahan internal: {str(e)}"}

# ==============================================================================
# ENDPOINT OCR (SCAN GAMBAR / STRUK)
# ==============================================================================

@router.post("/scan-struk")
async def scan_struk(file: UploadFile = File(...)):
    try:
        # Konfigurasi Path Tesseract (Mendukung Windows & Linux Ubuntu)
        if sys.platform.startswith('win'):
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        elif sys.platform.startswith('linux'):
            pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

        contents = await file.read()
        
        # 1. IMAGE PRE-PROCESSING
        # Ubah gambar menjadi hitam putih (Grayscale) agar Tesseract lebih mudah membaca teksnya
        image = Image.open(io.BytesIO(contents)).convert('L')
        
        # 2. PROSES OCR
        extracted_text = pytesseract.image_to_string(image)
        
        # 3. TEXT ANALYSIS (Mencari Nama Item & Nominal)
        # Pecah teks menjadi baris per baris, dan abaikan baris yang kosong
        lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]
        
        # Asumsi: Baris pertama di struk biasanya adalah Nama Toko / Barang
        nama_item = lines[0] if lines else "Toko Tidak Terbaca"
        
        # Gunakan Regex untuk mencari semua pola angka (misal: 50000, 50.000, 150.000,00)
        numbers = re.findall(r'\b\d{1,3}(?:\.\d{3})*(?:,\d+)?\b', extracted_text)
        
        parsed_numbers = []
        for num_str in numbers:
            # Hapus titik dan koma untuk mendapatkan angka murni
            clean_num = re.sub(r'[^\d]', '', num_str)
            if clean_num:
                parsed_numbers.append(int(clean_num))
                
        # Asumsi Logis: Angka terbesar di dalam sebuah struk biasanya adalah "Total Belanja"
        nominal = max(parsed_numbers) if parsed_numbers else 0

        # 4. KEMBALIKAN KE FLUTTER DENGAN FORMAT YANG TEPAT
        return {
            "status": "success", 
            "nama_item": nama_item, 
            "nominal": nominal,
            "raw_text": extracted_text # Opsional, untuk debugging
        }
    except Exception as e:
        return {"status": "error", "message": f"Gagal memproses gambar: {str(e)}"}
    
class LaporanRequest(BaseModel):
        keterangan: str
        jumlah: int

# 2. Buat fungsi untuk menyimpan laporan ke Firebase
@router.post("/simpan-laporan")
async def simpan_laporan(request: LaporanRequest):
    try:
        # PYTHON YANG MELAKUKAN INPUT KE DATABASE
        db.collection('laporan').add({
            "kategori": "Pengeluaran",
            "keterangan": request.keterangan,
            "jumlah": request.jumlah,
            "tanggal": datetime.now()
        })
        
        # (Opsional) Python juga bisa otomatis mencatat ini ke log aktivitas
        db.collection('logs').add({
            "email": "Admin/Sistem", 
            "activity": f"Input Pengeluaran: {request.keterangan}",
            "timestamp": datetime.now(),
            "details": f"Nominal: Rp{request.jumlah}"
        })

        return {"status": "success", "message": "Laporan berhasil disimpan oleh Backend Python"}
    except Exception as e:
        return {"status": "error", "message": f"Gagal menyimpan di backend: {str(e)}"}
# ==============================================================================
# FITUR BERITA KAJIAN POPULER (AUTOMATED CRON JOB JAM 00:00 WIB)
# ==============================================================================

def run_auto_scraping():
    try:
        url = "https://www.republika.co.id/rss/khazanah"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, features="xml")

        items = soup.findAll('item')
        berita_list = []
        all_text_for_analysis = ""

        for item in items[:15]:
            title = item.title.text
            link = item.link.text
            pubDate = item.pubDate.text
            description = item.description.text

            clean_desc = re.sub('<[^<]+>', '', description)
            clean_title = re.sub(r'[^\w\s]', '', title).lower()
            all_text_for_analysis += clean_title + " "

            berita_list.append({
                "title": title,
                "link": link,
                "date": pubDate,
                "description": clean_desc.strip(),
                "views": random.randint(50, 1000)
            })

        words = all_text_for_analysis.split()
        stop_words = ['dan', 'di', 'yang', 'ke', 'dari', 'ini', 'untuk', 'pada', 'dengan', 'dalam', 'tentang']
        filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
        word_counts = Counter(filtered_words)

        trending_keywords = [word[0] for word in word_counts.most_common(3)]

        old_docs = db.collection('berita').stream()
        for doc in old_docs:
            doc.reference.delete()

        for b in berita_list:
            b['trending_tags'] = trending_keywords
            db.collection('berita').add(b)

        print(f"[{datetime.now()}] CRAWLING OTOMATIS BERHASIL. Trending Hari Ini: {trending_keywords}")
        return {"status": "success", "trending_topics": trending_keywords}
    except Exception as e:
        print(f"[{datetime.now()}] ERROR CRAWLING: {str(e)}")
        return {"status": "error", "message": str(e)}


# 2. Pengaturan Jadwal Otomatis (Cron Job)
scheduler = AsyncIOScheduler()

@router.on_event("startup")
async def start_scheduler():
    run_auto_scraping()

    scheduler.add_job(
        run_auto_scraping,
        'cron',
        hour=0,
        minute=0,
        timezone='Asia/Jakarta'
    )

    if not scheduler.running:
        scheduler.start()


# 3. Endpoint Get Berita untuk Flutter
@router.get("/berita-populer")
async def get_berita_populer():
    docs = db.collection('berita').order_by("views", direction="DESCENDING").stream()
    return [doc.to_dict() for doc in docs]
