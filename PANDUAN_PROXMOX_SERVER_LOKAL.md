# 📘 PANDUAN PENERAPAN KHUSUS SERVER LOKAL LAPOR SAR LITE
### *Spesifikasi Kasus: Proxmox VE, VM Debian/Ubuntu (192.168.70.20), MikroTik Static DNS (laporsar.lan), Nginx Reverse Proxy, & Cloudflare Quick Tunnel*

Panduan ini disusun secara berurutan (*step-by-step*) khusus untuk skenario penerapan mandiri di server lokal Anda saat ini.

---

## 📌 RANGKUMAN SPESIFIKASI SISTEM
- **Hypervisor Host:** Proxmox Virtual Environment (VE)
- **Guest OS (Virtual Machine):** Debian 12 (Bookworm) / Ubuntu 22.04 LTS Server
- **IP Address VM Server:** `192.168.70.20/24` (Gateway: IP Router MikroTik, misal `192.168.70.1`)
- **Domain Intranet:** `http://laporsar.lan` (dan `http://natuna.laporsar.lan`)
- **Reverse Proxy:** Nginx (Port 80)
- **Akses Publik HTTPS (Chatbot/Webhook):** Cloudflare Quick Tunnel (`cloudflared`)
- **Tenant Target:** Kantor SAR Natuna (`natuna`)

---

