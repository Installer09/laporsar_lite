# 🐧 Panduan Produksi & Self-Host: Lapor SAR Lite di Server Debian (Debian 11 / 12)
### *Standar Operasional SysAdmin: Zero Port Exposure, Cloudflare Tunnel Daemon, & Docker Isolation*

Panduan ini disusun secara komprehensif untuk memandu insinyur sistem dan administrator IT menerapkan sistem **Lapor SAR Lite** pada server berbasis **Debian GNU/Linux (Debian 11 Bullseye atau Debian 12 Bookworm)**, baik di server fisik lokal (*on-premise / bare-metal*) maupun VPS Cloud (Linode, DigitalOcean, IDCloudHost, Biznet Gio, AWS, GCP, dll).

Karena varian **Lapor SAR Lite** telah dioptimalkan dengan mengalihkan komputasi AI berat ke Cloud API:
- **Kebutuhan RAM:** Cukup **2 GB RAM** (disarankan paket 2 vCPU / 2GB atau 4GB RAM agar proses build kontainer sangat leluasa).
- **Kebutuhan Disk:** Minimal **25 GB SSD/NVMe**.
- **Koneksi:** Cukup akses internet *outbound* (tidak wajib IP Publik Statis jika menggunakan Cloudflare Tunnel).

---

## 📋 DAFTAR ISI

