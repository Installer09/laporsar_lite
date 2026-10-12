# 📘 PANDUAN LENGKAP PENERAPAN SERVER LOKAL LAPOR SAR LITE
### *Spesifikasi Kasus: Proxmox VE, VM Debian 12 / Ubuntu (192.168.70.20), Manajemen User & Keamanan, Nginx Reverse Proxy, MikroTik DNS (laporsar.lan), & Cloudflare Tunnel*

Panduan ini disusun secara berurutan (*step-by-step*) khusus untuk skenario penerapan mandiri di server lokal Anda saat ini. Setiap langkah dilengkapi dengan **skrip perintah terminal Linux (bash) siap salin (*copy-paste*)**, konfigurasi keamanan ketat (*hardening*), serta verifikasi status.

---

## 📌 RANGKUMAN SPESIFIKASI SISTEM
- **Hypervisor Host:** Proxmox Virtual Environment (VE) 8.x
- **Guest OS (Virtual Machine):** Debian 12 (Bookworm) / Ubuntu 22.04 LTS Server
- **IP Address VM Server:** `192.168.70.20/24` (Gateway: `192.168.70.1`, DNS: `192.168.70.1, 8.8.8.8`)
- **User Pengelola Server:** `saradmin` (Hak akses: `sudo`, `docker`)
- **Domain Intranet:** `http://laporsar.lan` (dan `http://natuna.laporsar.lan`)
- **Reverse Proxy:** Nginx (Port 80)
- **Firewall:** UFW (Hanya buka port 22, 80, 443 — port DB/Redis/FastAPI tertutup dari luar)
- **Anti Brute-Force:** Fail2ban (Proteksi SSH)
- **Akses Publik HTTPS (Chatbot/Webhook):** Cloudflare Quick Tunnel (`cloudflared`)
- **Tenant Target Default:** Kantor SAR Natuna (`natuna`)

---

