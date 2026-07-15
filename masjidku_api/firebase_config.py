import firebase_admin
from firebase_admin import credentials, firestore

def initialize_db():
    try:
        # Inisialisasi hanya jika belum ada app yang berjalan
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"CRITICAL ERROR: File serviceAccountKey.json tidak ditemukan atau rusak! {e}")
        return None

# Variabel db ini yang akan di-import oleh file lain
db = initialize_db()