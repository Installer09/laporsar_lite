# 📘 PANDUAN LENGKAP PENERAPAN SERVER LOKAL LAPOR SAR LITE
### *Spesifikasi Kasus: Proxmox VE 8.x, VM Debian 13 (Trixie) (192.168.70.20), CLI Command-Line Master Guide, Nginx Reverse Proxy, MikroTik DNS (laporsar.lan), & Cloudflare Tunnel*

Panduan ini disusun secara berurutan (*step-by-step*) khusus untuk skenario penerapan mandiri di server lokal Anda menggunakan **Debian 13 (Trixie)**. Setiap langkah dilengkapi dengan **perintah terminal Linux (CLI bash) detail yang siap disalin (*copy-paste*)**, konfigurasi keamanan ketat (*hardening*), serta verifikasi status.

---

## 📌 RANGKUMAN SPESIFIKASI SISTEM
- **Hypervisor Host:** Proxmox Virtual Environment (VE) 8.x
- **Guest OS (Virtual Machine):** Debian 13 (Trixie) 64-bit Minimal Server
- **IP Address VM Server:** `192.168.70.20/24` (Gateway: `192.168.70.1`, DNS: `192.168.70.1, 8.8.8.8`)
- **User Pengelola Server:** `saradmin` (Hak akses: `sudo`, `docker`)
- **Direktori Aplikasi:** `/opt/laporsar_lite`
- **Domain Intranet:** `http://laporsar.lan` (dan `http://natuna.laporsar.lan`)
- **Reverse Proxy:** Nginx (Port 80 HTTP)
- **Firewall:** UFW / nftables (Hanya buka port 22, 80, 443 — port DB/Redis/FastAPI tertutup dari jaringan luar)
- **Anti Brute-Force:** Fail2ban (Proteksi SSH)
- **Akses Publik HTTPS (Chatbot/Webhook):** Cloudflare Quick Tunnel (`cloudflared`)
- **Tenant Target Default:** Kantor SAR Natuna (`natuna`)

---