0. [Pra-syarat & Persiapan Akun Eksternal (Sebelum Mulai)](#0-pra-syarat--persiapan-akun-eksternal-sebelum-mulai)
1. [Persiapan Sistem Operasi Debian](#1-persiapan-sistem-operasi-debian)
2. [Instalasi Docker Engine & Docker Compose Resmi](#2-instalasi-docker-engine--docker-compose-resmi)
3. [Kloning Repositori & Konfigurasi Berkas .env](#3-kloning-repositori--konfigurasi-berkas-env)
4. [Menjalankan Layanan Lapor SAR Lite](#4-menjalankan-layanan-lapor-sar-lite)
5. [Pilihan Akses Publik: Cloudflare Tunnel & Zero Trust (Direkomendasikan)](#5-pilihan-akses-publik-cloudflare-tunnel--zero-trust-direkomendasikan)
6. [Pilihan Alternatif: Nginx Reverse Proxy + SSL Let's Encrypt](#6-pilihan-alternatif-nginx-reverse-proxy--ssl-lets-encrypt)
7. [Pengerasan Keamanan Firewall (UFW)](#7-pengerasan-keamanan-firewall-ufw)
8. [Verifikasi & Uji Coba Operasional End-to-End](#8-verifikasi--uji-coba-operasional-end-to-end)
9. [Perawatan Rutin, Pemantauan, & Pencadangan](#9-perawatan-rutin-pemantauan--pencadangan)

---

## 0. Pra-syarat & Persiapan Akun Eksternal (Sebelum Mulai)

Sebelum melakukan instalasi pada server, siapkan kunci API dan akun eksternal berikut. Seluruh provider AI ini menyediakan tier gratis (*free tier*):

### 0.1 Mendapatkan API Key Groq (Whisper STT Sub-detik)
Digunakan untuk transkripsi rekaman suara laporan darurat (*voice note to text*) dengan model Whisper Large V3 secara instan (< 1 detik).
1. Buka portal [console.groq.com](https://console.groq.com) lalu daftar/masuk dengan akun Google atau GitHub.
2. Pada navigasi kiri, buka menu **API Keys**.
3. Klik tombol **Create API Key**.
4. Beri nama (misal: `laporsar-whisper`), lalu klik **Submit**.
5. Salin dan simpan token API yang dihasilkan (berawalan `gsk_...`).

### 0.2 Mendapatkan API Key Google Gemini (LLM & Embeddings)
Digunakan untuk pemahaman bahasa laporan darurat (*Natural Language Processing*) dan ekstraksi data spasial (koordinat, jumlah korban, jenis musibah).
1. Buka [aistudio.google.com](https://aistudio.google.com) lalu masuk dengan akun Google.
2. Klik tombol **Get API Key** di panel sebelah kiri.
3. Klik **Create API key** (pilih project Google Cloud bawaan atau buat otomatis).
4. Salin dan simpan token API yang dihasilkan (berawalan `AIzaSy...`).

### 0.3 Menyiapkan Nama Domain & Cloudflare (Untuk Named Tunnel)
Fitur peramban (*browser*) modern mewajibkan protokol **HTTPS** agar izin **Mikrofon** dan **Geolokasi GPS** pelapor dapat berfungsi.
1. Siapkan domain milik kantor SAR/organisasi Anda (misal: `laporsar.id` atau subdomain `sar-daerah.go.id`) dari registrar domain Anda.
2. Buat akun gratis di [cloudflare.com](https://dash.cloudflare.com).
3. Klik **Add a Domain / Add a Site**, masukkan nama domain Anda, lalu pilih paket **Free**.
4. Ubah *Nameservers* di panel registrar domain Anda sesuai yang diarahkan Cloudflare (misal: `dina.ns.cloudflare.com` & `noah.ns.cloudflare.com`). Tunggu hingga status domain menjadi *Active*.

### 0.4 (Opsional) Menyiapkan Bot Telegram untuk Siaga SAR
Jika Anda ingin sistem otomatis mengirimkan lembar disposisi darurat ke grup koordinasi tim penolong:
1. Buka aplikasi Telegram, cari akun resmi `@BotFather`.
2. Kirim perintah `/newbot`, lalu ikuti instruksi (masukkan nama tampilan dan username unik berakhiran `_bot`).
3. Catat **HTTP API Token** yang diberikan (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
4. Buat grup Telegram baru (misal: `Siaga Darurat SAR`) dan tambahkan bot yang baru dibuat ke dalam grup sebagai Administrator.
5. Dapatkan **Chat ID Grup**:
   - Kirim satu pesan ke dalam grup tersebut (misal: "Test Bot").
   - Buka URL ini di browser: `https://api.telegram.org/bot<TOKEN_BOT_ANDA>/getUpdates`
   - Cari bagian `"chat":{"id": -100xxxxxxxxxx}`. Salin angka tersebut (biasanya diawali dengan tanda minus `-`).

---

## 1. Persiapan Sistem Operasi Debian

Hubungkan ke server Debian Anda melalui SSH:
```bash
ssh root@IP_SERVER_DEBIAN_ANDA
```

### 1.1 Perbarui Indeks Paket
```bash
apt update && apt upgrade -y
```

### 1.2 Atur Zona Waktu Server ke Waktu Indonesia Barat (WIB)
Sinkronisasi waktu audit log SAR sangat penting:
```bash
timedatectl set-timezone Asia/Jakarta
timedatectl
```

### 1.3 Pasang Paket Utilitas Dasar
```bash
apt install -y curl wget git htop ufw ca-certificates gnupg lsb-release
```

---

## 2. Instalasi Docker Engine & Docker Compose Resmi

Gunakan repositori resmi Docker (hindari paket docker Debian bawaan yang versinya tertinggal).

### 2.1 Tambahkan GPG Key Resmi Docker
```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
```

### 2.2 Daftarkan Repositori Docker ke APT
```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### 2.3 Pasang Docker Engine & Plugin Docker Compose
```bash
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2.4 Pastikan Docker Aktif Saat Server Booting
```bash
systemctl enable --now docker
docker --version
docker compose version
```

---

## 3. Kloning Repositori & Konfigurasi Berkas .env

### 3.1 Kloning Kode Proyek
Letakkan proyek di direktori `/opt/laporsar_lite`:
```bash
git clone https://github.com/Installer09/laporsar_lite.git /opt/laporsar_lite
cd /opt/laporsar_lite
```

### 3.2 Buat dan Sesuaikan Berkas `.env`
Salin template konfigurasi:
```bash
cp .env.example .env
nano .env
```

Lakukan penyesuaian pada bagian-bagian berikut:

```env
# 1. Kunci Rahasia JWT (Ganti dengan string acak minimal 32 karakter untuk produksi)
SECRET_KEY=kombinasi_acak_rahasia_dan_panjang_untuk_keamanan_jwt_sar

# 2. Kata Sandi Default Akun Admin
DEV_ADMIN_USERNAME=admin
DEV_ADMIN_PASSWORD=ganti_password_admin_yang_kuat

# 3. Kunci API AI Cloud (Gunakan kunci yang didapat pada Langkah 0)
AI_STT_PROVIDER=groq
AI_STT_MODEL=whisper-large-v3
AI_STT_API_KEY=gsk_MASUKKAN_API_KEY_GROQ_ANDA

AI_LLM_PROVIDER=gemini
AI_LLM_MODEL=gemini-1.5-flash
AI_LLM_API_KEY=AIzaSy_MASUKKAN_API_KEY_GEMINI_ANDA

AI_EMBED_PROVIDER=gemini
AI_EMBED_MODEL=text-embedding-004
AI_EMBED_API_KEY=AIzaSy_MASUKKAN_API_KEY_GEMINI_ANDA

# 4. Integrasi Notifikasi Telegram (Opsional, isi jika disiapkan pada Langkah 0.4)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_SAR_GROUP_ID=-1001234567890
```

Simpan perubahan dengan menekan `Ctrl + O`, lalu `Enter`, dan keluar dengan `Ctrl + X`.

---

## 4. Menjalankan Layanan Lapor SAR Lite

### 4.1 Build dan Nyalakan Kontainer
Jalankan Docker Compose dalam mode daemon (*detached*):
```bash
cd /opt/laporsar_lite
docker compose up -d --build
```

### 4.2 Verifikasi Status Kontainer
```bash
docker compose ps
```
Seluruh 4 kontainer harus berstatus running/healthy:
- `laporsar_lite_db` (PostGIS 16 Spasial)
- `laporsar_lite_redis` (Redis 7 Cache)
- `laporsar_lite_backend` (FastAPI Engine)
- `laporsar_lite_frontend` (Next.js PWA & Operator Map)

### 4.3 Periksa Log Backend
```bash
docker compose logs -f backend
```
Pastikan Anda melihat pesan:
```text
INFO: Lapor SAR Lite started — AI Cloud & Storage Engine ready
INFO: Default Master Tenants (pusat, natuna, jakarta, surabaya) seeded successfully
```
Tekan `Ctrl + C` untuk keluar dari pemantauan log.

---

## 5. Pilihan Akses Publik: Cloudflare Tunnel & Zero Trust (Direkomendasikan)

Cloudflare Tunnel adalah cara paling aman dan modern karena **tidak ada port HTTP/HTTPS yang dibuka ke internet**, kebal dari serangan DDoS, dan berfungsi bahkan di jaringan kantor/daerah di balik NAT tanpa IP publik.

### 5.1 Pasang Paket `cloudflared` di Debian
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb
rm cloudflared.deb
```

### 5.2 Opsi A: Menggunakan Quick Tunnel (Untuk Uji Coba Cepat Tanpa Domain)
Jika Anda hanya ingin membuat tautan sementara tanpa login:
```bash
cloudflared tunnel --url http://127.0.0.1:3000
```
Tautan publik `https://xxxx.trycloudflare.com` akan langsung muncul di terminal.

---

### 5.3 Opsi B: Menggunakan Named Tunnel Resmi (Untuk Domain Tetap Kantor SAR)
Jika Anda telah menyiapkan domain di Cloudflare (Langkah 0.3):

1. **Login ke Akun Cloudflare:**
   ```bash
   cloudflared tunnel login
   ```
   Terminal akan menampilkan tautan URL. Buka URL tersebut di browser, pilih domain Anda untuk mengizinkan otorisasi. File sertifikat `cert.pem` otomatis tersimpan di `/root/.cloudflared/cert.pem`.

2. **Buat Tunnel Baru:**
   ```bash
   cloudflared tunnel create laporsar-server
   ```
   *Catat **Tunnel UUID** yang tercetak di layar.*

3. **Buat Berkas Konfigurasi Ingress:**
   ```bash
   nano /root/.cloudflared/config.yml
   ```
   Isi dengan konfigurasi berikut (ganti `UUID_TUNNEL_ANDA` dan nama domain Anda):
   ```yaml
   tunnel: UUID_TUNNEL_ANDA
   credentials-file: /root/.cloudflared/UUID_TUNNEL_ANDA.json

   ingress:
     # Mengarahkan seluruh trafik web & API ke frontend Next.js (port 3000)
     - hostname: darurat.domainanda.com
       service: http://127.0.0.1:3000
     - service: http_status:404
   ```

4. **Daftarkan DNS Route:**
   ```bash
   cloudflared tunnel route dns laporsar-server darurat.domainanda.com
   ```

5. **Pasang sebagai Layanan Systemd (Otomatis Aktif Saat Server Reboot):**
   ```bash
   cloudflared service install
   systemctl enable --now cloudflared
   systemctl status cloudflared
   ```

Domain resmi Anda `https://darurat.domainanda.com` kini aktif dengan proteksi enkripsi SSL penuh!

---

### 5.4 Proteksi Dashboard Admin dengan Cloudflare Zero Trust Access (Opsional)
Jika Anda ingin dashboard operator SAR dilindungi autentikasi tambahan tingkat korporat/instansi (One-Time PIN via email atau SSO):

1. Buka dashboard [one.dash.cloudflare.com](https://one.dash.cloudflare.com).
2. Di menu kiri, pilih **Access** > **Applications** > klik **Add an application**.
3. Pilih tipe **Self-hosted**.
4. Masukkan parameter aplikasi:
   - **Application name:** `Lapor SAR Command Center`
   - **Application domain:** `darurat.domainanda.com`
   - **Path:** `/admin` (hanya mengunci area dashboard operator, sedangkan portal darurat warga tetap terbuka untuk umum).
5. Pada bagian **Policies**, atur kebijakan akses:
   - **Policy name:** `Staff Basarnas Only`
   - **Action:** `Allow`
   - **Include Rule:** Pilih `Emails ending in` lalu masukkan domain dinas (misal: `@basarnas.go.id`) atau daftar email personel.
6. Simpan konfigurasi. Sekarang setiap petugas yang membuka `https://darurat.domainanda.com/admin` akan menerima kode OTP login resmi di email dinas mereka sebelum masuk.

---

## 6. Pilihan Alternatif: Nginx Reverse Proxy + SSL Let's Encrypt

Jika server Anda memiliki IP Publik Statis dan Anda memilih menggunakan Nginx konvensional:

### 6.1 Pasang Nginx & Certbot
```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 6.2 Buat Konfigurasi Server Block
```bash
nano /etc/nginx/sites-available/laporsar.conf
```
Tambahkan konfigurasi berikut (sesuaikan `darurat.domainanda.com`):
```nginx
server {
    listen 80;
    server_name darurat.domainanda.com;

    client_max_body_size 25M;

    # Frontend PWA & Static Assets
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API & WebSockets
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Uploads & Media Audio/Foto
    location /uploads/ {
        proxy_pass http://127.0.0.1:8000/uploads/;
        proxy_set_header Host $host;
    }
}
```

### 6.3 Aktifkan Site & Terbitkan Sertifikat SSL
```bash
ln -s /etc/nginx/sites-available/laporsar.conf /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# Terbitkan SSL Let's Encrypt Otomatis
certbot --nginx -d darurat.domainanda.com --non-interactive --agree-tos -m admin@domainanda.com
```

---

## 7. Pengerasan Keamanan Firewall (UFW)

### 7.1 Konfigurasi Firewall jika Menggunakan Cloudflare Tunnel (Direkomendasikan)
Karena Cloudflare Tunnel menggunakan koneksi *outbound*, Anda **TIDAK PERLU** membuka port 80 maupun 443 ke internet:
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw enable
```

### 7.2 Konfigurasi Firewall jika Menggunakan Nginx Standar
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## 8. Verifikasi & Uji Coba Operasional End-to-End

Setelah instalasi selesai, lakukan uji coba menyeluruh untuk memastikan semua modul berfungsi:

1. **Akses Portal Pelapor:**
   - Buka `https://darurat.domainanda.com` di ponsel atau browser.
   - Pastikan ikon gembok SSL (HTTPS) valid.
2. **Uji Izin Geolokasi (GPS):**
   - Tekan tombol **Bagikan Lokasi / Deteksi Lokasi**.
   - Pastikan browser memunculkan *prompt* izin lokasi dan titik koordinat terbaca akurat.
3. **Uji Perekaman Suara (Voice Note):**
   - Rekam suara darurat singkat, misalnya: *"Perahu kami karam di dekat perairan Natuna koordinat 3 derajat utara, ada 4 orang butuh evakuasi segera."*
   - Kirim laporan. Verifikasi transkripsi teks muncul dalam waktu < 1 detik (Groq Whisper).
4. **Uji Notifikasi Telegram (Jika Dikonfigurasi):**
   - Periksa grup Telegram Siaga SAR. Bot harus meneruskan ringkasan musibah, estimasi korban, dan tautan lokasi Google Maps.
5. **Uji Dashboard Operator / Admin:**
   - Buka `https://darurat.domainanda.com/admin` (atau `/login`).
   - Masuk menggunakan kredensial yang diatur pada `.env` (`admin` / password Anda).
   - Pastikan titik laporan baru muncul di Peta Spasial SAR (PostGIS Leaflet Map) dan rekaman audio dapat diputar.

---

## 9. Perawatan Rutin, Pemantauan, & Pencadangan

### 9.1 Memeriksa Penggunaan Sumber Daya Server
```bash
docker stats
```
Total penggunaan RAM seluruh kontainer hanya berkisar antara **1.2 GB hingga 1.8 GB**, menjaga server tetap dingin dan stabil.

### 9.2 Memperbarui Aplikasi (*Rolling Update*)
Jika ada pembaruan kode dari repositori GitHub:
```bash
cd /opt/laporsar_lite
git pull origin main
docker compose up -d --build
```

### 9.3 Pencadangan Database (*Backup Otomatis*)
Cadangkan database PostGIS secara berkala ke berkas terkompresi:
```bash
mkdir -p /opt/backups
docker compose exec db pg_dump -U laporsar_admin -d laporsar_master | gzip > /opt/backups/laporsar_$(date +%Y%m%d_%H%M%S).sql.gz
```

Anda juga dapat menjadwalkannya secara otomatis setiap tengah malam menggunakan crontab:
```bash
crontab -e
```
Tambahkan baris:
```cron
0 2 * * * docker compose -f /opt/laporsar_lite/docker-compose.yml exec -T db pg_dump -U laporsar_admin -d laporsar_master | gzip > /opt/backups/laporsar_$(date +\%Y\%m\%d).sql.gz
```

---

## 📞 Bantuan Operasional

Sistem Lapor SAR Lite kini telah siap untuk operasional penuh maupun demonstrasi evaluasi resmi. Jika ada pertanyaan teknis terkait penyesuaian multi-tenant kantor SAR daerah atau integrasi radio komunikasi, silakan periksa berkas dokumentasi internal atau hubungi tim pengembang.
