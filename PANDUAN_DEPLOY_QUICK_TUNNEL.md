# 🚀 Panduan Demonstrasi & Deploy: Lapor SAR Lite dengan Cloudflare Quick Tunnel

Panduan ini dirancang untuk insinyur sistem dan pengembang yang akan melakukan **demonstrasi langsung (*pitching / live demo*)** sistem **Lapor SAR** di hadapan calon mitra, pejabat instansi (BASARNAS / Kantor SAR Daerah), maupun pemangku kepentingan.

Dengan arsitektur **Lapor SAR Lite**:
- **Beban RAM Hemat:** Hanya membutuhkan **~1.5 - 2 GB RAM** (laptop presentasi tetap hening dan dingin).
- **Latensi Instan:** Transkripsi suara darurat selesai dalam **< 1 detik** menggunakan Cloud AI (Groq Whisper / OpenAI).
- **Zero Configuration Port:** Tidak perlu IP publik, router port forwarding, atau konfigurasi firewall kantor.
- **Akses Langsung HP Penguji:** Calon mitra cukup memindai QR Code untuk membuka portal darurat di smartphone mereka.

---

## 🏗️ 1. Arsitektur Demo Quick Tunnel

```
[ Smartphone Audiens / Penguji ]
              │
              ▼ (HTTPS Publik Gratis: https://xxxx.trycloudflare.com)
┌─────────────────────────────────────────────────────────────┐
│                 CLOUDFLARE EDGE NETWORK                     │
│  - Sertifikat SSL Otomatis & Terenkripsi                    │
│  - Proteksi Jaringan Tanpa Buka Port Masuk (Zero Exposure)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Terowongan Keluar (Outbound QUIC)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             LAPTOP / SERVER LOKAL PRESENTASI                │
│                                                             │
│  [ cloudflared daemon ] ─── Meneruskan ke Port 3000         │
│             │                                               │
│             ▼                                               │
│     Frontend (Next.js 16) ─── Port 3000                     │
│     - Halaman Pelapor Mobile (PWA)                          │
│     - Dashboard Operator & Peta Spasial SAR                 │
│     - Manajemen Berkas & Audio Player (/storage)            │
│             │ (Proxy internal /api/*)                       │
│             ▼                                               │
│     Backend (FastAPI)    ─── Port 8000                      │
│             │                                               │
│      ┌──────┴───────────────────────┐                       │
│      ▼                              ▼                       │
│  PostGIS & pgvector Database     Redis                      │
│  (Database Spasial & Vektor)     (Cache Cepat)              │
│                                                             │
│  Layanan AI Luar (Cloud API):                               │
│  - Groq Whisper Large V3 (Voice Note Transkripsi < 1s)      │
│  - Google Gemini 1.5 Flash / Groq Llama 3.3 (Ekstraksi SAR) │
│  - Gemini text-embedding-004 (Vektorisasi Kamus Semantik)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 2. Prasyarat Sistem

1. **Sistem Operasi:** Windows 10/11, macOS, atau Linux (Ubuntu/Debian).
2. **Perangkat Lunak:**
   - **Docker Desktop** (atau Docker Engine + Docker Compose).
   - **Cloudflared CLI** (Binary terowongan resmi dari Cloudflare).

### Cara Pasang `cloudflared` (Jika Belum Terpasang):

- **Windows (via Winget di PowerShell):**
  ```powershell
  winget install Cloudflare.cloudflared
  ```
  *Atau unduh file `.exe` langsung dari: [Cloudflare GitHub Releases](https://github.com/cloudflare/cloudflared/releases/latest)* dan letakkan di folder sistem atau di dalam folder `Lapor SAR Lite`.

- **Linux (Ubuntu / Debian):**
  ```bash
  curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
  sudo dpkg -i cloudflared.deb
  ```

- **macOS:**
  ```bash
  brew install cloudflared
  ```

---

## ⚙️ 3. Konfigurasi Kunci API (.env)

Buka berkas `.env` di dalam folder `Lapor SAR Lite`:

```env
# Masukkan API Key Groq untuk transkripsi suara instan (< 1 detik)
AI_STT_PROVIDER=groq
AI_STT_MODEL=whisper-large-v3
AI_STT_API_KEY=gsk_MASUKKAN_API_KEY_GROQ_ANDA

# Masukkan API Key Gemini untuk ekstraksi entitas SAR
AI_LLM_PROVIDER=gemini
AI_LLM_MODEL=gemini-1.5-flash
AI_LLM_API_KEY=AIzaSy_MASUKKAN_API_KEY_GEMINI_ANDA

# Masukkan API Key Embedding untuk Kamus Semantik & RAG (pgvector)
AI_EMBED_PROVIDER=gemini
AI_EMBED_MODEL=text-embedding-004
AI_EMBED_API_KEY=AIzaSy_MASUKKAN_API_KEY_GEMINI_ANDA
```

*(Tips: Dapatkan API Key Groq gratis di [console.groq.com](https://console.groq.com) dan Gemini di [aistudio.google.com](https://aistudio.google.com)).*

---

## 🚀 4. Menjalankan Demo (Cara 1-Klik / Otomatis di Windows)

Jika Anda menggunakan Windows, cukup **klik dua kali** berkas:
```text
start_demo.bat
```
Skrip ini akan secara otomatis:
1. Memeriksa ketersediaan Docker dan Cloudflared.
2. Menjalankan 4 kontainer esensial (`db`, `redis`, `backend`, `frontend`).
3. Membuka Cloudflare Quick Tunnel ke `http://localhost:3000`.
4. Menampilkan tautan publik `https://*.trycloudflare.com` di layar terminal Anda.