## 📑 DAFTAR LANGKAH IMPLEMENTASI
1. [Langkah 1: Persiapan Proxmox VE & Pengunduhan ISO Debian 13 via CLI](#langkah-1-persiapan-proxmox-ve--pengunduhan-iso-debian-13-via-cli)
2. [Langkah 2: Pembuatan Virtual Machine (VM) di Proxmox (CLI & GUI)](#langkah-2-pembuatan-virtual-machine-vm-di-proxmox-cli--gui)
3. [Langkah 3: Konfigurasi Jaringan Statis VM Debian 13 (192.168.70.20) via CLI](#langkah-3-konfigurasi-jaringan-statis-vm-debian-13-1921687020-via-cli)
4. [Langkah 4: Pembuatan User Pengelola & Hak Sudo via CLI](#langkah-4-pembuatan-user-pengelola--hak-sudo-via-cli)
5. [Langkah 5: Pengerasan Keamanan Server (SSH, UFW Firewall, Fail2ban) via CLI](#langkah-5-pengerasan-keamanan-server-ssh-ufw-firewall-fail2ban-via-cli)
6. [Langkah 6: Instalasi Resmi Docker Engine & Git di Debian 13 via CLI](#langkah-6-instalasi-resmi-docker-engine--git-di-debian-13-via-cli)
7. [Langkah 7: Kloning Proyek & Pembuatan File Environment (.env) Wajib via CLI](#langkah-7-kloning-proyek--pembuatan-file-environment-env-wajib-via-cli)
8. [Langkah 8: Menjalankan & Membangun Kontainer Docker via CLI](#langkah-8-menjalankan--membangun-kontainer-docker-via-cli)
9. [Langkah 9: Konfigurasi DNS Statis di Router MikroTik Kantor via CLI](#langkah-9-konfigurasi-dns-statis-di-router-mikrotik-kantor-via-cli)
10. [Langkah 10: Mengaktifkan Cloudflare Quick Tunnel (HTTPS Publik) via CLI](#langkah-10-mengaktifkan-cloudflare-quick-tunnel-https-publik-via-cli)
11. [Langkah 11: Pengujian & Validasi Sistem (CLI & Browser)](#langkah-11-pengujian--validasi-sistem-cli--browser)
12. [Langkah 12: Pemeliharaan Server, Backup & Monitoring Rutin via CLI](#langkah-12-pemeliharaan-server-backup--monitoring-rutin-via-cli)
13. [Lampiran: Skrip Otomasi Cepat Satu-Klik (`setup_server_security.sh`)](#lampiran-skrip-otomasi-cepat-satu-klik)

---

## Langkah 1: Persiapan Proxmox VE & Pengunduhan ISO Debian 13 via CLI

Anda dapat mengunduh ISO resmi **Debian 13 (Trixie)** langsung dari dalam terminal host Proxmox VE tanpa perlu mengunduhnya manual di browser.

### 1. Masuk ke Shell Proxmox Host
Buka browser ke dashboard Proxmox (`https://192.168.70.10:8006`), klik node Anda (misal: `pve`), lalu klik menu **>_ Shell**. Atau akses via SSH:
```bash
ssh root@192.168.70.10
```

### 2. Unduh ISO Debian 13 (Trixie) Netinst Langsung ke Storage Proxmox:
Jalankan perintah berikut di Shell Proxmox:
```bash
# Pindah ke direktori penyimpanan ISO Proxmox
cd /var/lib/vz/template/iso

# Unduh ISO Debian 13 (Testing/Trixie) Netinst AMD64
wget -c https://cdimage.debian.org/cdimage/weekly-builds/amd64/iso-cd/debian-testing-amd64-netinst.iso -O debian-13-trixie-amd64-netinst.iso

# Verifikasi file ISO telah tersimpan
ls -lh debian-13-trixie-amd64-netinst.iso
```

---

## Langkah 2: Pembuatan Virtual Machine (VM) di Proxmox (CLI & GUI)

Anda dapat membuat VM secara instan melalui **Proxmox CLI** (hanya 1 baris perintah) atau melalui menu GUI Proxmox.

### Opsi A: Pembuatan VM Menggunakan Proxmox CLI (Sangat Direkomendasikan - 5 Detik)
Jalankan perintah berikut langsung di **Shell Proxmox Host**:

```bash
# Buat VM ID 100 dengan spesifikasi 4 Core, 4GB RAM, 32GB SCSI SSD, VirtIO Network
qm create 100 \
  --name laporsar-server \
  --memory 4096 \
  --cores 4 \
  --cpu host \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci \
  --scsi0 local-lvm:32,ssd=1 \
  --cdrom local:iso/debian-13-trixie-amd64-netinst.iso \
  --boot order="scsi0;cdrom" \
  --agent 1 \
  --ostype l26

# Nyalakan VM secara langsung
qm start 100
```

### Opsi B: Pembuatan VM via Web GUI Proxmox
Jika lebih menyukai tampilan web:
1. Klik tombol **Create VM** di pojok kanan atas:
   - **General:** VM ID: `100`, Name: `laporsar-server`.
   - **OS:** Storage: `local`, ISO: `debian-13-trixie-amd64-netinst.iso`.
   - **System:** Qemu Agent: centang `[v]`.
   - **Disks:** Bus: `SCSI`, Storage: `local-lvm`, Disk size: `32 GB` atau `50 GB`, SSD emulation: centang `[v]`.
   - **CPU:** Sockets: `1`, Cores: `4`, Type: `host`.
   - **Memory:** `4096 MB`.
   - **Network:** Bridge: `vmbr0`, Model: `VirtIO (paravirtualized)`.
2. Klik **Finish**, lalu klik tombol **Start**.

### 3. Selesaikan Instalasi Debian 13 di Proxmox Console:
Buka tab **Console** pada VM 100:
- Pilih: **Install** (Text mode atau Graphical Install).
- Bahasa: *English*, Lokasi: *other $\rightarrow$ Asia $\rightarrow$ Indonesia*.
- Hostname: `laporsar-server`, Domain: `lan`.
- Set kata sandi untuk akun `root`.
- Buat user pengelola pertama: `saradmin` beserta kata sandinya.
- Partitioning: *Guided - use entire disk*.
- **Software Selection (PENTING):**
  - **HAPUS CENTANG [ ] Debian desktop environment**
  - **HAPUS CENTANG [ ] GNOME**
  - **CENTANG [v] SSH server**
  - **CENTANG [v] standard system utilities**
- Install GRUB boot loader ke disk utama (`/dev/sda` atau `/dev/vda`).
- Selesai $\rightarrow$ Reboot VM.

---

## Langkah 3: Konfigurasi Jaringan Statis VM Debian 13 (192.168.70.20) via CLI

Pastikan IP address VM terkunci statis ke `192.168.70.20` agar tidak berubah saat router atau server reboot.

Buka **Console** VM di Proxmox, lalu login sebagai `root`:
```bash
su -
```

### 1. Periksa Nama Antarmuka Jaringan Fisik:
```bash
ip -br link
```
*Umumnya antarmuka kartu jaringan bernama `ens18` atau `eth0`.*

### 2. Terapkan Konfigurasi IP Statis:
Di Debian 13, Anda dapat menggunakan standar `systemd-networkd` (modern) atau `/etc/network/interfaces` (`ifupdown`). Pilih salah satu yang aktif:

#### Opsi 1: Menggunakan `systemd-networkd` (Standar Modern Debian 13)
```bash
# 1. Buat direktori konfigurasi
mkdir -p /etc/systemd/network

# 2. Tulis file konfigurasi IP statis
cat << 'EOF' > /etc/systemd/network/10-static-ens18.network
[Match]
Name=ens18

[Network]
Address=192.168.70.20/24
Gateway=192.168.70.1
DNS=192.168.70.1
DNS=8.8.8.8
EOF

# 3. Aktifkan dan jalankan service systemd-networkd & resolved
systemctl enable --now systemd-networkd
systemctl restart systemd-networkd
systemctl enable --now systemd-resolved
```

#### Opsi 2: Menggunakan `/etc/network/interfaces` (`ifupdown` Tradisional)
```bash
cat << 'EOF' > /etc/network/interfaces
source /etc/network/interfaces.d/*

auto lo
iface lo inet loopback

auto ens18
iface ens18 inet static
    address 192.168.70.20
    netmask 255.255.255.0
    gateway 192.168.70.1
    dns-nameservers 192.168.70.1 8.8.8.8
EOF

# Restart layanan jaringan
systemctl restart networking
```

### 3. Verifikasi Konektivitas Jaringan via CLI:
```bash
# Cek IP Address yang aktif
ip addr show ens18

# Cek tabel routing
ip route show

# Cek koneksi ke Gateway MikroTik
ping -c 3 192.168.70.1

# Cek koneksi ke Internet DNS
ping -c 3 8.8.8.8

# Cek resolusi domain internet
ping -c 3 deb.debian.org
```
*Pastikan seluruh perintah ping menghasilkan respons `0% packet loss`.*

Sekarang Anda sudah bisa beralih dari Proxmox Web Console ke terminal SSH favorit Anda (seperti PowerShell, Windows Terminal, atau PuTTY):
```bash
ssh saradmin@192.168.70.20
# atau
ssh root@192.168.70.20
```

---

## Langkah 4: Pembuatan User Pengelola & Hak Sudo via CLI

Menjalankan operasional aplikasi langsung menggunakan user `root` berisiko tinggi. Konfigurasikan user `saradmin` dengan hak `sudo`.

Jalankan perintah berikut di terminal (sebagai `root`):

```bash
# 1. Perbarui daftar repository dan instal sudo beserta paket pendukung
apt update
apt install -y sudo curl wget git htop ca-certificates gnupg lsb-release

# 2. Buat user 'saradmin' (jika belum dibuat saat instalasi ISO)
if ! id "saradmin" &>/dev/null; then
    adduser --gecos "Administrator Lapor SAR" saradmin
fi

# 3. Tambahkan user 'saradmin' ke grup sudo
usermod -aG sudo saradmin

# 4. Verifikasi keanggotaan grup
id saradmin
# Output yang benar: uid=1000(saradmin) gid=1000(saradmin) groups=1000(saradmin),27(sudo)

# 5. Uji hak akses sudo
su - saradmin -c "sudo whoami"
# Masukkan password saradmin -> Output harus menghasilkan: root
```

---

## Langkah 5: Pengerasan Keamanan Server (SSH, UFW Firewall, Fail2ban) via CLI

Terapkan keamanan berlapis (*hardening*) pada Debian 13 agar server aman dari akses tidak sah dan serangan brute-force.

Jalankan seluruh blok perintah berikut (sebagai `root` atau `sudo`):

### 1. Instalasi Utilitas Keamanan:
```bash
apt install -y ufw fail2ban unattended-upgrades iptables
```

### 2. Konfigurasi Keamanan SSH:
Batasi percobaan login SSH dan matikan fitur yang tidak diperlukan:
```bash
mkdir -p /etc/ssh/sshd_config.d
cat << 'EOF' > /etc/ssh/sshd_config.d/99-laporsar-security.conf
# Kebijakan Keamanan SSH Lapor SAR Lite
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
EOF

# Terapkan konfigurasi SSH baru
systemctl restart ssh || systemctl restart sshd
```

### 3. Konfigurasi Firewall UFW (Strict Inbound Filtering):
> [!IMPORTANT]
> **Kebijakan Keamanan Jaringan:**
> Hanya port **22** (SSH), **80** (HTTP Nginx), dan **443** (HTTPS) yang dibuka ke jaringan kantor/LAN.
> Port database PostgreSQL (`5432`), cache Redis (`6379`), backend FastAPI (`8000`), dan frontend Next.js (`3000`) **TIDAK DIBUKA KE LUAR**. Seluruh komunikasi internal dilindungi dalam Docker bridge network.

```bash
# Reset aturan UFW ke default
ufw --force reset

# Kebijakan dasar: Tolak semua koneksi masuk, izinkan semua koneksi keluar
ufw default deny incoming
ufw default allow outgoing

# Buka hanya port operasional resmi:
ufw allow 22/tcp comment 'SSH Remote Management'
ufw allow 80/tcp comment 'Lapor SAR Nginx Reverse Proxy'
ufw allow 443/tcp comment 'HTTPS Secure Tunnel'

# Aktifkan Firewall UFW
echo "y" | ufw enable

# Periksa status firewall
ufw status verbose
```
*Output harus menunjukkan:*
```text
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere                   # SSH Remote Management
80/tcp                     ALLOW IN    Anywhere                   # Lapor SAR Nginx Reverse Proxy
443/tcp                    ALLOW IN    Anywhere                   # HTTPS Secure Tunnel
```

### 4. Konfigurasi Fail2ban (Anti Brute-Force SSH):
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

# Aktifkan dan jalankan Fail2ban
systemctl enable --now fail2ban
systemctl restart fail2ban

# Periksa status proteksi SSH jail
fail2ban-client status sshd
```

---

## Langkah 6: Instalasi Resmi Docker Engine & Git di Debian 13 via CLI

Pasang Docker Engine dan Docker Compose Plugin resmi dari Docker Inc. Skrip ini dirancang khusus dengan deteksi otomatis untuk Debian 13 (Trixie):

```bash
# 1. Bersihkan paket docker lama (jika ada)
apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# 2. Siapkan direktori keyring APT
install -m 0755 -d /etc/apt/keyrings

# 3. Unduh dan simpan GPG Key resmi Docker
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# 4. Deteksi Suite Debian 13 (Trixie) & Forward-Compatibility Fallback
SUITE=$(. /etc/os-release && echo "$VERSION_CODENAME")
if ! curl -fsSL -o /dev/null "https://download.docker.com/linux/debian/dists/${SUITE}/Release"; then
    echo "[INFO] Suite '${SUITE}' belum tersedia di repository Docker, menggunakan fallback binary kompatibel 'bookworm'..."
    SUITE="bookworm"
fi

# 5. Daftarkan repository resmi Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  ${SUITE} stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 6. Pasang paket Docker Engine dan Docker Compose Plugin
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 7. Aktifkan service Docker saat booting
systemctl enable --now docker

# 8. Masukkan user 'saradmin' ke grup 'docker' (agar bisa menjalankan docker tanpa sudo)
usermod -aG docker saradmin

# 9. Verifikasi instalasi Docker via CLI
docker --version
docker compose version
```

---

## Langkah 7: Kloning Proyek & Pembuatan File Environment (.env) Wajib via CLI

Seluruh berkas aplikasi ditempatkan di direktori `/opt/laporsar_lite`.

### 1. Buat Direktori Proyek & Atur Hak Akses:
```bash
# Jalankan sebagai root
mkdir -p /opt/laporsar_lite
chown -R saradmin:docker /opt/laporsar_lite
chmod -R 775 /opt/laporsar_lite
```

### 2. Kloning Repositori dari GitHub:
Beralih ke user `saradmin`:
```bash
su - saradmin
cd /opt/laporsar_lite

# Kloning kode proyek (jika folder masih kosong)
if [ ! -f "docker-compose.yml" ]; then
    git clone https://github.com/Installer09/laporsar_lite.git .
else
    git pull origin main
fi
```

---

### ⚙️ Pembuatan File 1: `.env` Utama (`/opt/laporsar_lite/.env`)
Salin dan jalankan blok perintah CLI ini langsung di terminal untuk membuat file `.env` root secara instan:

```bash
cat << 'EOF' > /opt/laporsar_lite/.env
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
FRONTEND_URL=http://laporsar.lan
NEXT_PUBLIC_API_URL=/api
INTERNAL_BACKEND_URL=http://backend:8000

# 4. PENYIMPANAN BERKAS LOKAL
STORAGE_TYPE=local
LOCAL_STORAGE_DIR=/app/uploads

# 5. PRESET AI MULTI-PROVIDER CLOUD (OPSIONAL)
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
EOF

echo "[OK] File /opt/laporsar_lite/.env berhasil dibuat!"
```

---

### ⚙️ Pembuatan File 2: `.env` Backend (`/opt/laporsar_lite/backend/.env`)
Salin dan jalankan blok perintah CLI ini:

```bash
cat << 'EOF' > /opt/laporsar_lite/backend/.env
# =====================================================================
# LAPOR SAR LITE — BACKEND SERVICE ENVIRONMENT (.env)
# =====================================================================
PROJECT_NAME="Lapor SAR API"
VERSION="3.1.0-lite"

SECRET_KEY=laporsar-lite-secret-key-change-for-production-demo
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

DEV_SUPERADMIN_ENABLED=true
DEV_SUPERADMIN_USERNAME=superadmin
DEV_SUPERADMIN_PASSWORD=superadmin

DEV_ADMIN_ENABLED=true
DEV_ADMIN_USERNAME=admin
DEV_ADMIN_PASSWORD=admin

DATABASE_URL=postgresql+asyncpg://laporsar_admin:laporsar_admin@db:5432/laporsar_master
REDIS_URL=redis://redis:6379/0

FRONTEND_URL=http://laporsar.lan
NEXT_PUBLIC_API_URL=/api
INTERNAL_BACKEND_URL=http://backend:8000

STORAGE_TYPE=local
LOCAL_STORAGE_DIR=/app/uploads
EOF

echo "[OK] File /opt/laporsar_lite/backend/.env berhasil dibuat!"
```

---

### ⚙️ Pembuatan File 3: `.env.production` Frontend (`/opt/laporsar_lite/frontend/.env.production`)
Salin dan jalankan blok perintah CLI ini:

```bash
cat << 'EOF' > /opt/laporsar_lite/frontend/.env.production
# =====================================================================
# LAPOR SAR LITE — FRONTEND PRODUCTION ENVIRONMENT
# =====================================================================
NEXT_PUBLIC_API_URL=/api
INTERNAL_BACKEND_URL=http://backend:8000
EOF

# Buat juga salinan ke .env lokal frontend
cp /opt/laporsar_lite/frontend/.env.production /opt/laporsar_lite/frontend/.env

echo "[OK] File frontend/.env.production dan frontend/.env berhasil dibuat!"
```

---

## Langkah 8: Menjalankan & Membangun Kontainer Docker via CLI

Jalankan perintah ini sebagai user `saradmin` di direktori proyek:

```bash
cd /opt/laporsar_lite

# 1. Hentikan kontainer lama jika sedang aktif
docker compose down

# 2. Bangun ulang (rebuild) image dan jalankan seluruh kontainer di background
docker compose up -d --build
```

### 1. Periksa Status Seluruh Kontainer via CLI:
```bash
docker compose ps
```
Output yang sehat harus menampilkan kelima service dengan status **Up**:
```text
NAME                     IMAGE                       STATUS                    PORTS
laporsar_lite_backend    laporsar_lite-backend       Up                        8000/tcp
laporsar_lite_db         postgis/postgis:16-3.4      Up (healthy)              5432/tcp
laporsar_lite_frontend   laporsar_lite-frontend      Up                        3000/tcp
laporsar_lite_nginx      nginx:alpine                Up                        0.0.0.0:80->80/tcp, [::]:80->80/tcp
laporsar_lite_redis      redis:7-alpine              Up (healthy)              6379/tcp
```

### 2. Uji Respons Server Lokal secara Internal via CLI (`curl`):
```bash
# 1. Uji Nginx Gerbang Depan (Harus mengembalikan HTTP 200)
curl -I http://127.0.0.1/

# 2. Uji REST API Backend melalui Nginx (Harus mengembalikan HTTP 200 OK)
curl -s http://127.0.0.1/api/health

# 3. Uji Detail Endpoint Versi API
curl -s http://127.0.0.1/api/v1/system/info
```

### 3. Memantau Log Kontainer secara Realtime:
```bash
# Pantau log Nginx
docker compose logs -f nginx

# Pantau log FastAPI Backend
docker compose logs -f backend

# Pantau log Next.js Frontend
docker compose logs -f frontend
```
*(Tekan `Ctrl + C` untuk keluar dari pemantauan log)*.

---

## Langkah 9: Konfigurasi DNS Statis di Router MikroTik Kantor via CLI

Agar seluruh perangkat kantor yang mengakses `http://laporsar.lan` atau `http://natuna.laporsar.lan` otomatis diarahkan ke server `192.168.70.20`:

### Eksekusi via Terminal RouterOS MikroTik (CLI):
1. Buka SSH ke MikroTik kantor:
   ```bash
   ssh admin@192.168.70.1
   ```
2. Jalankan dua perintah RouterOS berikut:
   ```routeros
   # 1. Daftarkan Domain Utama Portal Lapor SAR
   /ip dns static add name="laporsar.lan" address=192.168.70.20 ttl=1d comment="Lapor SAR Portal Utama"

   # 2. Daftarkan Regex Wildcard untuk Seluruh Subdomain Tenant Cabang
   /ip dns static add regexp=".*\\.laporsar\\.lan" address=192.168.70.20 ttl=1d comment="Lapor SAR Tenant Regional Wildcard"

   # 3. Verifikasi DNS Static di MikroTik
   /ip dns static print
   ```

---

## Langkah 10: Mengaktifkan Cloudflare Quick Tunnel (HTTPS Publik) via CLI

Cloudflare Quick Tunnel menyediakan URL HTTPS resmi secara cuma-cuma tanpa perlu membuka port (*Port Forwarding*) di router kantor, sehingga fitur PWA (GPS lokasi & Voice Note) dan Webhook WhatsApp/Telegram dapat terhubung.

### 1. Pasang paket `cloudflared` di Debian 13 via CLI:
```bash
# Unduh paket debian 64-bit resmi Cloudflare
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb

# Pasang paket
sudo dpkg -i cloudflared.deb
rm cloudflared.deb

# Verifikasi versi
cloudflared --version
```

### 2. Jalankan Quick Tunnel Mengarah ke Nginx (Port 80):
```bash
cloudflared tunnel --url http://127.0.0.1:80
```
Terminal akan menampilkan output seperti:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:                                          |
|  https://emergency-alert-rescue-xxxx.trycloudflare.com                                    |
+--------------------------------------------------------------------------------------------+
```

### 3. Menjalankan Cloudflared di Background secara Otomatis (Service):
```bash
sudo nohup cloudflared tunnel --url http://127.0.0.1:80 > /var/log/cloudflared.log 2>&1 &

# Tampilkan URL HTTPS aktif:
grep -o 'https://.*\.trycloudflare\.com' /var/log/cloudflared.log | tail -n 1
```

---

## Langkah 11: Pengujian & Validasi Sistem (CLI & Browser)

### 1. Validasi dari Komputer Klien / Operator (CLI Windows/Linux):
Buka terminal/CMD di komputer operator:
```bash
ping laporsar.lan
```
*Pastikan membalas (reply) dari IP `192.168.70.20`.*

### 2. Akses via Browser Web:
1. Buka browser: `http://laporsar.lan`
2. Halaman portal **Lapor SAR** akan langsung tampil lengkap dengan peta dan tombol layanan darurat.
3. Klik **Masuk Petugas** $\rightarrow$ Masukkan akun operator cabang Natuna:
   - **Username:** `natuna` *(atau `admin.natuna@basarnas.go.id`)*
   - **Password:** `admin`
4. Dashboard **Kantor SAR Natuna** akan memuat data alutsista lokal:
   - *KN SASIKIRANA 245*, *RIB 01 Natuna*
   - *Pos SAR Anambas*, *Unit Siaga Serasan*, *Unit Siaga Subi*.
   - WebSocket Live connected di header menyala hijau.

---

## Langkah 12: Pemeliharaan Server, Backup & Monitoring Rutin via CLI

### 1. Backup Otomatis Database PostgreSQL via CLI:
```bash
# Backup Master Database
docker exec -t laporsar_lite_db pg_dump -U laporsar_admin -d laporsar_master > /opt/backup_master_$(date +%F).sql

# Backup Tenant Natuna Database
docker exec -t laporsar_lite_db pg_dump -U laporsar_admin -d laporsar_natuna > /opt/backup_natuna_$(date +%F).sql

# Cek hasil backup
ls -lh /opt/backup_*.sql
```

### 2. Jadwalkan Backup Harian Otomatis via Crontab:
```bash
# Buka crontab
sudo crontab -e
```
Tambahkan baris berikut di akhir file (berjalan setiap pukul 02:00 pagi):
```text
0 2 * * * docker exec -t laporsar_lite_db pg_dump -U laporsar_admin -d laporsar_master > /opt/backup_master_$(date +\%F).sql 2>&1
0 2 * * * docker exec -t laporsar_lite_db pg_dump -U laporsar_admin -d laporsar_natuna > /opt/backup_natuna_$(date +\%F).sql 2>&1
```

### 3. Pembersihan Cache Docker & Monitoring Kapasitas Disk:
```bash
# Bersihkan dangling images & cache build
docker system prune -f

# Periksa penggunaan ruang harddisk
df -h /
```

---

## Lampiran: Skrip Otomasi Cepat Satu-Klik (`setup_server_security.sh`)

Untuk mempercepat instalasi seluruh paket, pembuatan user `saradmin`, firewall, fail2ban, dan Docker di Debian 13 baru:

```bash
# 1. Jalankan langsung sebagai root di server Debian 13:
cd /opt/laporsar_lite
sudo bash scripts/setup_server_security.sh
```

Skrip ini akan secara otomatis:
1. Memperbarui seluruh paket sistem Debian 13 (Trixie).
2. Membuat user `saradmin` dengan hak `sudo` dan shell bash.
3. Mengonfigurasi hardening SSH (`MaxAuthTries 3`).
4. Mengonfigurasi UFW Firewall (hanya port 22, 80, 443 yang dibuka).
5. Memasang dan mengaktifkan Fail2ban.
6. Memasang Docker Engine resmi beserta Docker Compose Plugin (dengan suite fallback cerdas).
7. Memasukkan `saradmin` ke grup `docker`.
8. Menyiapkan hak kepemilikan folder `/opt/laporsar_lite`.
