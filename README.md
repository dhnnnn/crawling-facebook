# 🚀 Multi-Platform Social Media Crawler

Proyek ini adalah backend API berbasis **FastAPI** yang dirancang untuk melakukan crawling data (komentar dan hashtag) dari berbagai platform media sosial seperti **Facebook**, **Instagram**, dan **TikTok** menggunakan **Playwright**.

## ✨ Fitur Utama

- **Multi-Platform Support**: Crawling data dari Facebook, Instagram, dan TikTok dalam satu aplikasi.
- **Comment Extraction**: Mengambil komentar dari postingan secara otomatis.
- **Hashtag Extraction**: Mengambil postingan berdasarkan hashtag tertentu (khusus Instagram).
- **Automated Cookie Management**: Mendukung login manual pertama kali dan menyimpan cookies untuk penggunaan berikutnya agar terhindar dari login berulang.
- **Smart Scrolling**: Simulasi pergerakan manusia dengan scrolling otomatis untuk memuat lebih banyak komentar.
- **Structured Data**: Hasil crawling disimpan dalam format JSON yang rapi dan terorganisir.
- **API Secured**: Dilindungi dengan API Key untuk akses yang aman.

## 📂 Struktur Proyek

```text
Crawling-medsos/
├── backend/                # Source code backend (FastAPI)
│   ├── app/                # Aplikasi utama
│   │   ├── api/            # Routes & endpoints API
│   │   ├── crawlers/       # Logika crawling per platform
│   │   ├── models/         # Pydantic schemas
│   │   └── services/       # Business logic
│   ├── .env                # Konfigurasi environment (Private)
│   ├── main.py             # Entry point aplikasi
│   └── requirements.txt    # Daftar dependensi Python
├── data/                   # Penyimpanan hasil crawling & cookies
│   ├── cookies/            # File JSON cookies per platform
│   └── crawling/           # Hasil crawl (Facebook, Instagram, TikTok)
│       ├── facebook/
│       ├── instagram/
│       └── tiktok/
└── .gitignore              # Daftar file yang diabaikan oleh Git
```

## 🛠️ Persiapan & Instalasi

### Prasyarat

- Python 3.8 ke atas
- Pip (Python Package Manager)

### Langkah-langkah

1. **Clone Repositori**

   ```bash
   git clone <url-repository-ini>
   cd Crawling-medsos
   ```

2. **Buat Virtual Environment (Opsional tapi Direkomendasikan)**

   ```bash
   python -m venv venv
   # Aktifkan venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **Instal Dependensi**

   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Instal Browser Playwright**

   ```bash
   playwright install chromium
   ```

5. **Konfigurasi Environment**
   Salin file `.env.example` menjadi `.env` di dalam folder `backend/`:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Buka file `.env` dan sesuaikan pengaturannya (seperti `API_KEY` dan `HEADLESS`).

## ⚙️ Konfigurasi (.env)

| Variabel      | Deskripsi                                                             | Default                   |
| ------------- | --------------------------------------------------------------------- | ------------------------- |
| `API_KEY`     | Key untuk mengakses API via header `X-API-Key`                        | `crawler_secret_key_2026` |
| `HEADLESS`    | `true` untuk lari di background, `false` untuk melihat proses browser | `false`                   |
| `MIN_DELAY`   | Delay minimal antar aksi (detik)                                      | `2`                       |
| `MAX_DELAY`   | Delay maksimal antar aksi (detik)                                     | `5`                       |
| `COOKIES_DIR` | Lokasi penyimpanan cookies                                            | `../data/cookies`         |

## 🚀 Cara Menjalankan

Jalankan server aplikasi menggunakan Uvicorn:

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Aplikasi akan berjalan di `http://localhost:8000`.

## 📖 Dokumentasi API

Setelah aplikasi berjalan, Anda dapat mengakses dokumentasi interaktif (Swagger UI) di:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

### Endpoints Utama

- **Facebook**:
  - `POST /api/facebook/crawl-comments`: Mengambil komentar dari URL postingan Facebook.
- **Instagram**:
  - `POST /api/instagram/crawl-comments`: Mengambil komentar dari URL postingan Instagram.
  - `POST /api/instagram/crawl-hashtag`: Mengambil data dari hashtag tertentu.
- **TikTok**:
  - `POST /api/tiktok/crawl-comments`: Mengambil komentar dari URL video TikTok.
- **Results**:
  - `GET /api/results`: Melihat daftar hasil crawling yang tersimpan.

> **Catatan**: Gunakan header `X-API-Key` untuk setiap request jika security diaktifkan.

## 📊 Struktur Penyimpanan Data

Hasil crawling akan disimpan secara otomatis di folder `data/crawling/` dengan format file:
`data/crawling/{platform}/comment/{timestamp}_{short_url}.json`

Isi file JSON mencakup:

- Metadata postingan (URL, waktu crawl)
- Statistik (Like, jumlah komentar)
- **Data Komentar**: Username, isi komentar, waktu, dan jumlah like per komentar.

## ⚠️ Catatan Penting

1. **Login Manual**: Saat pertama kali menjalankan crawler untuk platform tertentu, jika browser terbuka (`HEADLESS=false`), silakan lakukan login secara manual jika diminta. Cookies akan disimpan secara otomatis sehingga tidak perlu login lagi di kemudian hari.
2. **Keamanan**: Hindari melakukan crawling terlalu cepat atau terlalu banyak untuk mencegah akun terkena pemblokiran/suspend dari platform media sosial. Gunakan delay yang wajar.
3. **Kepatuhan**: Pastikan penggunaan alat ini mematuhi Ketentuan Layanan (Terms of Service) dari masing-masing platform.

---

Dibuat dengan ❤️ untuk kemudahan analisis data media sosial.
