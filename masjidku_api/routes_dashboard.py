from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from masjidku_api.firebase_config import db
from datetime import datetime
import bcrypt

router = APIRouter(tags=["Admin Monitoring"])

# ==========================================
# 1. HALAMAN LOGIN (GET)
# ==========================================
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    error_msg = f'<div class="alert alert-danger">{error}</div>' if error else ""
    
    return f"""
    <html>
    <head>
        <title>Login Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body style="background: #1a1a1a; display: flex; align-items: center; justify-content: center; height: 100vh;">
        <div class="card p-4 shadow" style="width: 350px; border-radius:15px;">
            <h4 class="text-center" style="color:#064635">Admin Login</h4>
            {error_msg}
            <form action="/login" method="post">
                <input type="email" name="email" class="form-control mb-3" placeholder="Email Admin" required>
                <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
                <button type="submit" class="btn w-100 text-white" style="background:#064635">MASUK SISTEM</button>
            </form>
        </div>
    </body>
    </html>
    """

# ==========================================
# 2. PROSES VALIDASI LOGIN (POST)
# ==========================================
@router.post("/login")
async def login_admin(
    request: Request, 
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        user_ref = db.collection("users").where("email", "==", email).limit(1).stream()
        user_data = None
        for doc in user_ref:
            user_data = doc.to_dict()

        if not user_data:
            return RedirectResponse(url="/login?error=Email tidak terdaftar!", status_code=303)

        hashed_password_db = user_data.get("password", "")

        if bcrypt.checkpw(password.encode('utf-8'), hashed_password_db.encode('utf-8')):
            if user_data.get("role") == "admin":
                return RedirectResponse(url="/dashboard", status_code=303)
            else:
                return RedirectResponse(url="/login?error=Anda bukan Admin!", status_code=303)
        else:
            return RedirectResponse(url="/login?error=Password salah!", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/login?error=Terjadi Kesalahan Server", status_code=303)

# ==========================================
# 3. HALAMAN DASHBOARD (GET)
# ==========================================
@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    users = [doc.to_dict() for doc in db.collection('users').stream()]
    logs = [doc.to_dict() for doc in db.collection('logs').order_by("timestamp", direction="DESCENDING").limit(10).stream()]
    
    donasi_stream = db.collection('donations').order_by("timestamp", direction="DESCENDING").stream()
    
    donasi_list = []
    for doc in donasi_stream:
        d_dict = doc.to_dict()
        d_dict['order_id'] = doc.id 
        donasi_list.append(d_dict)
        
    total_terkumpul = sum([int(d.get("amount", 0)) for d in donasi_list])
    
    html_content = f"""
    <html>
    <head>
        <title>Masjidku Pro Admin</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background: #f4f7f6; font-family: sans-serif; }}
            .nav-m {{ background: #064635; color: white; }}
            .card {{ border:none; border-radius:15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
            .log-container {{ height: 200px; overflow-y: auto; background: #212529; color: #00ff00; padding: 15px; border-radius: 10px; font-family: monospace; font-size: 13px; }}
            .log-item {{ border-bottom: 1px solid #333; padding: 5px 0; }}
        </style>
    </head>
    <body>
        <nav class="navbar nav-m p-3 shadow-sm"><div class="container d-flex justify-content-between"><b>🕌 MONITORING CENTER ADMIN</b><a href="/login" class="btn btn-danger btn-sm">Logout</a></div></nav>
        <div class="container mt-4">
            <div class="row">
                <div class="col-md-4">
                    <div class="card p-4 mb-3">
                        <h6 class="text-success">Input Petugas Jum'at</h6>
                        <form action="/add-announcement" method="post">
                            <input type="text" name="date" class="form-control mb-2" placeholder="Tanggal (e.g. 26 Juni)" required>
                            <input type="text" name="khatib" class="form-control mb-2" placeholder="Nama Khatib" required>
                            <input type="text" name="jabatan" class="form-control mb-2" placeholder="Gelar/Jabatan">
                            <button type="submit" class="btn btn-success btn-sm w-100">Update Petugas</button>
                        </form>
                    </div>
                    
                    <div class="card p-4 mb-3">
                        <h6 class="text-danger">Input Laporan Pengeluaran</h6>
                        
                        <div class="mb-3 p-2 border rounded bg-light">
                            <label class="form-label text-dark fw-bold" style="font-size: 12px;">📷 Scan Struk via Kamera HP</label>
                            <input type="file" id="cameraInput" accept="image/*" capture="environment" class="form-control form-control-sm">
                            <div id="ocrLoading" class="text-secondary mt-1" style="display:none; font-size:12px;">Menghubungi server OCR...</div>
                        </div>

                        <form action="/add-report" method="post">
                            <input type="text" id="reportJudul" name="judul" class="form-control mb-2" placeholder="Nama Pengeluaran" required>
                            <input type="number" id="reportNominal" name="nominal" class="form-control mb-2" placeholder="Nominal (Rp)" required>
                            
                            <textarea id="reportTeksAsli" name="teks_asli" class="form-control mb-2 text-dark" rows="4" style="font-size:12px; font-family:monospace;" placeholder="Teks asli struk akan muncul di sini..."></textarea>
                            
                            <button type="submit" class="btn btn-danger btn-sm w-100">Tambah Laporan</button>
                        </form>
                    </div>
                    
                    <div class="card p-4">
                        <h6 class="text-primary">Tambah Kegiatan</h6>
                        <form action="/add-activity" method="post">
                            <input type="text" name="title" class="form-control mb-2" placeholder="Judul Kegiatan" required>
                            <input type="text" name="time" class="form-control mb-2" placeholder="Waktu" required>
                            <textarea name="description" class="form-control mb-2" placeholder="Deskripsi Singkat" rows="2"></textarea>
                            <input type="text" name="imageUrl" class="form-control mb-3" placeholder="Link Gambar (URL)" required>
                            <button type="submit" class="btn btn-primary btn-sm w-100">Tambah Kegiatan</button>
                        </form>
                    </div>
                </div>

                <div class="col-md-8">
                    <div class="card p-4 mb-3">
                        <h6>Daftar Jamaah Terdaftar ({len(users)})</h6>
                        <div style="height: 150px; overflow-y: auto;">
                            <table class="table table-sm">
                                <thead><tr><th>Nama</th><th>Email</th><th>Role</th></tr></thead>
                                <tbody>{"".join([f"<tr><td>{u.get('name')}</td><td>{u.get('email')}</td><td><span class='badge bg-secondary'>{u.get('role')}</span></td></tr>" for u in users])}</tbody>
                            </table>
                        </div>
                    </div>
                    
                    <div class="card p-4 mb-3" style="border-left: 4px solid #064635;">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="text-success m-0"><b>Riwayat Donasi Masuk</b></h6>
                            <span class="badge bg-success" style="font-size: 14px;">Total: Rp {total_terkumpul:,}</span>
                        </div>
                        <div style="height: 150px; overflow-y: auto;">
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Order ID</th>
                                        <th>Email Jamaah</th>
                                        <th>Nominal</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {"".join([f"<tr><td><small style='color:gray;'>{d.get('order_id')}</small></td><td>{d.get('user_id')}</td><td><b>Rp {int(d.get('amount', 0)):,}</b></td><td><span class='badge bg-warning text-dark'>{d.get('status')}</span></td></tr>" for d in donasi_list]) if donasi_list else "<tr><td colspan='4' class='text-center text-muted'>Belum ada data donasi masuk...</td></tr>"}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <div class="card p-4">
                        <h6 class="text-dark">Live Activity Logs (Login/Register/Pass)</h6>
                        <div class="log-container">
                            {"".join([f'''
                                <div class="log-item">
                                    <span style="color: #888;">[{l.get('timestamp').strftime('%H:%M:%S') if l.get('timestamp') else 'Waktu Tidak Diketahui'}]</span> 
                                    <b style="color: #ffc107;">{l.get('email')}</b> 
                                    <span>{l.get('activity')}</span>
                                </div>
                            ''' for l in logs]) if logs else "Belum ada aktivitas terekam..."}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            document.getElementById('cameraInput').addEventListener('change', async function(e) {{
                const file = e.target.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('file', file);

                const loading = document.getElementById('ocrLoading');
                loading.style.display = 'block';
                loading.className = 'text-warning mt-1';
                loading.innerText = 'Sedang memproses gambar struk...';

                try {{
                    const response = await fetch('/api/scan-struk', {{
                        method: 'POST',
                        body: formData
                    }});
                    const result = await response.json();
                    
                    if (result.status === 'success' || response.ok) {{
                        loading.className = 'text-success mt-1';
                        loading.innerText = 'Scan selesai!';
                        
                        // FIX UTAMA: Menyesuaikan pembacaan key 'raw_text' dan 'nama_item' sesuai API Python Anda
                        let ocrText = result.raw_text || result.extracted_text || result.text || "";
                        let namaItem = result.nama_item || "";
                        let nominalUang = result.nominal || 0;
                        
                        // Jika Tesseract berhasil membaca kata yang valid (bukan sekadar simbol acak pendek)
                        if (ocrText && ocrText.trim().length > 4) {{
                            document.getElementById('reportTeksAsli').value = ocrText;
                            document.getElementById('reportJudul').value = namaItem || ocrText.substring(0, 30).replace(/\\n/g, ' ').trim();
                            document.getElementById('reportNominal').value = nominalUang || 0;
                        }} else {{
                            // Fallback pintar jika foto terlalu buram/Tesseract gagal membaca objek kertas
                            document.getElementById('reportTeksAsli').value = "Hasil Scan Nota Mentah:\\n[Teks struk buram / tidak terdeteksi otomatis oleh mesin].\\n\\nSilakan tulis atau edit ringkasan nota asli di sini secara manual.";
                            document.getElementById('reportJudul').value = namaItem && namaItem !== "ie," ? namaItem : "Pembelian Perlengkapan";
                            document.getElementById('reportNominal').value = nominalUang || 0;
                        }}
                    }} else {{
                        loading.className = 'text-danger mt-1';
                        loading.innerText = 'Gagal: ' + (result.message || 'Respons server tidak valid');
                    }}
                }} catch (err) {{
                    loading.className = 'text-danger mt-1';
                    loading.innerText = 'Gagal terhubung ke server OCR.';
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# ==========================================
# 4. ENDPOINT TAMBAH DATA (POST)
# ==========================================
@router.post("/add-announcement")
async def add_announcement(date: str = Form(...), khatib: str = Form(...), jabatan: str = Form(""), avatarUrl: str = Form("")):
    db.collection('announcements').add({
        "date": date, "khatib": khatib, "jabatan": jabatan,
        "avatarUrl": avatarUrl or f"https://ui-avatars.com/api/?name={khatib}&background=random"
    })
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/add-activity")
async def add_activity(title: str = Form(...), time: str = Form(...), description: str = Form(""), imageUrl: str = Form(...)):
    db.collection('activities').add({"title": title, "time": time, "description": description, "imageUrl": imageUrl})
    return RedirectResponse(url="/dashboard", status_code=303)

@router.post("/add-report")
async def add_report(judul: str = Form(...), nominal: int = Form(...), teks_asli: str = Form("")):
    db.collection('laporan').add({
        "kategori": "Pengeluaran",
        "keterangan": judul,
        "jumlah": nominal,
        "tanggal": datetime.now(),
        "teks_asli_struk": teks_asli
    })
    db.collection('logs').add({
        "email": "Admin Web",
        "activity": f"Laporan Pengeluaran: {judul} (Rp {nominal:,})",
        "timestamp": datetime.now()
    })
    return RedirectResponse(url="/dashboard", status_code=303)
