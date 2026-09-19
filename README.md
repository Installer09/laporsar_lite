# Lapor SAR Lite (Prototype Edition)

> **Sistem Informasi & Pelaporan Darurat Pencarian dan Pertolongan (SAR)**  
> Edisi prototipe ringan untuk demonstrasi (*pitching*), evaluasi instansi, dan penyebaran cepat (*quick deployment*).

---

## 🌟 Ikhtisar

**Lapor SAR Lite** adalah varian mandiri dari sistem Lapor SAR yang dioptimalkan untuk kebutuhan demonstrasi dan lingkungan server berspesifikasi hemat:
- **Beban RAM Hemat:** Hanya membutuhkan **~1.5 - 2 GB RAM** (mengeliminasi Ollama Llama 3.1 & Whisper lokal kontainer).
- **Transkripsi Sub-Detik:** Menggunakan **Cloud STT (Groq Whisper Large V3)** dengan latensi **< 1 detik**.
- **Multi-Provider AI Switchable:** Dukungan penuh untuk Google Gemini 1.5 Flash, Groq Llama 3.3, dan OpenAI GPT-4o-mini cukup dengan mengubah konfigurasi `.env`.
- **Penyimpanan Lokal & Media Manager UI:** Pengganti MinIO berbasis sistem berkas lokal (`./uploads`) yang dilengkapi antarmuka pemutar rekaman suara (*audio player*) dan penampil foto musibah di `/storage`.
- **Web Mobile-First (PWA):** Pengganti aplikasi Flutter berbasis web responsif yang dapat langsung diakses via pemindaian QR Code di layar presentasi.
- **Single Entrypoint Cloudflare Tunnel:** Proxy terpadu via Next.js sehingga hanya membutuhkan 1 URL publik (`https://*.trycloudflare.com`).

---

## 🏗️ Arsitektur Layanan

```
[ Pelapor (HP / Browser) ]          [ Operator SAR (Laptop) ]
             │                                   │
             └─────────────────┬─────────────────┘
                               │
            ┌──────────────────▼──────────────────┐
            │   CLOUDFLARE QUICK TUNNEL / NGINX   │
            └──────────────────┬──────────────────┘
                               │
            ┌──────────────────▼──────────────────┐
            │       Next.js 14 Frontend           │
            │   (Port 3000 / Web Mobile & UI)     │
            └──────────────────┬──────────────────┘
                               │ (Proxy rewrite /api/*)
            ┌──────────────────▼──────────────────┐
            │       FastAPI Backend Core          │
            │   (Port 8000 / REST & AI Router)    │
            └─────────┬──────────────┬────────────┘
                      │              │
        ┌─────────────▼────┐   ┌─────▼──────────────┐
        │  PostGIS 16 DB   │   │   Redis 7 Cache    │
        │  (Data Spasial)  │   │   (Status Sesi)    │
        └──────────────────┘   └────────────────────┘
                      │
        ┌─────────────▼─────────────────────────────┐
        │        Layanan Cloud AI (Pihak Ke-3)       │
        │  - Groq Whisper (Transkripsi Suara)       │
        │  - Google Gemini Flash / OpenAI LLM       │
        └───────────────────────────────────────────┘
```

---

## 🚀 Memulai Cepat (Quick Start)

### 1. Salin Konfigurasi Environment
```bash
cp .env.example .env
```
Sunting `.env` dan masukkan API Key AI Anda (contoh: Groq atau Gemini).

### 2. Jalankan Kontainer Docker
```bash
docker compose up -d
```

### 3. Jalankan Terowongan Publik Cloudflare (Opsional untuk Demo)
- **Windows:** Klik dua kali berkas `start_demo.bat`.
- **Manual CLI:**
  ```bash
  cloudflared tunnel --url http://localhost:3000
  ```

### 4. Akun Default Operator
- **URL Dashboard:** `http://localhost:3000` (atau URL Cloudflare Anda)
- **Username:** `admin`
- **Password:** `admin`

---

## 📁 Struktur Direktori

- `backend/` : Aplikasi FastAPI, model database, ekstraktor entitas SAR, dan routing API.
- `frontend/` : Aplikasi Next.js 14 (App Router), dashboard operator, peta spasial Leaflet, dan media manager.
- `docker-compose.yml` : Konfigurasi orkestrasi 4 kontainer utama (`db`, `redis`, `backend`, `frontend`).
- `PANDUAN_DEPLOY_QUICK_TUNNEL.md` : Panduan skenario demonstrasi menggunakan Cloudflare Quick Tunnel.
- `PANDUAN_DEPLOY_DEBIAN_SERVER.md` : Panduan instalasi dan deployment pada server Linux Debian (VPS/Baremetal).
- `start_demo.bat` : Skrip peluncur otomatis 1-klik untuk sistem operasi Windows.

---

## 📄 Lisensi
Hak Cipta © 2026 Tim Pengembang Digitalisasi Lapor SAR.
