@echo off
setlocal enabledelayedexpansion

echo ====================================================================
echo               LAPOR SAR LITE — DEMO & PITCHING RUNNER
echo ====================================================================
echo.

:: 1. Cek file .env
if not exist .env (
    echo [INFO] Berkas .env tidak ditemukan. Menyalin dari .env.example...
    copy .env.example .env >nul
    echo [PERHATIAN] Harap edit .env dan isi API Key AI Anda jika diperlukan.
    echo.
)

:: 2. Cek Docker
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker tidak ditemukan! Harap instal dan jalankan Docker Desktop terlebih dahulu.
    pause
    exit /b 1
)

:: 3. Jalankan Kontainer Docker
echo [1/3] Menjalankan layanan kontainer (PostGIS, Redis, Backend, Frontend)...
docker compose up -d --remove-orphans

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Gagal menjalankan Docker Compose. Periksa apakah Docker Desktop aktif.
    pause
    exit /b 1
)

echo [OK] Seluruh kontainer berhasil dijalankan!
echo.
echo Menunggu inisialisasi database dan backend (5 detik)...
timeout /t 5 /nobreak >nul

:: 4. Cek cloudflared
where cloudflared >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [PERHATIAN] cloudflared belum terinstal di sistem.
    echo Anda dapat menginstalnya via PowerShell: winget install Cloudflare.cloudflared
    echo Atau akses manual di browser lokal: http://localhost:3000
    echo.
    echo Dashboard Operator: http://localhost:3000 (User: admin / Pass: admin)
    echo Portal Pelapor HP:  http://localhost:3000/chat
    echo Penyimpanan Berkas: http://localhost:3000/storage
    echo.
    pause
    exit /b 0
)

:: 5. Jalankan Cloudflare Quick Tunnel
echo [2/3] Membuka terowongan aman Cloudflare Quick Tunnel ke Port 3000...
echo.
echo ====================================================================
echo   SALIN TAUTAN *.trycloudflare.com DI BAWAH INI UNTUK PRESENTASI:
echo ====================================================================
echo.

cloudflared tunnel --url http://localhost:3000

pause