## 📑 DAFTAR LANGKAH IMPLEMENTASI
1. [Langkah 1: Instalasi & Persiapan Proxmox VE](#langkah-1-instalasi--persiapan-proxmox-ve)
2. [Langkah 2: Pembuatan Virtual Machine (VM) di Proxmox](#langkah-2-pembuatan-virtual-machine-vm-di-proxmox)
3. [Langkah 3: Konfigurasi Jaringan Statis VM (192.168.70.20)](#langkah-3-konfigurasi-jaringan-statis-vm-1921687020)
4. [Langkah 4: Instalasi Docker Engine & Git di VM](#langkah-4-instalasi-docker-engine--git-di-vm)
5. [Langkah 5: Transfer / Kloning Proyek Lapor SAR Lite](#langkah-5-transfer--kloning-proyek-lapor-sar-lite)
6. [Langkah 6: Menjalankan Kontainer Lapor SAR & Nginx](#langkah-6-menjalankan-kontainer-lapor-sar--nginx)
7. [Langkah 7: Konfigurasi DNS Statis di Router MikroTik Kantor](#langkah-7-konfigurasi-dns-statis-di-router-mikrotik-kantor)
8. [Langkah 8: Mengaktifkan Cloudflare Quick Tunnel (HTTPS Publik)](#langkah-8-mengaktifkan-cloudflare-quick-tunnel-https-publik)
9. [Langkah 9: Verifikasi & Login Operator Kantor SAR Natuna](#langkah-9-verifikasi--login-operator-kantor-sar-natuna)

---

## Langkah 1: Instalasi & Persiapan Proxmox VE

Jika mesin fisik server Anda belum terpasang Proxmox VE:
1. Unduh installer ISO resmi **Proxmox VE (versi 8.x)** dari [proxmox.com/en/downloads](https://www.proxmox.com/en/downloads).
2. Buat USB Bootable menggunakan aplikasi **Rufus** (pilih mode *DD Image*) atau **Ventoy**.
3. Pasang USB ke PC Server, nyalakan, lalu masuk ke BIOS/UEFI (tekan `F2` / `Del` / `F12`):
   - Pastikan fitur **Intel VT-x** atau **AMD-V (Virtualization)** dalam posisi **Enabled**.
   - Atur booting prioritas ke USB.
4. Pilih **Install Proxmox VE (Graphical)**:
   - Pilih harddisk/SSD target instalasi.
   - Atur Negara: `Indonesia`, Timezone: `Asia/Jakarta`.
   - Masukkan password akun `root` dan email administrator Anda.
   - **Konfigurasi IP Management Proxmox:**
     - Interface: Pilih kartu LAN fisik utama (misal `eno1` atau `eth0`).
     - Hostname: `pve-sar.local`
     - IP Address (CIDR): `192.168.70.10/24` *(beri IP yang berbeda dengan VM Lapor SAR)*
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
   - Klik **Upload**, lalu unggah ISO **Debian 12 Netinst** atau **Ubuntu 22.04 Live Server**.
2. **Buat Virtual Machine Baru:**
   - Klik tombol biru **Create VM** di pojok kanan atas Proxmox:
     - **General:** VM ID: `100`, Name: `laporsar-server`.
     - **OS:** Pilih ISO Debian/Ubuntu yang baru diunggah.
     - **System:** Biarkan default (Qemu Agent: centang `[v]`).
     - **Disks:** Ukuran disk: minimal `32 GB` atau `50 GB` (tipe SSD/NVMe).
     - **CPU:** Sockets: `1`, Cores: `2` atau `4` core.
     - **Memory:** `4096 MB` (4 GB RAM disarankan, minimal 2 GB).
     - **Network:** Bridge: `vmbr0`, Model: `VirtIO (paravirtualized)`.
3. Klik **Finish**, lalu klik kanan VM `100 (laporsar-server)` $\rightarrow$ klik **Start**.
4. Buka tab **Console**, lalu selesaikan instalasi Debian/Ubuntu:
   - Buat user biasa (misal: `saradmin`) dan password.
   - Saat pemilihan paket (*Software Selection*):
     - **Hilangkan centang Desktop Environment (GNOME/XFCE)** agar server ringan.
     - **Centang:** `SSH server` dan `standard system utilities`.

---

## Langkah 3: Konfigurasi Jaringan Statis VM (192.168.70.20)

Setelah instalasi OS di VM selesai, pastikan IP mesin VM terkunci secara statis ke `192.168.70.20`.

1. Buka console VM di Proxmox (atau via SSH jika sudah terhubung).
2. Login sebagai `root`:
   ```bash
   su -
   ```
3. Edit konfigurasi antarmuka jaringan:
   - **Jika menggunakan Debian:**
     ```bash
     nano /etc/network/interfaces
     ```
     Ubah konfigurasi interface (misal `ens18` atau `eth0`) menjadi seperti berikut:
     ```text
     auto ens18
     iface ens18 inet static
         address 192.168.70.20
         netmask 255.255.255.0
         gateway 192.168.70.1
         dns-nameservers 192.168.70.1 8.8.8.8
     ```
     Simpan dengan `Ctrl + O`, `Enter`, lalu keluar dengan `Ctrl + X`.
     Terapkan konfigurasi:
     ```bash
     systemctl restart networking
     ```

   - **Jika menggunakan Ubuntu Server (Netplan):**
     ```bash
     nano /etc/netplan/00-installer-config.yaml
     ```
     Sesuaikan isinya:
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
     Terapkan konfigurasi:
     ```bash
     netplan apply
     ```

4. Uji koneksi internet dari VM:
   ```bash
   ping -c 3 8.8.8.8
   ```
   *(Harus menghasilkan balasan / reply).*

---

## Langkah 4: Instalasi Docker Engine & Git di VM

Jalankan perintah berikut di terminal VM untuk memasang Docker resmi:

```bash
# 1. Update paket dan pasang utilitas dasar
apt update && apt upgrade -y
apt install -y curl wget git htop ca-certificates gnupg lsb-release

# 2. Daftarkan GPG Key resmi Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Daftarkan repositori Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Pasang Docker Engine dan Docker Compose Plugin
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. Pastikan Docker otomatis hidup saat server reboot
systemctl enable --now docker
docker --version
docker compose version
```

---

## Langkah 5: Transfer / Kloning Proyek Lapor SAR Lite

Letakkan folder proyek di `/opt/laporsar_lite`:

### Opsi A: Transfer dari PC Anda via SCP (PowerShell)
Buka PowerShell di PC tempat source code ini berada:
```powershell
scp -r "D:\Project Digitalisasi\Lapor SAR Lite" root@192.168.70.20:/opt/laporsar_lite
```

### Opsi B: Kloning langsung dari Git di VM
```bash
git clone https://github.com/Installer09/laporsar_lite.git /opt/laporsar_lite
cd /opt/laporsar_lite
```

Pastikan berkas `.env` telah disesuaikan:
```bash
cd /opt/laporsar_lite
nano .env
```
Pastikan variabel `FRONTEND_URL` berisi:
```env
FRONTEND_URL=http://laporsar.lan
```

---

## Langkah 6: Menjalankan Kontainer Lapor SAR & Nginx

Di dalam folder `/opt/laporsar_lite` pada VM, jalankan seluruh kontainer:

```bash
cd /opt/laporsar_lite
docker compose up -d --build
```

Periksa apakah seluruh kontainer aktif:
```bash
docker compose ps
```
Output harus menunjukkan kelima kontainer berstatus **Up / healthy**:
- `laporsar_lite_nginx` (Port 80) $\rightarrow$ Gerbang utama Nginx Reverse Proxy
- `laporsar_lite_frontend` (Port 3000) $\rightarrow$ Next.js Web Dashboard & PWA
- `laporsar_lite_backend` (Port 8000) $\rightarrow$ FastAPI Engine & WebSocket
- `laporsar_lite_db` (Port 5432) $\rightarrow$ PostgreSQL 16 + PostGIS
- `laporsar_lite_redis` (Port 6379) $\rightarrow$ Redis Caching

---

## Langkah 7: Konfigurasi DNS Statis di Router MikroTik Kantor

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
5. Tambahkan satu entri lagi untuk subdomain cabang Natuna:
   - **Name:** `natuna.laporsar.lan`
   - **Address:** `192.168.70.20`
   - **TTL:** `1d`
   - Klik **Apply** $\rightarrow$ **OK**.

---

## Langkah 8: Mengaktifkan Cloudflare Quick Tunnel (HTTPS Publik)

Cloudflare Quick Tunnel digunakan untuk memancarkan alamat HTTPS publik resmi secara instan agar:
- Fitur PWA (Mikrofon Voice Note & GPS) dapat diuji di HP dengan standar keamanan peramban.
- Webhook WhatsApp Meta dan Telegram Bot dari internet dapat masuk ke server lokal.

### 1. Pasang `cloudflared` di VM Server:
Jalankan di terminal VM:
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i cloudflared.deb
rm cloudflared.deb
```

### 2. Jalankan Quick Tunnel Mengarah ke Nginx (Port 80):
```bash
cloudflared tunnel --url http://127.0.0.1:80
```

Terminal akan menampilkan URL publik acak berprotokol HTTPS, contoh:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:                                          |
|  https://emergency-alert-rescue-xxxx.trycloudflare.com                                    |
+--------------------------------------------------------------------------------------------+
```

### 3. Hubungkan ke Bot Laporan (Opsional):
- **WhatsApp Meta Cloud API:**  
  Masukkan Callback URL di Meta Dashboard:  
  `https://emergency-alert-rescue-xxxx.trycloudflare.com/api/whatsapp/webhook`
- **Telegram Bot (Kantor SAR Natuna):**  
  Buka URL berikut di browser PC Anda:  
  `https://api.telegram.org/bot<TOKEN_BOT_ANDA>/setWebhook?url=https://emergency-alert-rescue-xxxx.trycloudflare.com/api/telegram/webhook/natuna`

---

## Langkah 9: Verifikasi & Login Operator Kantor SAR Natuna

### 1. Uji Koneksi DNS dari PC Operator
Buka Command Prompt (CMD) di laptop/PC operator yang terhubung ke WiFi/LAN kantor:
```cmd
ping laporsar.lan
```
*Pastikan membalas dari IP `192.168.70.20`.*

### 2. Membuka Dashboard Lapor SAR
Buka browser (Google Chrome / Microsoft Edge), akses:
```text
http://laporsar.lan
```
*(Atau langsung ke `http://natuna.laporsar.lan`)*

### 3. Login Operator Kantor SAR Natuna
Masukkan data login:
- **Username:** `natuna` *(atau `admin.natuna@basarnas.go.id`)*
- **Password:** `admin`

### 4. Hasil Verifikasi:
- Dashboard langsung bertuliskan ruang kerja **Kantor SAR Natuna**.
- Peta operasi langsung berfokus pada wilayah perairan **Ranai, Kepulauan Anambas, Serasan, dan Subi**.
- Daftar alutsista dan pos yang tampil meliputi:
  - **KN SASIKIRANA 245** & **RIB 01 Natuna**
  - **Pos SAR Anambas** (Tarempa)
  - **Unit Siaga SAR Serasan**
  - **Unit Siaga SAR Subi**
- Indikator status live WebSocket di pojok atas menyala hijau (**Live Real-time Connected**).