---

## 🛠️ 5. Menjalankan Demo (Cara Manual via Terminal)

### Langkah 5.1: Jalankan Kontainer Docker
Buka Terminal/PowerShell di folder `Lapor SAR Lite`:
```bash
docker compose up -d
```
Pastikan seluruh kontainer berstatus sehat (*healthy*):
```bash
docker compose ps
```
Hasil:
- `laporsar_lite_db` (Port 5432) — Up (healthy)
- `laporsar_lite_redis` (Port 6379) — Up (healthy)
- `laporsar_lite_backend` (Port 8000) — Up (healthy)
- `laporsar_lite_frontend` (Port 3000) — Up

### Langkah 5.2: Buka Terowongan Cloudflare Quick Tunnel
Jalankan perintah berikut di terminal:
```bash
cloudflared tunnel --url http://localhost:3000
```
Tunggu sekitar 3–5 detik, Anda akan melihat output URL publik seperti berikut:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://emergency-response-sar.trycloudflare.com                                          |
+--------------------------------------------------------------------------------------------+
```
Salin URL tersebut (`https://...trycloudflare.com`). **Sistem Anda kini sudah online di seluruh dunia dengan HTTPS resmi!**

---

## 🎯 6. Skenario Uji Coba Saat Presentasi (Pitching Flow)

Untuk memukau audiens dalam presentasi, jalankan skenario berikut:

### Skenario 1: Demonstrasi Akses Smartphone Audiens
1. Tampilkan layar proyektor ke halaman beranda (`https://...trycloudflare.com`).
2. Minta salah satu penguji/calon mitra untuk **mengaktifkan kamera HP-nya** dan **memindai QR Code** yang ada di bagian bawah halaman.
3. Halaman pelaporan mobile akan langsung terbuka di browser ponsel mereka tanpa perlu mengunduh aplikasi apa pun.

### Skenario 2: Simulasi Laporan Suara (Voice Note Transkripsi)
1. Di ponsel penguji, klik menu **Lapor Kejadian**.
2. Tekan tombol mikrofon dan rekam suara kondisi darurat:
   > *"Lapor SAR, ada perahu nelayan mati mesin di perairan Natuna koordinat 03 derajat 55 menit Lintang Utara 108 derajat 23 menit Bujur Timur. Terdapat 3 orang nelayan di atas kapal, butuh evakuasi segera."*
3. Kirim pesan suara tersebut.
4. **Perhatikan waktu respon:** Dalam hitungan **< 1 detik**, Groq Whisper akan mentranskripsi suara ke teks bahasa Indonesia dengan presisi tinggi, dan mesin AI otomatis mengisi kolom lokasi, jumlah korban, serta jenis musibah.

### Skenario 3: Verifikasi di Dashboard Operator (Pusat Komando)
1. Di laptop presenter, buka tab **Dashboard Operator** (`/reports` atau `/`).
2. Login dengan akun demo:
   - **Username:** `admin`
   - **Password:** `admin`
3. Laporan yang baru saja dikirim dari smartphone penguji langsung muncul secara *real-time*.
4. Operator dapat melihat titik koordinat di peta Leaflet/OpenStreetMap dan mengubah status menjadi **Terverifikasi / Proses SAR**.

### Skenario 4: Pemutaran Rekaman Suara di Dashboard (/storage)
1. Buka menu **Penyimpanan Berkas** (`/storage`) di sidebar kiri.
2. Tunjukkan statistik penggunaan disk lokal server (misal: 15 MB terpakai dari sisa 80 GB disk).
3. Klik tombol **Play** pada berkas audio laporan tadi untuk memutar rekaman suara pelapor langsung melalui browser laptop.
4. Setelah demo selesai, klik tombol **"Reset Berkas Demo"** untuk mengembalikan penyimpanan ke kondisi bersih.

### Skenario 5: Eksplorasi Kamus Semantik & Vektor AI (/knowledge)
1. Buka menu **Kamus Istilah** (`/knowledge`) di panel kiri.
2. Ketik kata atau konsep dalam kotak **Pencarian Semantik AI** (contoh: *"perahu kecil nelayan"*).
3. Tunjukkan kepada audiens bagaimana sistem berbasis **pgvector** menemukan istilah lokal terkait (seperti *"pompong"*, *"kelotok"*, *"jukung"*) lengkap dengan skor jarak semantiknya (*cosine distance*).
4. Tunjukkan tombol **"Vektorisasi Semua Istilah"** untuk mendemonstrasikan kapabilitas sinkronisasi embedding RAG lokal ke database.

---

## 🔄 7. Menguji Perbandingan Provider AI (Benchmarking)

Jika calon mitra bertanya *"Bagaimana jika instansi kami ingin memakai OpenAI atau Groq saja?"*, Anda bisa langsung mendemonstrasikan fleksibilitas sistem ini:

1. Buka berkas `.env`.
2. Ubah `AI_LLM_PROVIDER` dari `gemini` ke `groq` atau `openai`.
3. Restart kontainer backend:
   ```bash
   docker compose restart backend
   ```
4. Sistem akan langsung menggunakan provider baru tanpa perlu kompilasi ulang kode.

---

## 🛑 8. Menghentikan Demo

Jika presentasi telah selesai:
1. Tekan `Ctrl + C` pada jendela terminal `cloudflared`.
2. Hentikan kontainer Docker:
   ```bash
   docker compose down
   ```
   *(Data database dan file demo akan tetap tersimpan aman di volume Docker lokal).*
