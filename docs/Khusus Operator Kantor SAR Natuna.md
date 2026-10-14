# 🚀 Panduan Eksekusi & Walkthrough: Lapor SAR Lite di Server Lokal (`laporsar.lan`)

Sistem Lapor SAR Lite telah berhasil dikonfigurasi untuk berjalan di dedicated server lokal Anda (**IP: `192.168.70.20`**) dengan domain intranet **`http://laporsar.lan`**, mendukung penuh **Multi-Tenant Kantor SAR Natuna**.

---

## 🧭 Langkah 1: Pengaturan DNS Statis di Router MikroTik Kantor

Agar seluruh PC di kantor mengenali `laporsar.lan` dan subdomain cabang seperti `natuna.laporsar.lan` mengarah ke Server `192.168.70.20`:

### Opsi A: Via Terminal MikroTik (CLI - Sangat Disarankan)
Cukup jalankan dua baris ini di **New Terminal** Winbox / SSH MikroTik:
```routeros
/ip dns static add name="laporsar.lan" address=192.168.70.20 ttl=1d comment="Lapor SAR Pusat"
/ip dns static add regexp=".*\\.laporsar\\.lan" address=192.168.70.20 ttl=1d comment="Lapor SAR Cabang (Natuna, dll)"
```
*(Perintah kedua menggunakan `regexp` sehingga otomatis mendukung seluruh nama cabang seperti `natuna.laporsar.lan` tanpa perlu ditambahkan satu per satu).*

### Opsi B: Via Winbox (GUI)
1. Buka Winbox dan login ke router MikroTik.
2. Buka menu **IP** $\rightarrow$ **DNS** $\rightarrow$ tombol **Static**.
3. Klik ikon tambah **[ + ]**:
   - **Name**: `laporsar.lan`
   - **Type**: `A`
   - **Address**: `192.168.70.20`
   - **TTL**: `1d`
4. Tambahkan satu lagi untuk cabang Natuna:
   - **Name**: `natuna.laporsar.lan`
   - **Type**: `A`
   - **Address**: `192.168.70.20`
   - **TTL**: `1d`
5. Klik **Apply** lalu **OK**.

---

## 🚀 Langkah 2: Menjalankan Layanan di Mesin Server

Di mesin server (`192.168.70.20`), buka Terminal di folder proyek `Lapor SAR Lite`:

```bash
docker compose up -d --build
```

Periksa status kelima kontainer:
```bash
docker compose ps
```
Semua kontainer harus berstatus `running` / `healthy`:
- `laporsar_lite_nginx` (Port 80)
- `laporsar_lite_frontend` (Port 3000)
- `laporsar_lite_backend` (Port 8000)
- `laporsar_lite_db` (Port 5432)
- `laporsar_lite_redis` (Port 6379)

---

## 🌊 Cara Masuk (Login) Khusus Operator Kantor SAR Natuna

Ada **2 cara mudah** bagi operator Natuna untuk masuk ke dashboard:

### Cara 1: Masuk Lewat Domain Utama `http://laporsar.lan` (Paling Praktis)
1. Buka browser: **`http://laporsar.lan`**
2. Di halaman login, masukkan kredensial operator Natuna:
   - **Username**: `natuna` *(atau `admin.natuna@basarnas.go.id`)*
   - **Password**: `admin`
3. Sistem secara cerdas mendeteksi akun tersebut terdaftar di wilayah **Kantor SAR Natuna**:
   - Database otomatis diarahkan ke `laporsar_tenant_natuna`.
   - Peta operasi otomatis fokus ke wilayah **Ranai, Kepulauan Anambas, Serasan, Subi**.
   - Pos SAR & Alutsista yang tampil adalah milik Natuna (KN SASIKIRANA 245, RIB 01 Natuna, D-Max Rescue).

---

### Cara 2: Akses Langsung Subdomain Khusus `http://natuna.laporsar.lan`
1. Buka browser: **`http://natuna.laporsar.lan`**
2. Halaman langsung bertuliskan ruang kerja **Kantor SAR Natuna**.
3. Login dengan akun operator Natuna (`natuna` / `admin`).

---

### 🔑 Daftar Kredensial Login Sistem

| Level Akses / Wilayah | Username | Password | Database yang Digunakan |
| :--- | :--- | :--- | :--- |
| **Operator SAR Natuna** 🏝️ | `natuna`<br>*(atau `admin.natuna@basarnas.go.id`)* | `admin` | `laporsar_tenant_natuna` *(Terisolasi untuk Natuna saja)* |
| **Pusat / Command Center** 🏢 | `admin` | `admin` | `laporsar_master` *(Pusat)* |
| **Super Admin Global** 👑 | `superadmin` | `superadmin` | Akses seluruh sistem & monitoring nasional |

---

## ☁️ Langkah 4: Menghubungkan Webhook WhatsApp (Meta) & Telegram

Agar Meta WhatsApp Cloud API dan Telegram dapat mengirim pesan darurat masyarakat ke server lokal Anda:

1. **Jalankan Cloudflare Tunnel di Server Lokal:**
   ```bash
   cloudflared tunnel --url http://127.0.0.1:80
   ```
   Terminal akan menampilkan tautan HTTPS sementara, contoh:
   `https://emergency-sar-xxxx.trycloudflare.com`

2. **Daftarkan Webhook WhatsApp (Meta Developer Console):**
   - **Callback URL:** `https://emergency-sar-xxxx.trycloudflare.com/api/whatsapp/webhook`
   - **Verify Token:** `SARBOT_VERIFY_TOKEN` (sesuai `.env`)
   - Centang subscription: `messages`

3. **Daftarkan Webhook Telegram Bot untuk Natuna:**
   Cukup buka tautan ini di browser:
   `https://api.telegram.org/bot<TOKEN_BOT_ANDA>/setWebhook?url=https://emergency-sar-xxxx.trycloudflare.com/api/telegram/webhook/natuna`
   *(Ganti `/pusat` menjadi `/natuna` agar setiap laporan dari Telegram langsung masuk ke database Kantor SAR Natuna).*
