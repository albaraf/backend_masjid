from firebase_config import db

def verify_admin(email, password):
    try:
        email_clean = email.strip().lower()
        users_ref = db.collection('users').where('email', '==', email_clean).get()

        if not users_ref:
            return False, "User tidak ditemukan"
        
        user_data = users_ref[0].to_dict()
        
        # Ambil password dari database dan dari input, ubah semua ke String
        # .strip() berguna untuk menghapus spasi di awal/akhir jika ada
        password_db = str(user_data.get('password', '')).strip()
        password_input = str(password).strip()

        print(f"DEBUG: Membandingkan '{password_input}' dengan '{password_db}'")

        if password_db == password_input:
            if user_data.get('role') == 'admin':
                return True, user_data
            else:
                return False, f"Akses ditolak! Role anda adalah {user_data.get('role')}"
        else:
            return False, "Password salah! Periksa kembali besar kecil hurufnya."

    except Exception as e:
        return False, f"Terjadi kesalahan: {str(e)}"