import bcrypt
from firebase_config import db

def create_admin():
    password = "admin123"
    # Melakukan hashing password agar aman di database
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    admin_data = {
        "name": "Administrator Utama",
        "email": "admin@gmail.com",
        "password": hashed_password.decode('utf-8'), # Menyimpan hasil hash berupa string
        "role": "admin",        # Syarat wajib agar bisa masuk dashboard
        "uid": "admin_manual_01"
    }

    # Simpan ke koleksi users di Firestore
    db.collection("users").document("admin_01").set(admin_data)
    print("✅ Akun Admin Aman berhasil dibuat!")
    print("Email: admin@gmail.com | Password Asli: admin123")

if __name__ == "__main__":
    create_admin()