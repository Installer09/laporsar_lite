#!/usr/bin/env bash
# ==============================================================================
# SKRIP OTOMATIS KONFIGURASI SERVER, USER & KEAMANAN LAPOR SAR LITE
# Target OS: Debian 13 (Trixie) / Debian 12 (Bookworm) / Ubuntu 24.04/22.04 LTS
# ==============================================================================
set -euo pipefail

# Warna terminal untuk output informatif
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}     SKRIP SETUP SERVER, USER & KEAMANAN MANDIRI — LAPOR SAR LITE            ${NC}"
echo -e "${BLUE}==============================================================================${NC}"

# 1. Verifikasi hak akses root
if [ "${EUID}" -ne 0 ]; then
    echo -e "${RED}[ERROR] Skrip ini harus dijalankan sebagai root (gunakan 'su -' atau 'sudo bash').${NC}"
    exit 1
fi

TARGET_USER="saradmin"
PROJECT_DIR="/opt/laporsar_lite"

# 2. Update repository dan pasang paket dasar
echo -e "\n${YELLOW}[1/7] Memperbarui sistem dan menginstal paket penting...${NC}"
apt update && apt upgrade -y
apt install -y \
    sudo curl wget git htop ca-certificates gnupg lsb-release \
    ufw fail2ban unattended-upgrades

# 3. Manajemen User Pengelola (User Non-Root)
echo -e "\n${YELLOW}[2/7] Mengonfigurasi user pengelola '${TARGET_USER}'...${NC}"
if id "${TARGET_USER}" &>/dev/null; then
    echo -e "${GREEN}[OK] User '${TARGET_USER}' sudah ada.${NC}"
else
    useradd -m -s /bin/bash -c "Administrator Lapor SAR" "${TARGET_USER}"
    echo -e "${YELLOW}Masukkan kata sandi baru untuk user '${TARGET_USER}':${NC}"
    passwd "${TARGET_USER}"
    echo -e "${GREEN}[OK] User '${TARGET_USER}' berhasil dibuat.${NC}"
fi

# Masukkan user ke grup sudo
usermod -aG sudo "${TARGET_USER}"

# 4. Pengerasan Keamanan SSH
echo -e "\n${YELLOW}[3/7] Mengonfigurasi keamanan SSH...${NC}"
SSH_SECURITY_FILE="/etc/ssh/sshd_config.d/99-laporsar-security.conf"
mkdir -p /etc/ssh/sshd_config.d
cat << 'EOF' > "${SSH_SECURITY_FILE}"
# Keamanan SSH Lapor SAR Lite
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
X11Forwarding no
EOF

# Restart SSH daemon secara aman
if systemctl is-active --quiet sshd; then
    systemctl restart sshd
elif systemctl is-active --quiet ssh; then
    systemctl restart ssh
fi
echo -e "${GREEN}[OK] Kebijakan keamanan SSH berhasil diterapkan.${NC}"

# 5. Konfigurasi Firewall UFW
echo -e "\n${YELLOW}[4/7] Mengonfigurasi UFW Firewall...${NC}"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# Port yang wajib dibuka:
# - Port 22/tcp  : Administrasi SSH
# - Port 80/tcp  : Nginx Reverse Proxy (Gerbang Utama Intranet/LAN)
# - Port 443/tcp : HTTPS (Jika menggunakan sertifikat/tunnel publik)
ufw allow 22/tcp comment 'SSH Remote Admin'
ufw allow 80/tcp comment 'Lapor SAR Nginx HTTP'
ufw allow 443/tcp comment 'Lapor SAR HTTPS'

# CATATAN: Port PostgreSQL (5432), Redis (6379), FastAPI (8000), dan Next.js (3000)
# SENGAJA TIDAK DIBUKA ke publik/LAN demi keamanan. Komunikasi antar kontainer
# berjalan melalui Docker bridge network internal (laporsar_lite_network).

echo "y" | ufw enable
echo -e "${GREEN}[OK] UFW Firewall aktif dengan proteksi port internal.${NC}"

# 6. Konfigurasi Fail2ban (Proteksi Brute-Force)
echo -e "\n${YELLOW}[5/7] Mengonfigurasi Fail2ban untuk proteksi Brute-Force...${NC}"
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
echo -e "${GREEN}[OK] Fail2ban aktif memantau percobaan login mencurigakan.${NC}"

# 7. Instalasi Resmi Docker Engine & Compose
echo -e "\n${YELLOW}[6/7] Menginstal Docker Engine & Docker Compose Plugin...${NC}"
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
fi

OS_ID=$(. /etc/os-release && echo "$ID")
OS_CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")

# Debian 13 (Trixie) & Forward-Compatibility Suite Detection
DOCKER_CODENAME="${OS_CODENAME}"
if ! curl -fsSL -o /dev/null "https://download.docker.com/linux/${OS_ID}/dists/${DOCKER_CODENAME}/Release"; then
    echo -e "${YELLOW}[INFO] Repositori Docker resmi untuk '${DOCKER_CODENAME}' belum aktif, menggunakan fallback binary kompatibel 'bookworm'...${NC}"
    DOCKER_CODENAME="bookworm"
fi

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${OS_ID} \
  ${DOCKER_CODENAME} stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
usermod -aG docker "${TARGET_USER}"
echo -e "${GREEN}[OK] Docker Engine & Compose berhasil diinstal.${NC}"

# 8. Persiapan Direktori Proyek
echo -e "\n${YELLOW}[7/7] Menyiapkan direktori proyek di ${PROJECT_DIR}...${NC}"
mkdir -p "${PROJECT_DIR}"
chown -R "${TARGET_USER}:docker" "${PROJECT_DIR}"
chmod -R 775 "${PROJECT_DIR}"

echo -e "\n${GREEN}==============================================================================${NC}"
echo -e "${GREEN}  KONFIGURASI SERVER & KEAMANAN SELESAI DENGAN SUKSES!                        ${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo -e "Informasi Konfigurasi:"
echo -e " - User Pengelola : ${YELLOW}${TARGET_USER}${NC} (Grup: sudo, docker)"
echo -e " - Direktori Kerja: ${YELLOW}${PROJECT_DIR}${NC}"
echo -e " - Firewall       : ${GREEN}Aktif${NC} (Port terbuka: 22, 80, 443)"
echo -e " - Fail2ban       : ${GREEN}Aktif${NC} (Proteksi SSH)"
echo -e " - Docker         : ${GREEN}Siap digunakan tanpa sudo${NC}"
echo -e "\nLangkah selanjutnya:"
echo -e " 1. Login sebagai user: ${YELLOW}su - ${TARGET_USER}${NC}"
echo -e " 2. Kloning proyek     : ${YELLOW}git clone https://github.com/Installer09/laporsar_lite.git ${PROJECT_DIR}${NC}"
echo -e " 3. Ikuti panduan pembuatan file .env di PANDUAN_PROXMOX_SERVER_LOKAL.md"
echo -e "==============================================================================\n"
