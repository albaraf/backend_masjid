import webbrowser
from threading import Timer
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from masjidku_api import routes_api
from masjidku_api import routes_dashboard  # (Jika ada)

app = FastAPI(title="Masjidku Pro Modular Backend")

# Pengaturan CORS agar Flutter Web bisa akses
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Izinkan semua origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MENGGABUNGKAN SEMUA ROUTER ---
# Tambahkan prefix="/api" di parameter routes_api.router
app.include_router(routes_api.router, prefix="/api")
app.include_router(routes_dashboard.router)

@app.get("/")
def welcome():
    return {
        "message": "Server Masjidku Pro Aktif",
        "endpoints": {
            "dashboard": "/dashboard",
            "api_users": "/api/users",
            "api_docs": "/docs"
        }
    }

# --- OTOMATIS BUKA CHROME ---
def open_browser():
    webbrowser.open("http://127.0.0.1:8000/login")

if __name__ == "__main__":
    # Jalankan timer untuk buka browser setelah 1.5 detik
    Timer(1.5, open_browser).start()
    
    # Jalankan server uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)