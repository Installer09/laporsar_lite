# 🐧 Panduan Produksi & Self-Host: Lapor SAR Lite di Server Debian (Debian 11 / 12)
### *Standar Operasional SysAdmin: Zero Port Exposure, Cloudflare Tunnel Daemon, & Docker Isolation*

Panduan ini disusun secara khusus untuk menerapkan sistem **Lapor SAR Lite** pada server berbasis **Debian GNU/Linux (Debian 11 Bullseye atau Debian 12 Bookworm)**, baik di server fisik lokal (*on-premise / bare-metal*) maupun VPS Cloud (Linode, DigitalOcean, IDCloudHost, AWS, GCP, dll).

Karena versi **Lapor SAR Lite** telah dipangkas dari beban AI lokal yang berat:
- **Kebutuhan RAM:** Hanya **~2 GB RAM** (Server VPS paket 2 vCPU / 2GB atau 4GB RAM sudah sangat leluasa).
- **Kebutuhan Disk:** Minimal **25 GB SSD/NVMe**.
- **Koneksi:** Cukup akses internet *outbound* (tidak wajib IP Publik Statis jika menggunakan Cloudflare Tunnel).

---

## 📋 DAFTAR ISI

1. [Persiapan Sistem Operasi Debian](#1-persiapan-sistem-operasi-debian)
2. [Instalasi Docker Engine & Docker Compose Resmi](#2-instalasi-docker-engine--docker-compose-resmi)
3. [Kloning Repositori & Konfigurasi Berkas .env](#3-kloning-repositori--konfigurasi-berkas-env)
4. [Menjalankan Layanan Lapor SAR Lite](#4-menjalankan-layanan-lapor-sar-lite)
5. [Pilihan Akses Publik: Cloudflare Tunnel (Direkomendasikan)](#5-pilihan-akses-publik-cloudflare-tunnel-direkomendasikan)
6. [Pilihan Alternatif: Nginx Reverse Proxy + SSL Let's Encrypt](#6-pilihan-alternatif-nginx-reverse-proxy--ssl-lets-encrypt)
7. [Pengerasan Keamanan Firewall (UFW)](#7-pengerasan-keamanan-firewall-ufw)
8. [Perawatan Rutin & Pemantauan Performa](#8-perawatan-rutin--pemantauan-performa)

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

Isi kunci API AI pihak ketiga Anda:
```env
# Ganti kunci rahasia JWT dengan string acak yang kuat
SECRET_KEY=ganti_dengan_kunci_acak_panjang_minimal_32_karakter

# Preset Rekomendasi Utama (Groq Whisper + Gemini Flash)
AI_STT_PROVIDER=groq
AI_STT_MODEL=whisper-large-v3
AI_STT_API_KEY=gsk_MASUKKAN_API_KEY_GROQ_ANDA

AI_LLM_PROVIDER=gemini
AI_LLM_MODEL=gemini-1.5-flash
AI_LLM_API_KEY=AIzaSy_MASUKKAN_API_KEY_GEMINI_ANDA

AI_EMBED_PROVIDER=gemini
AI_EMBED_MODEL=text-embedding-004
AI_EMBED_API_KEY=AIzaSy_MASUKKAN_API_KEY_GEMINI_ANDA
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
- `laporsar_lite_db` (PostGIS 16)
- `laporsar_lite_redis` (Redis 7)
- `laporsar_lite_backend` (FastAPI)
- `laporsar_lite_frontend` (Next.js)

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

## 5. Pilihan Akses Publik: Cloudflare Tunnel (Direkomendasikan)

Cloudflare Tunnel adalah cara paling aman dan modern karena **tidak ada port HTTP/HTTPS yang dibuka ke internet**, kebal dari serangan DDoS, dan berfungsi bahkan di jaringan kantor/daerah di balik NAT tanpa IP publik.

### 5.1 Pasang Paket `cloudflared` di Debian
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb
rm cloudflared.deb
```

### 5.2 Opsi A: Menggunakan Quick Tunnel (Untuk Demo Instan Cepat)
Jika Anda hanya ingin membuat tautan sementara untuk presentasi:
```bash
cloudflared tunnel --url http://127.0.0.1:3000
```
Tautan publik `https://xxxx.trycloudflare.com` akan langsung muncul di terminal.

### 5.3 Opsi B: Menggunakan Named Tunnel Resmi (Untuk Domain Permanen)
Jika Anda memiliki domain di Cloudflare (misal: `sar-daerah.go.id` atau `laporsar.com`):

1. **Login ke Cloudflare:**
   ```bash
   cloudflared tunnel login
   ```
   Klik tautan autentikasi yang diberikan untuk memilih domain Anda.

2. **Buat Tunnel Baru:**
   ```bash
   cloudflared tunnel create laporsar-server
   ```
   Catat *Tunnel UUID* yang dihasilkan.

3. **Buat Berkas Konfigurasi:**
   ```bash
   mkdir -p ~/.cloudflared
   nano ~/.cloudflared/config.yml
   ```
   Isi dengan konfigurasi berikut:
   ```yaml
   tunnel: UUID_TUNNEL_ANDA
   credentials-file: /root/.cloudflared/UUID_TUNNEL_ANDA.json

   ingress:
     - hostname: demo.domainanda.com
       service: http://127.0.0.1:3000
     - service: http_status:404
   ```

4. **Daftarkan DNS Route:**
   ```bash
   cloudflared tunnel route dns laporsar-server demo.domainanda.com
   ```

5. **Pasang sebagai Layanan Systemd (Otomatis Nyala Saat Reboot):**
   ```bash
   cloudflared service install
   systemctl enable --now cloudflared
   systemctl status cloudflared
   ```

Domain Anda `https://demo.domainanda.com` kini aktif dengan SSL penuh dan perlindungan DDoS!

---

## 6. Pilihan Alternatif: Nginx Reverse Proxy + SSL Let's Encrypt

Jika server Anda memiliki IP Publik Statis dan Anda lebih memilih Nginx konvensional:

### 6.1 Pasang Nginx & Certbot
```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 6.2 Buat Konfigurasi Server Block
```bash
nano /etc/nginx/sites-available/laporsar.conf
```
Tambahkan konfigurasi berikut (ganti `demo.domainanda.com`):
```nginx
server {
    listen 80;
    server_name demo.domainanda.com;

    client_max_body_size 25M;

    # Frontend & Static Files
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

    # Uploads & Media Streaming
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
certbot --nginx -d demo.domainanda.com --non-interactive --agree-tos -m admin@domainanda.com
```

---

## 7. Pengerasan Keamanan Firewall (UFW)

Jika menggunakan **Cloudflare Tunnel**, server **TIDAK PERLU** membuka port 80 maupun 443!

### 7.1 Konfigurasi Firewall untuk Cloudflare Tunnel
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

## 8. Perawatan Rutin & Pemantauan Performa

### 8.1 Memeriksa Penggunaan Sumber Daya Server
```bash
docker stats
```
Anda akan melihat penggunaan RAM total kontainer hanya berkisar antara **1.2 GB hingga 1.8 GB**, sangat efisien untuk server berkapasitas hemat.

### 8.2 Memperbarui Aplikasi (*Rolling Update*)
Jika ada pembaruan kode terbaru dari repositori GitHub:
```bash
cd /opt/laporsar_lite
git pull origin main
docker compose up -d --build
```

### 8.3 Pencadangan Database (*Backup*)
Buat salinan database PostGIS secara berkala:
```bash
mkdir -p /opt/backups
docker compose exec db pg_dump -U laporsar_admin -d laporsar_master | gzip > /opt/backups/laporsar_$(date +%Y%m%d_%H%M%S).sql.gz
```

---

## 📞 Bantuan Operasional

Sistem Lapor SAR Lite siap digunakan untuk operasional kantor SAR maupun demonstrasi evaluasi nasional. Jika ada kendala koneksi AI atau perizinan mikrofon/kamera di browser, pastikan domain selalu diakses melalui protokol **HTTPS**.