## 📑 DAFTAR LANGKAH IMPLEMENTASI
1. [Langkah 1: Instalasi & Persiapan Proxmox VE](#langkah-1-instalasi--persiapan-proxmox-ve)
2. [Langkah 2: Pembuatan Virtual Machine (VM) di Proxmox](#langkah-2-pembuatan-virtual-machine-vm-di-proxmox)
3. [Langkah 3: Konfigurasi Jaringan Statis VM (192.168.70.20)](#langkah-3-konfigurasi-jaringan-statis-vm-1921687020)
4. [Langkah 4: Pembuatan User Pengelola & Hak Akses Sudo](#langkah-4-pembuatan-user-pengelola--hak-akses-sudo)
5. [Langkah 5: Pengerasan Keamanan Server (SSH, UFW Firewall, Fail2ban)](#langkah-5-pengerasan-keamanan-server-ssh-ufw-firewall-fail2ban)
6. [Langkah 6: Instalasi Resmi Docker Engine & Git di VM](#langkah-6-instalasi-resmi-docker-engine--git-di-vm)
7. [Langkah 7: Transfer / Kloning Proyek & Konfigurasi File Environment (.env) Wajib](#langkah-7-transfer--kloning-proyek--konfigurasi-file-environment-env-wajib)
8. [Langkah 8: Menjalankan & Membangun Ulang Kontainer Docker](#langkah-8-menjalankan--membangun-ulang-kontainer-docker)
9. [Langkah 9: Konfigurasi DNS Statis di Router MikroTik Kantor](#langkah-9-konfigurasi-dns-statis-di-router-mikrotik-kantor)
10. [Langkah 10: Mengaktifkan Cloudflare Quick Tunnel (HTTPS Publik)](#langkah-10-mengaktifkan-cloudflare-quick-tunnel-https-publik)
11. [Langkah 11: Verifikasi & Login Operator Kantor SAR Natuna](#langkah-11-verifikasi--login-operator-kantor-sar-natuna)
12. [Langkah 12: Pemeliharaan Server, Backup & Monitoring Rutin](#langkah-12-pemeliharaan-server-backup--monitoring-rutin)
13. [Lampiran: Skrip Otomasi Cepat Satu-Klik (`setup_server_security.sh`)](#lampiran-skrip-otomasi-cepat-satu-klik)

---

## Langkah 1: Instalasi & Persiapan Proxmox VE

Jika mesin fisik server Anda belum terpasang Proxmox VE:
1. Unduh installer ISO resmi **Proxmox VE (versi 8.x)** dari [proxmox.com/en/downloads](https://www.proxmox.com/en/downloads).
2. Buat USB Bootable menggunakan aplikasi **Rufus** (pilih mode *DD Image*) atau **Ventoy**.
3. Pasang USB ke PC Server, nyalakan, lalu masuk ke BIOS/UEFI (tekan `F2` / `Del` / `F12`):
   - Pastikan fitur **Intel VT-x** atau **AMD-V (Virtualization)** dalam posisi **Enabled**.
   - Atur prioritas booting ke USB Flashdisk.
4. Pilih **Install Proxmox VE (Graphical)**:
   - Pilih harddisk/SSD target instalasi.
   - Atur Negara: `Indonesia`, Timezone: `Asia/Jakarta`, Keyboard: `U.S. English`.
   - Masukkan password akun `root` dan email administrator Anda.
   - **Konfigurasi IP Management Host Proxmox:**
     - Interface: Pilih kartu LAN fisik utama (misal `eno1` atau `eth0`).
     - Hostname: `pve-sar.local`
     - IP Address (CIDR): `192.168.70.10/24` *(IP host Proxmox, bedakan dengan IP VM Lapor SAR)*
     - Gateway: `192.168.70.1` *(IP Router MikroTik)*
     - DNS Server: `192.168.70.1` (atau `8.8.8.8`)
5. Tunggu proses instalasi selesai, cabut flashdisk, lalu klik **Reboot**.
6. Buka browser di PC kerja Anda, akses web dashboard Proxmox:
   ```text
   https://192.168.70.10:8006
   ```
   *(Abaikan peringatan sertifikat SSL di browser dengan klik "Advanced" $\rightarrow$ "Proceed").*
   - Login: User `root`, password sesuai yang Anda buat saat instalasi.

---

## Langkah 2: Pembuatan Virtual Machine (VM) di Proxmox

1. **Upload ISO OS ke Proxmox:**
   - Di web Proxmox, klik node Anda (`pve`) $\rightarrow$ storage **`local`** $\rightarrow$ **ISO Images**.
   - Klik tombol **Upload**, lalu unggah ISO **Debian 12 Netinst** (rekomendasi ringan) atau **Ubuntu 22.04 Live Server**.
2. **Buat Virtual Machine Baru:**
   - Klik tombol biru **Create VM** di pojok kanan atas dashboard Proxmox:
     - **General:** Node: `pve`, VM ID: `100`, Name: `laporsar-server`.
     - **OS:** Pilih *Storage: local*, ISO image: `debian-12.x.x-amd64-netinst.iso`.
     - **System:** Graphic: Default, Qemu Agent: centang `[v]`.
     - **Disks:** Bus/Device: `SCSI`, Storage: `local-lvm`, Disk size: minimal `32 GB` atau `50 GB`, SSD emulation: centang `[v]`.
     - **CPU:** Sockets: `1`, Cores: `2` atau `4` core, Type: `host`.
     - **Memory:** `4096 MB` (4 GB RAM disarankan, minimal 2 GB).
     - **Network:** Bridge: `vmbr0`, Model: `VirtIO (paravirtualized)`.
3. Klik **Finish**, lalu klik VM `100 (laporsar-server)` $\rightarrow$ klik **Start**.
4. Buka tab **Console**, lalu selesaikan instalasi Debian:
   - Pilih bahasa: *English*, Lokasi: *other $\rightarrow$ Asia $\rightarrow$ Indonesia*.
   - Hostname: `laporsar-server`, Domain: `lan`.
   - Set password root.
   - Buat user biasa pertama: `saradmin` dan masukkan password-nya.
   - **Software Selection (PENTING):**
     - **HILANGKAN CENTANG [ ] Debian desktop environment & GNOME** (agar hemat RAM dan CPU).
     - **CENTANG [v] SSH server** dan **[v] standard system utilities**.
   - Install GRUB boot loader ke disk utama (`/dev/sda` atau `/dev/vda`).
   - Klik *Finish the installation* $\rightarrow$ VM akan reboot.

---

## Langkah 3: Konfigurasi Jaringan Statis VM (192.168.70.20)

Pastikan IP address VM terkunci statis ke `192.168.70.20` agar tidak berubah saat router reboot.

1. Buka console VM di Proxmox, lalu login sebagai `root`:
   ```bash
   su -
   ```
2. Edit file antarmuka jaringan:
   - **Jika menggunakan Debian 12:**
     ```bash
     nano /etc/network/interfaces
     ```
     Sesuaikan baris antarmuka jaringan utama (biasanya bernama `ens18` atau `eth0`):
     ```text
     # The primary network interface
     auto ens18
     iface ens18 inet static
         address 192.168.70.20
         netmask 255.255.255.0
         gateway 192.168.70.1
         dns-nameservers 192.168.70.1 8.8.8.8
     ```
     Simpan file: Tekan `Ctrl + O`, lalu `Enter`, keluar dengan `Ctrl + X`.

     Terapkan konfigurasi jaringan:
     ```bash
     systemctl restart networking
     ```

   - **Jika menggunakan Ubuntu Server (Netplan):**
     ```bash
     nano /etc/netplan/00-installer-config.yaml
     ```
     Isi dengan:
     ```yaml
     network:
       version: 2
       ethernets:
         ens18:
           dhcp4: no
           addresses:
             - 192.168.70.20/24
           routes:
             - to: default
               via: 192.168.70.1
           nameservers:
             addresses: [192.168.70.1, 8.8.8.8]
     ```
     Terapkan dengan:
     ```bash
     netplan apply
     ```

3. Uji koneksi internet dari VM:
   ```bash
   ping -c 3 8.8.8.8
   ping -c 3 google.com
   ```
   *Pastikan menghasilkan balasan (0% packet loss).*

---

## Langkah 4: Pembuatan User Pengelola & Hak Akses Sudo

Mengelola server langsung sebagai `root` berisiko tinggi. Buat user pengelola khusus `saradmin` dengan hak `sudo`.

Jalankan perintah berikut di console VM (sebagai `root`):

```bash
# 1. Update paket dan instal paket sudo
apt update
apt install -y sudo curl wget git htop

# 2. Buat user 'saradmin' jika belum ada saat instalasi OS
if ! id "saradmin" &>/dev/null; then
    adduser --gecos "Administrator Lapor SAR" saradmin
fi

# 3. Masukkan user 'saradmin' ke dalam grup 'sudo'
usermod -aG sudo saradmin

# 4. Verifikasi bahwa saradmin sudah masuk ke grup sudo
id saradmin
# Output harus menampilkan: uid=1000(saradmin) gid=1000(saradmin) groups=1000(saradmin),27(sudo)
```

Uji masuk sebagai `saradmin`:
```bash
su - saradmin
sudo whoami
# Masukkan password saradmin -> Output harus menampilkan: root
exit
```

---

## Langkah 5: Pengerasan Keamanan Server (SSH, UFW Firewall, Fail2ban)

Terapkan standar keamanan berlapis (*security hardening*) agar server aman dari akses tidak sah dan serangan brute-force di jaringan kantor maupun publik.

Jalankan seluruh skrip berikut sebagai `root`:

### 1. Pasang Utilitas Keamanan:
```bash
apt install -y ufw fail2ban unattended-upgrades
```

### 2. Pengerasan Keamanan SSH:
Buat file konfigurasi keamanan SSH khusus:
```bash
cat << 'EOF' > /etc/ssh/sshd_config.d/99-laporsar-security.conf
# Keamanan SSH Server Lapor SAR
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
EOF

# Restart service SSH
systemctl restart sshd || systemctl restart ssh
```

### 3. Konfigurasi Firewall UFW (Sangat Penting):
Aturan keamanan: **Semua port incoming ditutup secara default**, kecuali port yang diperlukan. Port database (5432), cache Redis (6379), FastAPI Backend (8000), dan Next.js Frontend (3000) **TIDAK DIBUKA KE LUAR**, karena seluruh lalu lintas wajib disaring melalui Nginx di port 80.

```bash
# Reset aturan lama
ufw --force reset

# Kebijakan default
ufw default deny incoming
ufw default allow outgoing

# Port yang dibuka:
ufw allow 22/tcp comment 'SSH Remote Management'
ufw allow 80/tcp comment 'Lapor SAR Nginx Reverse Proxy'
ufw allow 443/tcp comment 'HTTPS Secure Tunnel'

# Aktifkan UFW
echo "y" | ufw enable

# Periksa status firewall
ufw status verbose
```
*Output harus menunjukkan Status: active dan hanya port 22, 80, 443 yang berstatus ALLOW IN.*

### 4. Konfigurasi Fail2ban (Anti Brute-Force):
Fail2ban otomatis memblokir IP yang gagal memasukkan password SSH berulang kali.

```bash
cat << 'EOF' > /etc/fail2ban/jail.local
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port    = 22
mode    = normal
EOF

systemctl enable fail2ban
systemctl restart fail2ban
fail2ban-client status sshd
```

---

## Langkah 6: Instalasi Resmi Docker Engine & Git di VM

Lapor SAR Lite berjalan di atas kontainer Docker resmi. Pasang Docker Engine dan Docker Compose Plugin terbaru:

```bash
# 1. Daftarkan GPG Key resmi Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# 2. Daftarkan repositori resmi Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3. Instal Docker Engine & Docker Compose Plugin
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Aktifkan service Docker agar otomatis hidup saat server menyala
systemctl enable --now docker

# 5. Berikan hak akses Docker kepada user 'saradmin'
usermod -aG docker saradmin

# 6. Verifikasi versi
docker --version
docker compose version
```

---

## Langkah 7: Transfer / Kloning Proyek & Konfigurasi File Environment (.env) Wajib

Seluruh berkas aplikasi ditempatkan di direktori `/opt/laporsar_lite`.

### 1. Buat Direktori & Atur Izin Kepemilikan:
```bash
mkdir -p /opt/laporsar_lite
chown -R saradmin:docker /opt/laporsar_lite
chmod -R 775 /opt/laporsar_lite
```

### 2. Kloning Proyek dari Git:
Masuk sebagai user `saradmin`:
```bash
su - saradmin
git clone https://github.com/Installer09/laporsar_lite.git /opt/laporsar_lite
cd /opt/laporsar_lite
```

> [!IMPORTANT]
> **PENTING: File `.env` di-ignore oleh Git demi keamanan kredensial.**
> Anda wajib membuat file `.env` di folder utama dan folder pendukung dari file template `.env.example` yang telah disediakan.

---

### ⚙️ Konfigurasi 1: File `.env` Folder Utama (`/opt/laporsar_lite/.env`)

File ini adalah **Single Source of Truth** untuk seluruh orkestrasi kontainer Docker.

1. Salin template `.env.example`:
   ```bash
   cd /opt/laporsar_lite
   cp .env.example .env
   nano .env
   ```

2. Pastikan nilai konfigurasi wajib berikut terisi dengan benar:
   ```env
   # =====================================================================
   # LAPOR SAR LITE — ENVIRONMENT CONFIGURATION (ROOT SINGLE SOURCE)
   # =====================================================================
   PROJECT_NAME="Lapor SAR API"
   VERSION="3.1.0-lite"

   # 1. KEAMANAN & AUTENTIKASI
   SECRET_KEY=laporsar-lite-secret-key-change-for-production-demo
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=10080

   # Akun Super Admin Global (Akses semua sistem)
   DEV_SUPERADMIN_ENABLED=true
   DEV_SUPERADMIN_USERNAME=superadmin
   DEV_SUPERADMIN_PASSWORD=superadmin

   # Akun Admin Command Center Pusat
   DEV_ADMIN_ENABLED=true
   DEV_ADMIN_USERNAME=admin
   DEV_ADMIN_PASSWORD=admin

   # 2. DATABASE & CACHE (Jaringan Internal Docker)
   DATABASE_URL=postgresql+asyncpg://laporsar_admin:laporsar_admin@db:5432/laporsar_master
   REDIS_URL=redis://redis:6379/0

   # 3. ROUTING & DOMAIN (KUNCI UTAMA TAMPILAN DASHBOARD)
   # - Untuk Server Lokal saat ini: http://laporsar.lan (atau http://192.168.70.20)
   # - Untuk Migrasi Domain Resmi nanti: https://laporsar.basarnas.go.id
   FRONTEND_URL=http://laporsar.lan
   NEXT_PUBLIC_API_URL=/api
   INTERNAL_BACKEND_URL=http://backend:8000

   # 4. PENYIMPANAN BERKAS LOKAL
   STORAGE_TYPE=local
   LOCAL_STORAGE_DIR=/app/uploads

   # 5. PRESET AI MULTI-PROVIDER CLOUD
   AI_STT_PROVIDER=groq
   AI_STT_MODEL=whisper-large-v3
   AI_STT_API_KEY=gsk_your_groq_api_key_here

   AI_LLM_PROVIDER=gemini
   AI_LLM_MODEL=gemini-1.5-flash
   AI_LLM_API_KEY=AIzaSy_your_gemini_api_key_here

   AI_EMBED_PROVIDER=gemini
   AI_EMBED_MODEL=text-embedding-004
   AI_EMBED_API_KEY=AIzaSy_your_gemini_api_key_here

   # 6. INTEGRASI BOT TELEGRAM & WHATSAPP (OPSIONAL)
   TELEGRAM_BOT_TOKEN=
   TELEGRAM_SAR_GROUP_ID=
   TELEGRAM_SECRET_TOKEN=

   WHATSAPP_API_TOKEN=
   WHATSAPP_PHONE_NUMBER_ID=
   WHATSAPP_VERIFY_TOKEN=SARBOT_VERIFY_TOKEN
   WHATSAPP_SAR_GROUP_ID=
   ```
   *(Simpan: Tekan `Ctrl + O` $\rightarrow$ `Enter` $\rightarrow$ `Ctrl + X`)*.

---

### ⚙️ Konfigurasi 2: File `.env` Folder Backend (`/opt/laporsar_lite/backend/.env`)

Folder `./backend` di-mount ke dalam kontainer FastAPI. Agar worker Python membaca nama service Docker:

```bash
cd /opt/laporsar_lite/backend
cp .env.example .env
nano .env
```
Pastikan variabel koneksinya menggunakan:
```env
DATABASE_URL=postgresql+asyncpg://laporsar_admin:laporsar_admin@db:5432/laporsar_master
REDIS_URL=redis://redis:6379/0
FRONTEND_URL=http://laporsar.lan
```
*(Simpan: `Ctrl + O` $\rightarrow$ `Enter` $\rightarrow$ `Ctrl + X`)*.

---

### ⚙️ Konfigurasi 3: File `.env` Folder Frontend (`/opt/laporsar_lite/frontend`)

Next.js menggunakan konfigurasi relative URL `/api` agar otomatis kompatibel dengan domain apa pun:

```bash
cd /opt/laporsar_lite/frontend
cp .env.example .env.production
```
Pastikan isinya:
```env
NEXT_PUBLIC_API_URL=/api
INTERNAL_BACKEND_URL=http://backend:8000
```

---

## Langkah 8: Menjalankan & Membangun Ulang Kontainer Docker

> [!WARNING]
> **PENTING: Setiap kali mengubah file `.env` atau menarik pembaruan kode via `git pull`, kontainer HARUS di-rebuild dan di-restart** agar Nginx dan Node.js memuat konfigurasi terbaru.

Jalankan sebagai user `saradmin`:

```bash
cd /opt/laporsar_lite

# 1. Hentikan kontainer lama jika ada
docker compose down

# 2. Bangun ulang (rebuild) dan jalankan seluruh kontainer
docker compose up -d --build
```

### Memeriksa Status Kontainer:
```bash
docker compose ps
```
Output harus menunjukkan kelima kontainer berstatus **Up / healthy**:
- `laporsar_lite_nginx` (Port 80) $\rightarrow$ Gerbang Nginx Reverse Proxy
- `laporsar_lite_frontend` (Port 3000) $\rightarrow$ Next.js Web Dashboard
- `laporsar_lite_backend` (Port 8000) $\rightarrow$ FastAPI Engine & WebSocket
- `laporsar_lite_db` (Port 5432) $\rightarrow$ PostgreSQL 16 + PostGIS
- `laporsar_lite_redis` (Port 6379) $\rightarrow$ Redis Caching

### Memeriksa Log Kontainer (Jika Diperlukan):
```bash
# Cek log Nginx
docker compose logs -f nginx

# Cek log backend FastAPI
docker compose logs -f backend

# Cek log frontend Next.js
docker compose logs -f frontend
```

---

## Langkah 9: Konfigurasi DNS Statis di Router MikroTik Kantor

Agar seluruh komputer dan HP di jaringan kantor yang mengakses `http://laporsar.lan` atau `http://natuna.laporsar.lan` otomatis diarahkan ke server `192.168.70.20`:

### Opsi 1: Menggunakan Terminal MikroTik (CLI - Tercepat)
1. Buka **Winbox** atau **SSH** ke Router MikroTik kantor.
2. Buka menu **New Terminal**, salin dan jalankan 2 baris perintah berikut:
   ```routeros
   /ip dns static add name="laporsar.lan" address=192.168.70.20 ttl=1d comment="Lapor SAR Server Lokal"
   /ip dns static add regexp=".*\\.laporsar\\.lan" address=192.168.70.20 ttl=1d comment="Lapor SAR Subdomain Cabang"
   ```

### Opsi 2: Menggunakan Winbox (GUI)
1. Buka Winbox, klik menu **IP** $\rightarrow$ **DNS**.
2. Pastikan opsi **Allow Remote Requests** tercentang (`[v]`).
3. Klik tombol **Static** di sebelah kanan.
4. Klik tombol **[ + ]** (Tambah):
   - **Name:** `laporsar.lan`
   - **Address:** `192.168.70.20`
   - **TTL:** `1d`
   - Klik **Apply** $\rightarrow$ **OK**.
5. Tambahkan entri kedua untuk subdomain cabang Natuna:
   - **Name:** `natuna.laporsar.lan`
   - **Address:** `192.168.70.20`
   - **TTL:** `1d`
   - Klik **Apply** $\rightarrow$ **OK**.

---

## Langkah 10: Mengaktifkan Cloudflare Quick Tunnel (HTTPS Publik)

Cloudflare Quick Tunnel memancarkan alamat HTTPS publik resmi secara instan agar:
- Fitur PWA (Mikrofon Voice Note & GPS Lokasi) dapat berjalan di HP dengan standar keamanan browser modern.
- Webhook WhatsApp Meta dan Telegram Bot dari internet dapat masuk ke server lokal Anda.

### 1. Pasang `cloudflared` di VM Server (sebagai `root` atau `sudo`):
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb
```

### 2. Jalankan Quick Tunnel Mengarah ke Nginx (Port 80):
```bash
cloudflared tunnel --url http://127.0.0.1:80
```
Terminal akan menampilkan URL publik acak HTTPS, contoh:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:                                          |
|  https://emergency-alert-rescue-xxxx.trycloudflare.com                                    |
+--------------------------------------------------------------------------------------------+
```

### 3. Menjalankan Cloudflared sebagai Service Background Otomatis (Opsional):
Jika Anda ingin tunnel tetap hidup meskipun terminal ditutup:
```bash
sudo nohup cloudflared tunnel --url http://127.0.0.1:80 > /var/log/cloudflared.log 2>&1 &
```
Cek URL tunnel yang sedang aktif:
```bash
grep -o 'https://.*\.trycloudflare\.com' /var/log/cloudflared.log | tail -n 1
```

---

## Langkah 11: Verifikasi & Login Operator Kantor SAR Natuna

### 1. Uji Koneksi DNS dari PC Operator
Buka Command Prompt (CMD) di laptop/PC operator kantor:
```cmd
ping laporsar.lan
```
*Pastikan membalas (reply) dari IP `192.168.70.20`.*

### 2. Membuka Dashboard Lapor SAR
Buka browser (Google Chrome / Microsoft Edge), akses:
```text
http://laporsar.lan
```
Halaman publik **Portal Terpadu Lapor SAR** akan tampil secara instan beserta peta sebaran insiden.

### 3. Login Operator Kantor SAR Natuna
1. Klik tombol **Masuk Petugas** di pojok kanan atas $\rightarrow$ Pilih **Masuk Akun**.
2. Masukkan kredensial:
   - **Username:** `natuna` *(atau `admin.natuna@basarnas.go.id`)*
   - **Password:** `admin`
3. Klik **Masuk**.

### 4. Hasil Verifikasi:
- Dashboard langsung bertuliskan ruang kerja **Kantor SAR Natuna**.
- Peta operasi otomatis berfokus pada wilayah perairan **Ranai, Kepulauan Anambas, Serasan, dan Subi**.
- Daftar alutsista dan pos yang tampil:
  - **KN SASIKIRANA 245** & **RIB 01 Natuna**
  - **Pos SAR Anambas** (Tarempa)
  - **Unit Siaga SAR Serasan**
  - **Unit Siaga SAR Subi**
- Indikator status live WebSocket di header menyala hijau (**Online / Live Connected**).

---

## Langkah 12: Pemeliharaan Server, Backup & Monitoring Rutin

Untuk menjaga performa dan keandalan server jangka panjang:

### 1. Backup Rutin Database PostgreSQL:
Jalankan perintah ini untuk membuat salinan cadangan (*dump*) database master dan seluruh tenant:
```bash
# Backup database master
docker exec -t laporsar_lite_db pg_dump -U laporsar_admin -d laporsar_master > /opt/backup_master_$(date +%F).sql

# Backup database tenant Natuna
docker exec -t laporsar_lite_db pg_dump -U laporsar_admin -d laporsar_natuna > /opt/backup_natuna_$(date +%F).sql
```

### 2. Pembersihan Log & Docker Cache:
Jika disk server mulai penuh:
```bash
# Bersihkan build cache Docker yang tidak terpakai
docker system prune -f

# Periksa kapasitas disk
df -h
```

### 3. Memperbarui Kode Proyek di Masa Mendatang:
```bash
cd /opt/laporsar_lite
git pull origin main
docker compose down
docker compose up -d --build
```

---

## Lampiran: Skrip Otomasi Cepat Satu-Klik

Untuk mempermudah setup server baru tanpa harus mengetik perintah satu per satu, telah disediakan skrip otomatis di dalam repositori: [`scripts/setup_server_security.sh`](file:///d:/Project%20Digitalisasi/Lapor%20SAR%20Lite/scripts/setup_server_security.sh).

### Cara Menjalankan di Server Baru:
Login sebagai `root`, lalu jalankan:

```bash
# 1. Unduh skrip langsung dari repositori
curl -fsSL https://raw.githubusercontent.com/Installer09/laporsar_lite/main/scripts/setup_server_security.sh -o setup.sh

# 2. Beri izin eksekusi dan jalankan
chmod +x setup.sh
bash setup.sh
```

Skrip ini akan secara otomatis:
1. Memperbarui seluruh paket sistem Debian/Ubuntu.
2. Membuat user `saradmin` dengan hak `sudo`.
3. Mengonfigurasi keamanan SSH (`MaxAuthTries 3`, proteksi sesi).
4. Mengonfigurasi firewall UFW (hanya membuka port 22, 80, 443).
5. Mengaktifkan Fail2ban untuk proteksi brute-force.
6. Memasang Docker Engine resmi dan Docker Compose Plugin.
7. Memasukkan user `saradmin` ke grup `docker`.
8. Menyiapkan direktori `/opt/laporsar_lite` dengan hak kepemilikan yang tepat.
