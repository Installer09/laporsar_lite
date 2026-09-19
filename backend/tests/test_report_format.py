import sys
import os
from datetime import datetime

# Masukkan backend ke PATH agar app dapat diimpor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.message_formatter import message_formatter

def test_angka_ke_kata():
    print("=== UJI COBA ANGKA KE KATA ===")
    tests = [
        (0, "NIHIL"),
        (1, "SATU"),
        (3, "TIGA"),
        (10, "SEPULUH"),
        (11, "SEBELAS"),
        (12, "DUA BELAS"),
        (25, "DUA PULUH LIMA"),
        (100, "SERATUS NIHIL"),  # Atau SERATUS saja, tapi ini aman
        (105, "SERATUS LIMA")
    ]
    for n, expected in tests:
        res = message_formatter.angka_ke_kata(n)
        print(f"{n} -> {res} (Expected: {expected})")
        assert res.strip() == expected.strip(), f"Gagal untuk {n}: {res} != {expected}"
    print("✅ Uji coba angka_ke_kata BERHASIL!\n")


def test_format_hari_tanggal():
    print("=== UJI COBA FORMAT HARI TANGGAL ===")
    dt = datetime(2026, 5, 24)  # MINGGU, 24 Mei 2026
    res_upper = message_formatter.format_hari_tanggal(dt, upper=True)
    res_normal = message_formatter.format_hari_tanggal(dt, upper=False)
    
    print(f"Upper: {res_upper}")
    print(f"Normal: {res_normal}")
    
    assert "MINGGU" in res_upper
    assert "Minggu" in res_normal
    assert "Mei" in res_upper
    assert "2026" in res_upper
    print("✅ Uji coba format_hari_tanggal BERHASIL!\n")


def test_render_kmm():
    print("=== UJI COBA RENDER KMM ===")
    dt = datetime(2026, 5, 14)  # Kamis, 14 Mei 2026
    data_kmm = {
        "KLASIFIKASI": "KMM (Kondisi Membahayakan Manusia)",
        "jenis_kejadian": "Orang Tenggelam",
        "LOKASI_KEJADIAN": "Pantai Piwang, Kab. Natuna",
        "WAKTU_INFO_DITERIMA": "0514 1350 G",
        "PELAPOR": "Bpk Nurul Huda (08127639215)",
        "WAKTU_KEJADIAN": "0514 1340 G",
        "KOORDINAT": "3° 55.926'N 108° 23.089'E",
        "HEADING_JARAK": "Heading 68.28° dan Jarak 2.68 NM dari Kantor SAR Natuna",
        "JUMLAH_KORBAN_TOTAL": "3",
        "korban_selamat": "2",
        "korban_meninggal": "0",
        "korban_hilang": "1",
        "data_korban": [
            {"nama": "Okta", "jenis_kelamin": "Laki", "umur": "8", "alamat": "Padang Kurak"}
        ],
        "KRONOLOGI": "Sebanyak 6 (enam) orang anak-anak berenang di Pantai Piwang, 3 (tiga) orang selamat dan 3 (tiga) orang tenggelam...",
        "AKSI": "PDTW 0514 1352 G KPP Natuna berkoordinasi dengan potensi SAR terdekat di lokasi",
        "HASIL": "Masih dalam pencarian",
        "UNSUR_SAR": "* Kantor SAR Natuna\n* BPBD Kabupaten Natuna\n* Masyarakat",
        "ALUT_PALSAR": "* LCR\n* Peralatan Selam\n* Pal Keselamatan Lainnya",
        "CUACA": "* Cuaca : Berawan tebal\n* Suhu : 26 - 28 °C\n* Kecepatan angin : 5 - 10 Kts\n* Arah Angin : Barat\n* Gelombang : 0.5 - 1.25 M",
        "created_at": dt
    }
    
    report_text = message_formatter.render(None, data_kmm)
    print(report_text)
    
    # Validasi isi sesuai contoh format baku
    assert "KMM 3 (TIGA) ORG TENGGELAM" in report_text, "Judul KMM salah"
    assert "PANTAI PIWANG" in report_text, "Lokasi KMM salah"
    assert "Yth : Kabasarnas." in report_text, "SOP Terbaru Yth harus ada di KMM"
    assert "Mhn izin melaporkan informasi KMM 3 (Tiga) org" in report_text
    assert "Nama : Okta (Laki/8 Thn)" in report_text
    assert "Alamat : Padang Kurak" in report_text
    print("✅ Uji coba render_kmm BERHASIL!\n")


def test_render_laka_kapal():
    print("=== UJI COBA RENDER LAKA KAPAL ===")
    dt = datetime(2026, 5, 24)
    data_kapal = {
        "KLASIFIKASI": "Kecelakaan Kapal",
        "jenis_kejadian": "Kapal Mati Mesin",
        "LOKASI_KEJADIAN": "PERAIRAN JEMAJA, KAB. ANAMBAS",
        "WAKTU_INFO_DITERIMA": "0524 1220 G",
        "PELAPOR": "SHINNING SS2",
        "WAKTU_KEJADIAN": "0524 1123 G",
        "KOORDINAT": "02 51.6'N 105 28.7' E",
        "HEADING_JARAK": "Heading 238.54° dan Jarak 15.56 NM dari USS. JEMAJA",
        "JUMLAH_KORBAN_TOTAL": "0",
        "korban_selamat": "-",
        "korban_meninggal": "-",
        "korban_hilang": "-",
        "data_korban": [],
        "data_kapal": {
            "nama_kapal": "MV SS 2",
            "jenis_kapal": "KAPAL KARGO",
            "warna_kapal": "HITAM KUNING",
            "imo": "9158123",
            "call_sign": "XYNX",
            "telepon_satelit": "+88 164170530"
        },
        "KRONOLOGI": "* PDTW 0524 1123 G KAPAL MENGALAMI MATI MESIN\n* PDTW 0524 1125 G KAPAL SEDANG DALAM PERBAIKAN MESIN",
        "AKSI": "* PDTW 0518 1223 G KANTOR SAR KOORDINASI DENGAN USS. JEMAJA",
        "HASIL": "DARI HASIL KOORDINASI DENGAN PIHAK KAPAL, KEADAAN KAPAL DAN SELURUH KREW DALAM KEADAAN BAIK.",
        "UNSUR_SAR": "* USS JEMAJA\n* BAKAMLA Natuna",
        "ALUT_PALSAR": "* RIB ANAMBAS\n* Alat Navigasi",
        "CUACA": "* Cuaca : Badai Petir Ringan dan Hujan\n* Suhu : 31°C",
        "created_at": dt
    }
    
    report_text = message_formatter.render(None, data_kapal)
    print(report_text)
    
    # Validasi isi sesuai contoh format baku
    assert "LAKA KAPAL 1 (SATU) UNIT KAPAL MATI MESIN DI PERAIRAN JEMAJA KABUPATEN ANAMBAS" in report_text, "Judul Laka Kapal salah"
    assert "Yth : Kabasarnas." in report_text, "Tembusan Yth harus ada di Laka Kapal"
    assert "NAMA KAPAL: MV SS 2" in report_text
    assert "IMO : 9158123" in report_text
    print("✅ Uji coba render_laka_kapal BERHASIL!\n")


if __name__ == "__main__":
    try:
        test_angka_ke_kata()
        test_format_hari_tanggal()
        test_render_kmm()
        test_render_laka_kapal()
        print("🎉 SEMUA UJI UNIT FORMAT LAPORAN BERHASIL!")
    except AssertionError as e:
        print(f"❌ ASSERTION ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        sys.exit(1)
