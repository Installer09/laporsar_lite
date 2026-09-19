import logging
import re
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Tembusan Basarnas Pusat (SOP Terbaru: Dicantumkan untuk semua jenis laporan)

# 1. TEMPLATE LAKA KAPAL
LAKA_KAPAL_TEMPLATE = """*INFO AWAL*
*LAKA KAPAL {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF}}) UNIT {{DETAIL_JUDUL}}*

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

{{MOTTO_INSTANSI}}

Yth : Kabasarnas.
Cc  : Deputi Bidang Operasi Pencarian dan Pertolongan, dan Kesiapsiagaan Basarnas.
Bcc : Direktur Operasi Basarnas.

Mhn izin melaporkan Info Awal LAKA KAPAL {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF}}) UNIT {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}} terima info dari {{PELAPOR}}

*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
 {{KOORDINAT}}

*HEADING & JARAK*
> {{HEADING_JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORG*
S : {{KORBAN_SELAMAT}} Org
MD : {{KORBAN_MENINGGAL}} Org
DP : {{KORBAN_HILANG}} Org

*DATA KORBAN*
{{DATA_KORBAN}}

*DATA KAPAL*
{{DATA_KENDARAAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*AKSI:*
{{AKSI}}

*HASIL:*
> {{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR:*
{{ALUT_PALSAR}}

*CUACA:*
{{CUACA}}

Demikian sebagai laporan.
Mhn Ump.

TTD
{{TTD_KEPALA}}"""

DEFAULT_TEMPLATE = LAKA_KAPAL_TEMPLATE

# 2. TEMPLATE LAKA PESAWAT
LAKA_PESAWAT_TEMPLATE = """*INFO AWAL*
*LAKA PESAWAT {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF}}) UNIT {{DETAIL_JUDUL}}*

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

{{MOTTO_INSTANSI}}

Yth : Kabasarnas.
Cc  : Deputi Bidang Operasi Pencarian dan Pertolongan, dan Kesiapsiagaan Basarnas.
Bcc : Direktur Operasi Basarnas.

Mhn izin melaporkan Info Awal LAKA PESAWAT {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF}}) UNIT {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}} terima info dari {{PELAPOR}}

*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
 {{KOORDINAT}}

*HEADING & JARAK*
> {{HEADING_JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORG*
S : {{KORBAN_SELAMAT}} Org
MD : {{KORBAN_MENINGGAL}} Org
DP : {{KORBAN_HILANG}} Org

*DATA KORBAN*
{{DATA_KORBAN}}

*DATA PESAWAT*
{{DATA_KENDARAAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*AKSI:*
{{AKSI}}

*HASIL:*
> {{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR:*
{{ALUT_PALSAR}}

*CUACA:*
{{CUACA}}

Demikian sebagai laporan.
Mhn Ump.

TTD
{{TTD_KEPALA}}"""

# 3. TEMPLATE KPK
LAKA_KPK_TEMPLATE = """*INFO AWAL*
*KECELAKAAN DENGAN PENANGANAN KHUSUS {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF}}) UNIT {{DETAIL_JUDUL}}*

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

{{MOTTO_INSTANSI}}

Yth : Kabasarnas.
Cc  : Deputi Bidang Operasi Pencarian dan Pertolongan, dan Kesiapsiagaan Basarnas.
Bcc : Direktur Operasi Basarnas.

Mhn izin melaporkan Info Awal KECELAKAAN DENGAN PENANGANAN KHUSUS {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF}}) UNIT {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}} terima info dari {{PELAPOR}}

*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
 {{KOORDINAT}}

*HEADING & JARAK*
> {{HEADING_JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORG*
S : {{KORBAN_SELAMAT}} Org
MD : {{KORBAN_MENINGGAL}} Org
DP : {{KORBAN_HILANG}} Org

*DATA KORBAN*
{{DATA_KORBAN}}

*DATA SARANA / KENDARAAN*
{{DATA_KENDARAAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*AKSI:*
{{AKSI}}

*HASIL:*
> {{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR:*
{{ALUT_PALSAR}}

*CUACA:*
{{CUACA}}

Demikian sebagai laporan.
Mhn Ump.

TTD
{{TTD_KEPALA}}"""

# 4. TEMPLATE KMM
KMM_TEMPLATE = """*INFO AWAL*
*KMM {{JUMLAH_KORBAN_TOTAL}} ({{JUMLAH_KORBAN_HURUF}}) ORG {{DETAIL_JUDUL}}*

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

{{MOTTO_INSTANSI}}

Yth : Kabasarnas.
Cc  : Deputi Bidang Operasi Pencarian dan Pertolongan, dan Kesiapsiagaan Basarnas.
Bcc : Direktur Operasi Basarnas.

Mhn izin melaporkan informasi KMM {{JUMLAH_KORBAN_TOTAL}} ({{JUMLAH_KORBAN_HURUF_INLINE}}) org {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}} terima info dari {{PELAPOR}}

*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING & JARAK*
> {{HEADING_JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORG*
S : {{KORBAN_SELAMAT}} Org
MD : {{KORBAN_MENINGGAL}} Org
DP : {{KORBAN_HILANG}} Org

*DATA KORBAN*
{{DATA_KORBAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*AKSI:*
{{AKSI}}

*HASIL:*
> {{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR:*
{{ALUT_PALSAR}}

*CUACA:*
{{CUACA}}

Demikian sebagai laporan.
Mhn Ump.

TTD
{{TTD_KEPALA}}"""

# 5. TEMPLATE BENCANA
BENCANA_TEMPLATE = """*INFO AWAL*
*BENCANA {{JUMLAH_KORBAN_TOTAL}} ({{JUMLAH_KORBAN_HURUF}}) ORG {{DETAIL_JUDUL}}*

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

{{MOTTO_INSTANSI}}

Yth : Kabasarnas.
Cc  : Deputi Bidang Operasi Pencarian dan Pertolongan, dan Kesiapsiagaan Basarnas.
Bcc : Direktur Operasi Basarnas.

Mhn izin melaporkan informasi BENCANA {{JUMLAH_KORBAN_TOTAL}} ({{JUMLAH_KORBAN_HURUF_INLINE}}) org {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}} terima info dari {{PELAPOR}}

*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING & JARAK*
> {{HEADING_JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORG*
S : {{KORBAN_SELAMAT}} Org
MD : {{KORBAN_MENINGGAL}} Org
DP : {{KORBAN_HILANG}} Org

*DATA KORBAN*
{{DATA_KORBAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*AKSI:*
{{AKSI}}

*HASIL:*
> {{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR:*
{{ALUT_PALSAR}}

*CUACA:*
{{CUACA}}

Demikian sebagai laporan.
Mhn Ump.

TTD
{{TTD_KEPALA}}"""

# Fallback template


class MessageFormatterService:
    @staticmethod
    def angka_ke_kata(n: int) -> str:
        """Menerjemahkan angka integer menjadi kata huruf Indonesia."""
        if n == 0:
            return "NIHIL"
        
        satuan = ["", "SATU", "DUA", "TIGA", "EMPAT", "LIMA", "ENAM", "TUJUH", "DELAPAN", "SEMBILAN", "SEPULUH", "SEBELAS"]
        if n < 12:
            return satuan[n]
        elif n < 20:
            return MessageFormatterService.angka_ke_kata(n - 10) + " BELAS"
        elif n < 100:
            utama = n // 10
            sisa = n % 10
            hasil = satuan[utama] + " PULUH"
            if sisa > 0:
                hasil += " " + satuan[sisa]
            return hasil
        elif n < 200:
            return "SERATUS " + MessageFormatterService.angka_ke_kata(n - 100)
        elif n < 1000:
            utama = n // 100
            sisa = n % 100
            hasil = satuan[utama] + " RATUS"
            if sisa > 0:
                hasil += " " + MessageFormatterService.angka_ke_kata(sisa)
            return hasil
        return str(n)

    @staticmethod
    def format_hari_tanggal(dt: datetime, upper: bool = False) -> str:
        """Memformat datetime objek menjadi string Hari, Tanggal Bulan Tahun Indonesia."""
        hari_map = {
            "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
            "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
        }
        bulan_map = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
            7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
        }
        
        hari = hari_map.get(dt.strftime("%A"), dt.strftime("%A"))
        tanggal = dt.day
        bulan = bulan_map.get(dt.month, dt.strftime("%B"))
        tahun = dt.year
        
        if upper:
            return f"{hari.upper()}, {tanggal} {bulan} {tahun}"
        else:
            return f"{hari}, {tanggal} {bulan} {tahun}"

    @staticmethod
    def decimal_to_dms(lat: float, lng: float) -> str:
        """Convert decimal latitude and longitude to standard BASARNAS DMS string format."""
        from typing import Tuple
        def to_dms_parts(val: float) -> Tuple[int, int, float]:
            abs_val = abs(val)
            degrees = int(abs_val)
            minutes_float = (abs_val - degrees) * 60
            minutes = int(minutes_float)
            seconds = round((minutes_float - minutes) * 60, 2)
            if seconds >= 60.0:
                seconds = 0.0
                minutes += 1
            if minutes >= 60:
                minutes = 0
                degrees += 1
            return degrees, minutes, seconds

        lat_deg, lat_min, lat_sec = to_dms_parts(lat)
        lat_dir = "LU" if lat >= 0 else "LS"
        
        lng_deg, lng_min, lng_sec = to_dms_parts(lng)
        lng_dir = "BT" if lng >= 0 else "BB"
        
        lat_str = f"{lat_deg:02d}° {lat_min:02d}' {lat_sec:05.2f}\" {lat_dir}"
        lng_str = f"{lng_deg:03d}° {lng_min:02d}' {lng_sec:05.2f}\" {lng_dir}"
        
        return f"{lat_str} / {lng_str}"

    @staticmethod
    def hitung_sarana(data: dict, klasifikasi: str) -> int:
        """Menghitung jumlah sarana (kapal/pesawat/alat) yang terlibat secara aman."""
        if "jumlah_sarana" in data and data["jumlah_sarana"]:
            try:
                return int(data["jumlah_sarana"])
            except:
                pass
        
        key_map = {
            "KAPAL": "data_kapal",
            "PESAWAT": "data_pesawat",
            "ALAT": "data_alat"
        }
        
        target_key = None
        for k, v in key_map.items():
            if k in klasifikasi.upper():
                target_key = v
                break
        
        if not target_key:
            target_key = "data_kapal"
            
        vessel_data = data.get(target_key)
        if not vessel_data:
            # check inside metadata_kejadian
            vessel_data = data.get("metadata_kejadian", {}).get(target_key)
            
        if vessel_data:
            if isinstance(vessel_data, str):
                prefixes = ["KM", "KMN", "KRI", "TB", "RIB", "RHIB", "MV", "MT", "LCT", "TK", "BG", "KAPAL", "PESAWAT", "MOBIL", "MOTOR"]
                count = 0
                for line in vessel_data.split("\n"):
                    if any(p in line.upper() for p in prefixes):
                        count += 1
                return max(count, 1)
            elif isinstance(vessel_data, list):
                return len(vessel_data)
            elif isinstance(vessel_data, dict):
                return 1
                
        return 1

    def format_data_kapal(self, data_kapal) -> str:
        """Memformat data kapal secara terperinci sesuai format formal Basarnas."""
        nama = "-"
        jenis = "-"
        warna = "-"
        imo = "-"
        call_sign = "-"
        telp = "-"
        gt = ""

        if not data_kapal:
            return (
                "- NAMA KAPAL: \n"
                "- JENIS KAPAL: \n"
                "- WARNA KAPAL: \n"
                "- IMO : \n"
                "- Call Sign: \n"
                "- Telepon Satelit: "
            )

        if isinstance(data_kapal, str):
            lines = [line.strip() for line in data_kapal.split("\n") if line.strip()]
            for line in lines:
                if ":" in line:
                    k, v = [part.strip() for part in line.split(":", 1)]
                    k_upper = k.upper()
                    if k_upper in ("NAMA", "NAMA KAPAL"):
                        nama = v
                    elif k_upper in ("JENIS", "JENIS KAPAL", "KAPAL"):
                        jenis = v
                    elif k_upper in ("WARNA", "WARNA KAPAL"):
                        warna = v
                    elif k_upper == "IMO":
                        imo = v
                    elif k_upper in ("CALL SIGN", "CALLSIGN"):
                        call_sign = v
                    elif k_upper in ("TELEPON SATELIT", "TELP"):
                        telp = v
                    elif k_upper in ("GT", "KAPASITAS", "GROSS TONNAGE"):
                        gt = v
                else:
                    line_lower = line.lower()
                    if any(term in line_lower for term in ("pompong", "speedboat", "perahu", "kapal", "yacht", "tugboat", "tongkang")):
                        jenis = line
                    elif "warna" in line_lower:
                        warna = line.replace("warna", "").strip(": ").title()

        elif isinstance(data_kapal, dict):
            nama = data_kapal.get("nama_kapal") or data_kapal.get("nama") or "-"
            jenis = data_kapal.get("jenis_kapal") or data_kapal.get("jenis") or "-"
            warna = data_kapal.get("warna_kapal") or data_kapal.get("warna") or "-"
            imo = data_kapal.get("imo") or data_kapal.get("imo_kapal") or "-"
            call_sign = data_kapal.get("call_sign") or data_kapal.get("callsign") or "-"
            telp = data_kapal.get("telepon_satelit") or data_kapal.get("telp") or "-"
            gt = data_kapal.get("gt") or data_kapal.get("kapasitas") or ""

        # Normalize default "-"
        if not nama or str(nama).strip() == "": nama = "-"
        if not jenis or str(jenis).strip() == "": jenis = "-"
        if not warna or str(warna).strip() == "": warna = "-"
        if not imo or str(imo).strip() == "": imo = "-"
        if not call_sign or str(call_sign).strip() == "": call_sign = "-"
        if not telp or str(telp).strip() == "": telp = "-"

        # If GT is present and not already inside jenis, format jenis with GT
        if gt:
            gt_str = str(gt).upper().replace("GT", "").strip()
            if gt_str and gt_str not in jenis.upper():
                jenis = f"{jenis} ({gt_str} GT)"

        return (
            f"- NAMA KAPAL: {nama}\n"
            f"- JENIS KAPAL: {jenis}\n"
            f"- WARNA KAPAL: {warna}\n"
            f"- IMO : {imo}\n"
            f"- Call Sign: {call_sign}\n"
            f"- Telepon Satelit: {telp}"
        )

    def format_data_pesawat(self, data_pesawat) -> str:
        """Memformat data pesawat secara terperinci."""
        if not data_pesawat:
            return (
                "- NAMA PESAWAT: \n"
                "- JENIS PESAWAT: \n"
                "- WARNA PESAWAT: \n"
                "- REGISTER / CALL SIGN: \n"
                "- RUTE: \n"
                "- OPERATOR: "
            )
        if isinstance(data_pesawat, str):
            lines = [line.strip() for line in data_pesawat.split("\n") if line.strip()]
            formatted_lines = []
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    formatted_lines.append(f"- {k.strip().upper()}: {v.strip()}")
                else:
                    formatted_lines.append(f"- {line}")
            return "\n".join(formatted_lines)
        elif isinstance(data_pesawat, dict):
            nama = data_pesawat.get("nama_pesawat") or data_pesawat.get("nama") or "-"
            jenis = data_pesawat.get("jenis_pesawat") or data_pesawat.get("jenis") or "-"
            warna = data_pesawat.get("warna_pesawat") or data_pesawat.get("warna") or "-"
            call_sign = data_pesawat.get("call_sign") or data_pesawat.get("register") or "-"
            rute = data_pesawat.get("rute") or data_pesawat.get("rute_pesawat") or "-"
            operator = data_pesawat.get("operator") or "-"
            
            return (
                f"- NAMA PESAWAT: {nama}\n"
                f"- JENIS PESAWAT: {jenis}\n"
                f"- WARNA PESAWAT: {warna}\n"
                f"- REGISTER / CALL SIGN: {call_sign}\n"
                f"- RUTE: {rute}\n"
                f"- OPERATOR: {operator}"
            )
        return "- "

    def format_data_alat(self, data_alat) -> str:
        """Memformat data sarana / kendaraan KPK secara terperinci."""
        if not data_alat:
            return (
                "- JENIS KENDARAAN: \n"
                "- WARNA KENDARAAN: \n"
                "- NOMOR POLISI: \n"
                "- PEMILIK: "
            )
        if isinstance(data_alat, str):
            lines = [line.strip() for line in data_alat.split("\n") if line.strip()]
            formatted_lines = []
            for line in lines:
                if ":" in line:
                    k, v = line.split(":", 1)
                    formatted_lines.append(f"- {k.strip().upper()}: {v.strip()}")
                else:
                    formatted_lines.append(f"- {line}")
            return "\n".join(formatted_lines)
        elif isinstance(data_alat, dict):
            jenis = data_alat.get("jenis_kendaraan") or data_alat.get("jenis") or "-"
            warna = data_alat.get("warna_kendaraan") or data_alat.get("warna") or "-"
            nopol = data_alat.get("nopol") or data_alat.get("no_polisi") or "-"
            pemilik = data_alat.get("pemilik") or "-"
            
            return (
                f"- JENIS KENDARAAN: {jenis}\n"
                f"- WARNA KENDARAAN: {warna}\n"
                f"- NOMOR POLISI: {nopol}\n"
                f"- PEMILIK: {pemilik}"
            )
        return "- "

    def format_korban(self, data_korban: list, total_korban: int = None) -> str:
        """Alias for format_data_korban for test backwards compatibility."""
        return self.format_data_korban(data_korban, total_korban=total_korban)

    def format_data_korban(self, data_korban: list, is_kmm_bencana: bool = True, total_korban: int = None) -> str:
        """Memformat data korban secara dinamis dengan template blok terstruktur."""
        # Determine if it's empty
        is_empty = False
        if not data_korban:
            is_empty = True
        elif isinstance(data_korban, str):
            clean_str = data_korban.strip().lower()
            if clean_str in ("", "-", "belum ada data korban.", "tidak tahu", "belum tahu", "nihil", "tidak ada"):
                is_empty = True
        elif isinstance(data_korban, list) and len(data_korban) == 0:
            is_empty = True

        if is_empty:
            # Tampilkan 1 saja skeleton kosong jika tidak ada data korban yang diketahui
            block = (
                f"*Korban ke-1:*\n"
                f"- Nama : \n"
                f"- Alamat : \n"
                f"- Ciri-ciri:"
            )
            return block

        if isinstance(data_korban, str):
            # Try to parse from JSON string
            try:
                parsed = json.loads(data_korban)
                if isinstance(parsed, list):
                    return self.format_data_korban(parsed, is_kmm_bencana, total_korban)
            except Exception:
                pass
            
            # Non-JSON string
            lines = [line.strip() for line in data_korban.split("\n") if line.strip()]
            formatted_lines = []
            for line in lines:
                if not line.startswith("-"):
                    formatted_lines.append(f"- {line}")
                else:
                    formatted_lines.append(line)
            return "\n".join(formatted_lines)

        # It's a list of parsed victims
        formatted_blocks = []
        parsed_count = len(data_korban)
        
        if parsed_count == 0:
            return (
                f"*Korban ke-1:*\n"
                f"- Nama : \n"
                f"- Alamat : \n"
                f"- Ciri-ciri:"
            )
            
        for idx in range(1, parsed_count + 1):
            victim_info = data_korban[idx - 1]
                
            if isinstance(victim_info, dict):
                block_lines = [f"*Korban ke-{idx}:*"]
                nama = victim_info.get("nama") or victim_info.get("nama_korban") or ""
                jk = victim_info.get("jenis_kelamin") or victim_info.get("jk") or ""
                umur = victim_info.get("umur") or ""
                alamat = victim_info.get("alamat") or ""
                ciri = victim_info.get("ciri_ciri") or victim_info.get("ciri") or ""
                
                # Normalisasi nilai default "-" / empty
                if nama == "-": nama = ""
                if jk == "-": jk = ""
                if umur == "-": umur = ""
                if alamat == "-": alamat = ""
                if ciri == "-": ciri = ""
                
                # Normalisasi Jenis Kelamin (L / P)
                jk_norm = ""
                if jk:
                    jk_upper = str(jk).strip().upper()
                    if jk_upper in ("LAKI-LAKI", "LAKI LAKI", "PRIA", "COWOK", "L"):
                        jk_norm = "L"
                    elif jk_upper in ("PEREMPUAN", "WANITA", "CEWEK", "P"):
                        jk_norm = "P"
                    else:
                        jk_norm = jk
                        
                # Normalisasi Umur (Thn)
                umur_norm = ""
                if umur:
                    umur_str = str(umur).strip()
                    if not re.search(r'\b(thn|tahun)\b', umur_str, re.IGNORECASE):
                        umur_norm = f"{umur_str} Thn"
                    else:
                        # Ganti thn/tahun dengan Thn secara seragam
                        umur_norm = re.sub(r'\b(?:thn|tahun)\b', 'Thn', umur_str, flags=re.IGNORECASE)
                        
                # Gabungkan JK dan Umur di samping Nama
                jk_umur_parts = []
                if jk_norm:
                    jk_umur_parts.append(jk_norm)
                if umur_norm:
                    jk_umur_parts.append(umur_norm)
                    
                if jk_umur_parts:
                    jk_umur_str = f" ({'/'.join(jk_umur_parts)})"
                else:
                    jk_umur_str = ""
                    
                block_lines.append(f"- Nama : {nama}{jk_umur_str}")
                block_lines.append(f"- Alamat : {alamat}")
                block_lines.append(f"- Ciri-ciri: {ciri}")
                formatted_blocks.append("\n".join(block_lines))
                
            elif isinstance(victim_info, str) and victim_info.strip() not in ("", "-"):
                # Simply format simple string like the old way
                formatted_blocks.append(f"- {victim_info.strip()}")
            else:
                # Blank skeleton block
                block_lines = [
                    f"*Korban ke-{idx}:*",
                    f"- Nama : ",
                    f"- Alamat : ",
                    f"- Ciri-ciri:"
                ]
                formatted_blocks.append("\n".join(block_lines))
            
        return "\n\n".join(formatted_blocks)

    def to_basarnas_pdtw(self, waktu_str: str, created_at: datetime, koordinat_lng: float = None) -> str:
        """Converts raw waktu string to standard BASARNAS PDTW format: MMDD HHMM <TZ_CHAR>"""
        if not waktu_str or str(waktu_str).strip() == "":
            return "Belum Diketahui"
        
        import re
        from datetime import timezone, timedelta
        
        # 1. Determine local timezone offset based on incident longitude
        offset_hours = 7.0
        tz_char = "G"
        if koordinat_lng is not None:
            try:
                lng_val = float(koordinat_lng)
                if lng_val >= 135.0:
                    offset_hours = 9.0
                    tz_char = "J" # WIT
                elif lng_val >= 115.0:
                    offset_hours = 8.0
                    tz_char = "H" # WITA
                else:
                    offset_hours = 7.0
                    tz_char = "G" # WIB
            except Exception:
                pass

        w_clean = str(waktu_str).strip()
        
        # If already formatted as PDTW (MMDD HHMM <TZ>)
        if re.match(r'^\d{4}\s+\d{4}\s+[G-J]$', w_clean, re.IGNORECASE):
            return w_clean.upper()
        if re.match(r'^PDTW\s+\d{4}\s+\d{4}\s+[G-J]$', w_clean, re.IGNORECASE):
            return re.sub(r'^PDTW\s+', '', w_clean, flags=re.IGNORECASE).upper()
            
        # Check if waktu_str is a datetime object or can be parsed as an ISO datetime
        dt_parsed = None
        if isinstance(waktu_str, datetime):
            dt_parsed = waktu_str
        else:
            try:
                # Replace space with T to make it standard ISO
                iso_str = w_clean.replace(" ", "T")
                dt_parsed = datetime.fromisoformat(iso_str)
            except Exception:
                pass
                
        if dt_parsed:
            # Convert to target local timezone
            if dt_parsed.tzinfo is not None:
                local_dt = dt_parsed.astimezone(timezone(timedelta(hours=offset_hours)))
            else:
                local_dt = dt_parsed.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=offset_hours)))
            return local_dt.strftime(f"%m%d %H%M {tz_char}")

        # Default values from reference datetime
        ref_dt = created_at or datetime.now()
        if ref_dt.tzinfo is not None:
            ref_dt = ref_dt.astimezone(timezone(timedelta(hours=offset_hours)))
        else:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=offset_hours)))
        year = ref_dt.year
        month = ref_dt.month
        day = ref_dt.day
        hour = 6 # default to 06:00
        minute = 0
        
        waktu_upper = w_clean.upper()
        
        # 2. Extract Date parts
        # Check for YYYY-MM-DD
        iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', w_clean)
        if iso_match:
            year = int(iso_match.group(1))
            month = int(iso_match.group(2))
            day = int(iso_match.group(3))
        else:
            # Check for DD-MM-YYYY or DD/MM/YYYY
            slash_match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', w_clean)
            if slash_match:
                day = int(slash_match.group(1))
                month = int(slash_match.group(2))
                year = int(slash_match.group(3))
            else:
                # Check for date like "26 MEI 2026" or "26 MEI"
                month_map = {
                    "JAN": 1, "PEB": 2, "FEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "MAY": 5,
                    "JUN": 6, "JUL": 7, "AGU": 8, "AUG": 8, "SEP": 9, "OKT": 10, "OCT": 10,
                    "NOV": 11, "DES": 12, "DEC": 12
                }
                for m_name, m_num in month_map.items():
                    m_match = re.search(rf'(\d{{1,2}})\s+{m_name}', waktu_upper)
                    if m_match:
                        day = int(m_match.group(1))
                        month = m_num
                        break
                        
        # 3. Extract Time parts
        # Check for HH:MM or HH.MM
        time_match = re.search(r'\b(\d{1,2})[:.](\d{2})', w_clean)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
        else:
            pukul_match = re.search(r'\b(?:PUKUL|JAM)\s+(\d{1,2})', waktu_upper)
            if pukul_match:
                hour = int(pukul_match.group(1))
                minute = 0
                # 12-hour AM/PM adjustment for Indonesian SORE/MALAM/SIANG
                if hour < 12:
                    if "SORE" in waktu_upper or "MALAM" in waktu_upper:
                        hour += 12
                    elif "SIANG" in waktu_upper and hour <= 4:
                        hour += 12
            else:
                # Word-based fallbacks
                if "PAGI" in waktu_upper:
                    hour = 6
                    minute = 0
                elif "SIANG" in waktu_upper:
                    hour = 12
                    minute = 0
                elif "SORE" in waktu_upper:
                    hour = 16
                    minute = 0
                elif "MALAM" in waktu_upper:
                    hour = 20
                    minute = 0
                elif "SUBUH" in waktu_upper:
                    hour = 4
                    minute = 0
                    
        # Format MMDD HHMM TZ
        return f"{month:02d}{day:02d} {hour:02d}{minute:02d} {tz_char}"

    def render(self, template: str, data: dict) -> str:
        """
        Renders template safely. 
        Selects dynamic, classification-specific template if template is None.
        """
        klasifikasi_raw = data.get("KLASIFIKASI") or data.get("klasifikasi") or data.get("jenis_kejadian") or "KMM"
        klasifikasi_upper = str(klasifikasi_raw).upper()

        # Tentukan template berdasarkan KLASIFIKASI secara dinamis jika tidak disuplai
        if not template:
            if "KAPAL" in klasifikasi_upper or "LAUT" in klasifikasi_upper or "AIR" in klasifikasi_upper:
                template = LAKA_KAPAL_TEMPLATE
                active_klasifikasi = "LAKA KAPAL"
            elif "PESAWAT" in klasifikasi_upper or "UDARA" in klasifikasi_upper:
                template = LAKA_PESAWAT_TEMPLATE
                active_klasifikasi = "LAKA PESAWAT"
            elif "KHUSUS" in klasifikasi_upper or "KPK" in klasifikasi_upper or "LANTAS" in klasifikasi_upper:
                template = LAKA_KPK_TEMPLATE
                active_klasifikasi = "KPK"
            elif "BENCANA" in klasifikasi_upper:
                template = BENCANA_TEMPLATE
                active_klasifikasi = "BENCANA"
            else:
                template = KMM_TEMPLATE
                active_klasifikasi = "KMM"
        else:
            active_klasifikasi = "KMM"
            if "KAPAL" in template or "data_kapal" in template or "DATA KAPAL" in template:
                active_klasifikasi = "LAKA KAPAL"
            elif "PESAWAT" in template or "data_pesawat" in template or "DATA PESAWAT" in template:
                active_klasifikasi = "LAKA PESAWAT"
            elif "KPK" in template or "DATA SARANA" in template:
                active_klasifikasi = "KPK"
            elif "BENCANA" in template:
                active_klasifikasi = "BENCANA"

        is_kmm_bencana = active_klasifikasi in ("KMM", "BENCANA")

        # Hitung jumlah sarana & korban
        jumlah_sarana = self.hitung_sarana(data, active_klasifikasi)
        jumlah_sarana_huruf = self.angka_ke_kata(jumlah_sarana)

        # Hitung korban total
        korban_total_val = 0
        try:
            korban_total_val = int(data.get("JUMLAH_KORBAN_TOTAL") or data.get("korban_total") or 0)
        except:
            pass

        if korban_total_val == 0:
            # Hitung dari data_korban jika ada
            korban_list = data.get("data_korban") or data.get("data_korban_payload")
            if isinstance(korban_list, list):
                korban_total_val = len(korban_list)
            elif isinstance(korban_list, dict) and "daftar_korban" in korban_list:
                korban_total_val = len(korban_list["daftar_korban"])

        jumlah_korban_huruf = self.angka_ke_kata(korban_total_val)
        jumlah_korban_huruf_inline = jumlah_korban_huruf.title()

        # Bangun Detail Judul Dinamis
        lokasi_raw = data.get("LOKASI_KEJADIAN") or data.get("lokasi_teks") or ""
        
        # Bersihkan jenis kejadian untuk judul
        clean_jenis = str(data.get("jenis_kejadian") or data.get("KLASIFIKASI") or "").upper()
        for prefix in ["KMM (KONDISI MEMBAHAYAKAN MANUSIA)", "KONDISI MEMBAHAYAKAN MANUSIA", "KMM", 
                        "KECELAKAAN KAPAL", "LAKA KAPAL", "KECELAKAAN PESAWAT", "LAKA PESAWAT", 
                        "BENCANA ALAM", "BENCANA", "KPK"]:
            if clean_jenis == prefix:
                clean_jenis = ""
            elif clean_jenis.startswith(prefix + " "):
                clean_jenis = clean_jenis[len(prefix):].strip()
        clean_jenis = clean_jenis.strip("-: ").strip()

        # If clean_jenis is empty or generic (e.g. just classification), try to extract subject from KRONOLOGI
        if not clean_jenis or clean_jenis in ["LAKA KAPAL", "LAKA PESAWAT", "KMM", "BENCANA", "KPK", "KONDISI MEMBAHAYAKAN MANUSIA"]:
            kronologi = str(data.get("KRONOLOGI") or data.get("kronologi") or "").upper()
            
            # Get dynamic boat types / subjects from pre-warmed cache or fallback
            from app.services.rule_extractor import RuleExtractor
            db_boats = ["POMPONG", "SPEEDBOAT", "PERAHU", "TONGKANG", "TUGBOAT", "TANKER", "KAPAL", "KM", "KMN"]
            if RuleExtractor._dictionary_cache:
                vessel_types = [item["word"].upper() for item in RuleExtractor._dictionary_cache.get("VESSEL_TYPE", [])]
                vessel_prefixes = [item["word"].upper() for item in RuleExtractor._dictionary_cache.get("VESSEL_PREFIX", [])]
                combined_boats = list(set(vessel_types + vessel_prefixes + db_boats))
                combined_boats.sort(key=len, reverse=True)
                db_boats = combined_boats
                
            db_problems_list = ["MATI MESIN", "TENGGELAM", "TERBALIK", "HANYUT", "KANDAS", "TERBAKAR", "KEBAKARAN", "TABRAKAN", "HILANG KONTAK", "LOST CONTACT", "BELUM KEMBALI", "TIDAK BISA DIHUBUNGI", "BELUM PULANG"]
            if RuleExtractor._dictionary_cache:
                problems_from_db = [item["word"].upper() for item in RuleExtractor._dictionary_cache.get("INCIDENT_PROBLEM", [])]
                combined_problems = list(set(problems_from_db + db_problems_list))
                combined_problems.sort(key=len, reverse=True)
                db_problems_list = combined_problems

            # Construct regex pattern dynamically
            boats_pattern = "|".join(re.escape(b) for b in db_boats)
            problems_patterns = []
            for p in db_problems_list:
                problems_patterns.append(re.escape(p).replace(r"\ ", r"\s+").replace(" ", r"\s+"))
            problems_pattern = "|".join(problems_patterns)
            
            boat_match = re.search(
                rf'\b({boats_pattern})\s+(?:[A-Z0-9\s]{{0,20}}\s+)?({problems_pattern})',
                kronologi
            )
            
            if boat_match:
                clean_jenis = f"{boat_match.group(1)} {boat_match.group(2)}"
            else:
                # Fallback: check just for specific common phrases
                phrases = []
                default_phrases = [
                    "POMPONG MATI MESIN", "KAPAL MATI MESIN", "PERAHU TERBALIK", "KAPAL TENGGELAM", 
                    "ORANG TENGGELAM", "ORANG HANYUT", "ORANG HILANG", "POMPONG BELUM KEMBALI",
                    "KAPAL BELUM KEMBALI", "POMPONG HILANG", "KAPAL HILANG", "TIDAK BISA DIHUBUNGI"
                ]
                for s in ["POMPONG", "KAPAL", "PERAHU", "ORANG"]:
                    for p in db_problems_list[:5]:
                        phrases.append(f"{s} {p}")
                for dp in default_phrases:
                    if dp not in phrases:
                        phrases.append(dp)
                        
                found_phrase = None
                for phrase in phrases:
                    if phrase in kronologi:
                        found_phrase = phrase
                        break
                if found_phrase:
                    clean_jenis = found_phrase
                else:
                    # Advanced fallback: combine any found subject and problem dynamically
                    subj_found = None
                    prob_found = None
                    
                    default_subjects = ["POMPONG", "SPEEDBOAT", "PERAHU", "TONGKANG", "TUGBOAT", "TANKER", "KAPAL", "KM", "KMN", "ANAK", "NELAYAN", "ABK", "WARGA", "WISATAWAN", "ORANG"]
                    db_subjects = []
                    if RuleExtractor._dictionary_cache:
                        for category in ["VESSEL_PREFIX", "VICTIM_ROLE", "VESSEL_TYPE"]:
                            for item in RuleExtractor._dictionary_cache.get(category, []):
                                db_subjects.append(item["word"].upper())
                        for item in RuleExtractor._dictionary_cache.get("QUANTIFIER", []):
                            if item["word"].upper() in ["ABK", "KRU", "AWAK", "KORBAN", "PENUMPANG"]:
                                db_subjects.append(item["word"].upper())
                                
                    if db_subjects:
                        subjects = []
                        for s in db_subjects:
                            if s not in subjects:
                                subjects.append(s)
                        for s in default_subjects:
                            if s.upper() not in subjects:
                                subjects.append(s.upper())
                    else:
                        subjects = default_subjects
                        
                    default_problems = ["MATI MESIN", "HILANG KONTAK", "LOST CONTACT", "TENGGELAM", "TERBALIK", "HANYUT", "KANDAS", "TERBAKAR", "KEBAKARAN", "TABRAKAN", "HILANG", "TERJEBAK", "TERJEPIT", "BELUM KEMBALI", "BELUM PULANG", "TIDAK BISA DIHUBUNGI"]
                    if db_problems_list:
                        problems = []
                        for p in db_problems_list:
                            if p not in problems:
                                problems.append(p)
                        for p in default_problems:
                            if p not in problems:
                                problems.append(p)
                    else:
                        problems = default_problems
                        
                    for s in subjects:
                        if s in kronologi:
                            subj_found = s
                            break
                    for p in problems:
                        if p in kronologi:
                            prob_found = p
                            break
                    if subj_found and prob_found:
                        clean_jenis = f"{subj_found} {prob_found}"
                    elif prob_found:
                        clean_jenis = prob_found

            # Final check: if clean_jenis is still empty or generic, try fallback to data_kapal/vessel data type
            if not clean_jenis or clean_jenis in ["LAKA KAPAL", "LAKA PESAWAT", "KMM", "BENCANA", "KPK", "KONDISI MEMBAHAYAKAN MANUSIA"]:
                dk = str(data.get("data_kapal") or data.get("metadata_kejadian", {}).get("data_kapal") or "").lower()
                dp = str(data.get("data_pesawat") or data.get("metadata_kejadian", {}).get("data_pesawat") or "").lower()
                
                if active_klasifikasi == "LAKA KAPAL":
                    vessel_type = "KAPAL"
                    if "pompong" in dk:
                        vessel_type = "POMPONG"
                    elif "speedboat" in dk:
                        vessel_type = "SPEEDBOAT"
                    elif "perahu" in dk:
                        vessel_type = "PERAHU"
                    clean_jenis = f"{vessel_type} BELUM KEMBALI"
                elif active_klasifikasi == "LAKA PESAWAT":
                    clean_jenis = "PESAWAT HILANG KONTAK"
                elif active_klasifikasi == "KPK":
                    clean_jenis = "KECELAKAAN SARANA"
        
        # Normalisasi kejadian "belum kembali", "tidak bisa dihubungi", "lost contact" -> HILANG KONTAK
        for phrase in ["BELUM KEMBALI", "TIDAK BISA DIHUBUNGI", "LOST CONTACT"]:
            if phrase in clean_jenis:
                clean_jenis = clean_jenis.replace(phrase, "HILANG KONTAK")
        
        # Potong duplikasi kata ORANG / ORG
        if active_klasifikasi in ("KMM", "BENCANA"):
            if clean_jenis.startswith("ORANG "):
                clean_jenis = clean_jenis[6:].strip()
            elif clean_jenis.startswith("ORG "):
                clean_jenis = clean_jenis[4:].strip()

        # Satukan dengan lokasi
        lokasi_upper = str(lokasi_raw).upper() if (lokasi_raw is not None and lokasi_raw is not False and lokasi_raw != "") else ""
        if lokasi_upper:
            # 1. Ubah "DEKAT SENOA" -> "PERAIRAN SENOA"
            from app.services.rule_extractor import RuleExtractor
            islands = [item["word"].upper() for item in RuleExtractor._dictionary_cache.get("ISLAND", [])] if RuleExtractor._dictionary_cache.get("ISLAND") else ["SENOA", "JEMAJA", "SUBI", "MIDAI", "SERASAN", "PANJANG", "TIGA", "SEDANAU", "LAUT", "PULAU"]
            match_dekat = re.search(r'\b(?:DI\s+)?DEKAT\s+([A-Z0-9\s]+)', lokasi_upper)
            if match_dekat:
                place = match_dekat.group(1).strip()
                if any(isl in place for isl in islands):
                    lokasi_upper = lokasi_upper.replace(match_dekat.group(0), f"PERAIRAN {place}")
            
            # Strip "DI " dari awal lokasi jika ada agar tidak double
            lokasi_upper = re.sub(r'^DI\s+', '', lokasi_upper).strip()

            # 2. Normalisasi kabupaten
            kab_match = re.search(r'\b(?:KAB\.?|KABUPATEN)\s+([A-Z\s]+)', lokasi_upper)
            if kab_match:
                kab_name = kab_match.group(1).strip()
                lokasi_upper = re.sub(r'\b(?:KAB\.?|KABUPATEN)\s+[A-Z\s]+', f"KABUPATEN {kab_name}", lokasi_upper)
            else:
                pos_sar = data.get("pos_sar_terdekat") or ""
                detected_kab = "KABUPATEN NATUNA"
                if "ANAMBAS" in lokasi_upper or "JEMAJA" in lokasi_upper or "ANAMBAS" in pos_sar.upper() or "JEMAJA" in pos_sar.upper():
                    detected_kab = "KABUPATEN ANAMBAS"
                elif "NATUNA" in lokasi_upper or "NATUNA" in pos_sar.upper():
                    detected_kab = "KABUPATEN NATUNA"
                lokasi_upper = f"{lokasi_upper} {detected_kab}"
            
            # Bersihkan spasi ganda, hilangkan koma sebelum KABUPATEN
            lokasi_upper = re.sub(r'\s+', ' ', lokasi_upper).strip()
            lokasi_upper = lokasi_upper.replace("KABUPATEN KABUPATEN", "KABUPATEN")
            lokasi_upper = re.sub(r',\s*KABUPATEN', ' KABUPATEN', lokasi_upper)

        if lokasi_upper and lokasi_upper not in clean_jenis:
            detail_judul = f"{clean_jenis} DI {lokasi_upper}"
        else:
            detail_judul = clean_jenis

        # Hari & Tanggal
        dt_obj = data.get("created_at") or datetime.now()
        if isinstance(dt_obj, str):
            try:
                dt_obj = datetime.fromisoformat(dt_obj.replace("Z", "+00:00"))
            except:
                dt_obj = datetime.now()
        
        # Get koordinat_lng dynamically for timezone offset calculation
        lng_val = data.get("koordinat_lng") or data.get("longitude")
        if not lng_val:
            direct_coord = data.get("KOORDINAT") or data.get("koordinat") or ""
            try:
                from app.services.geo_service import parse_coordinates
                coords = parse_coordinates(str(direct_coord))
                if coords:
                    _, lng_val = coords
            except Exception:
                pass
        try:
            lng_val = float(lng_val) if lng_val is not None else None
        except Exception:
            lng_val = None

        hari_tanggal = self.format_hari_tanggal(dt_obj, upper=(active_klasifikasi != "KMM"))

        def replace_match(match):
            key = match.group(1).strip()
            
            # Dynamic identity placeholders
            if key == "NAMA_INSTANSI":
                return data.get("NAMA_INSTANSI") or "Kantor Pencarian dan Pertolongan Natuna"
            if key == "MOTTO_INSTANSI":
                motto = data.get("MOTTO_INSTANSI") or "We Are Family\nProfesional - Modern - Teruji"
                return "\n".join(f"*{line.strip()}*" for line in motto.split("\n") if line.strip())
            if key == "TTD_KEPALA":
                return data.get("TTD_KEPALA") or "NATUNA 01"
            
            # 1. Penanganan Tanggal
            if key == "HARI_TANGGAL":
                return hari_tanggal

            if key == "WAKTU_KEJADIAN":
                w_str = data.get("WAKTU_KEJADIAN") or data.get("waktu") or data.get("waktu_kejadian") or ""
                return self.to_basarnas_pdtw(w_str, dt_obj, koordinat_lng=lng_val)

            if key == "WAKTU_INFO_DITERIMA":
                wi_str = data.get("WAKTU_INFO_DITERIMA") or data.get("waktu_info_diterima") or ""
                return self.to_basarnas_pdtw(wi_str, dt_obj, koordinat_lng=lng_val)
                
            if key == "KOORDINAT":
                lat = data.get("koordinat_lat") or data.get("latitude")
                lng = data.get("koordinat_lng") or data.get("longitude")
                if not lat or not lng:
                    direct_coord = data.get("KOORDINAT") or data.get("koordinat") or ""
                    from app.services.geo_service import parse_coordinates
                    coords = parse_coordinates(str(direct_coord))
                    if coords:
                        lat, lng = coords
                if lat and lng:
                    try:
                        return self.decimal_to_dms(float(lat), float(lng))
                    except Exception:
                        pass
                direct_coord = data.get("KOORDINAT") or data.get("koordinat") or "Belum Diketahui"
                return str(direct_coord)
                
            # 2. Penanganan Judul Dinamis
            if key == "DETAIL_JUDUL":
                return detail_judul
            if key == "DETAIL_JUDUL_INLINE":
                return detail_judul.title()
            if key == "JUMLAH_SARANA":
                return str(jumlah_sarana)
            if key == "JUMLAH_SARANA_HURUF":
                return jumlah_sarana_huruf
            if key == "JUMLAH_KORBAN_HURUF":
                return jumlah_korban_huruf
            if key == "JUMLAH_KORBAN_HURUF_INLINE":
                return jumlah_korban_huruf_inline
            if key == "JUMLAH_KORBAN_TOTAL":
                return str(korban_total_val)

            # 3. Penanganan Korban Detail
            if key in ("DATA_KORBAN", "RINCIAN_KORBAN"):
                korban_list = data.get("data_korban")
                if korban_list is None:
                    # check metadata
                    korban_list = data.get("metadata_kejadian", {}).get("data_korban")
                if korban_list is None:
                    korban_list = []
                elif isinstance(korban_list, str) and (korban_list.startswith("[") or korban_list.startswith("{")):
                    try:
                        korban_list = json.loads(korban_list)
                    except:
                        pass
                if isinstance(korban_list, dict) and "daftar_korban" in korban_list:
                    korban_list = korban_list["daftar_korban"]
                return self.format_data_korban(korban_list, is_kmm_bencana, total_korban=korban_total_val)
                
            # 4. Penanganan Korban Breakdown
            if key in ("KORBAN_SELAMAT", "KORBAN_MENINGGAL", "KORBAN_HILANG"):
                field_map = {
                    "KORBAN_SELAMAT": ["korban_selamat", "korban_s"],
                    "KORBAN_MENINGGAL": ["korban_meninggal", "korban_md"],
                    "KORBAN_HILANG": ["korban_hilang", "korban_dp"]
                }
                val = None
                for alias in field_map[key]:
                    if alias in data:
                        val = data[alias]
                        break
                if val is not None and str(val).strip() != "":
                    return str(val)
                return "-"

            # 5. Penanganan Data Sarana/Kendaraan
            if key == "DATA_KENDARAAN":
                if active_klasifikasi == "LAKA KAPAL":
                    val = data.get("data_kapal") or data.get("metadata_kejadian", {}).get("data_kapal")
                    return self.format_data_kapal(val)
                elif active_klasifikasi == "LAKA PESAWAT":
                    val = data.get("data_pesawat") or data.get("metadata_kejadian", {}).get("data_pesawat")
                    return self.format_data_pesawat(val)
                elif active_klasifikasi == "KPK":
                    val = data.get("data_alat") or data.get("metadata_kejadian", {}).get("data_alat")
                    return self.format_data_alat(val)
                return "- "

            # 6. Heading dan Jarak Terintegrasi
            if key == "HEADING_JARAK":
                # Cari heading, jarak, dan pos_sar
                heading = data.get("heading") or data.get("heading_ke_lokasi")
                jarak = data.get("jarak") or data.get("jarak_ke_lokasi")
                pos_sar = data.get("pos_sar_terdekat") or "Kantor SAR Natuna"
                
                if heading and jarak:
                    # Bersihkan simbol derajat/NM ganda
                    heading_str = str(heading).replace("°", "") + "°"
                    jarak_str = str(jarak).upper().replace("NM", "").strip() + " NM"
                    return f"Heading {heading_str} dan Jarak {jarak_str} dari {pos_sar}"
                
                # Fallback to HEADING_JARAK string if provided directly
                direct_hj = data.get("HEADING_JARAK") or data.get("heading_jarak")
                if direct_hj and direct_hj.strip() != "" and direct_hj != "Tidak terdeteksi":
                    if "/" in direct_hj:
                        parts = [p.strip() for p in direct_hj.split("/")]
                        if len(parts) >= 2:
                            return f"Heading {parts[0]}° dan Jarak {parts[1]} NM dari {pos_sar}"
                    return direct_hj
                return f"Tidak terdeteksi (Koordinat belum terisi)"

            # 7. Unsur SAR, Alut, Aksi, Hasil Formatter (Menggunakan baris peluru)
            if key in ("UNSUR_SAR", "ALUT_PALSAR", "AKSI"):
                val = data.get(key) or data.get(key.lower())
                if not val or str(val).strip() == "":
                    # Fallbacks
                    if key == "UNSUR_SAR": return "* Kantor SAR Natuna\n* Potensi SAR Terdekat"
                    if key == "ALUT_PALSAR": return "* LCR\n* Pal Keselamatan Lainnya"
                    if key == "AKSI": return f"* Kantor SAR berkoordinasi dengan unsur terkait di lokasi"
                
                if isinstance(val, list):
                    items_str = []
                    for item in val:
                        if isinstance(item, dict):
                            name_val = item.get("nama") or item.get("name") or str(item)
                            items_str.append(f"* {name_val}")
                        else:
                            items_str.append(f"* {item}")
                    return "\n".join(items_str)
                elif isinstance(val, str):
                    lines = [line.strip() for line in val.split("\n") if line.strip()]
                    formatted_lines = []
                    for line in lines:
                        if isinstance(line, str):
                            if not line.startswith("*"):
                                formatted_lines.append(f"* {line}")
                            else:
                                formatted_lines.append(line)
                    return "\n".join(formatted_lines)

            # 8. Alias mapping default
            aliases = {
                "JENIS_KEJADIAN": ["jenis_kejadian", "JENIS_KEJADIAN", "KLASIFIKASI", "klasifikasi"],
                "KLASIFIKASI": ["KLASIFIKASI", "klasifikasi", "jenis_kejadian", "JENIS_KEJADIAN"],
                "WAKTU_KEJADIAN": ["waktu", "WAKTU_KEJADIAN", "waktu_kejadian"],
                "LOKASI_KEJADIAN": ["lokasi_teks", "LOKASI_KEJADIAN", "lokasi_kejadian", "lokasi"],
                "KRONOLOGI": ["kronologi", "KRONOLOGI"],
                "KOORDINAT": ["koordinat", "KOORDINAT"],
                "CUACA": ["cuaca", "CUACA"],
                "JUDUL_KEJADIAN": ["judul_kejadian", "JUDUL_KEJADIAN"],
                "WAKTU_INFO_DITERIMA": ["waktu_info_diterima", "WAKTU_INFO_DITERIMA"],
                "PELAPOR": ["pelapor", "PELAPOR"],
                "HASIL": ["hasil", "HASIL"]
            }
            
            # Cari dari alias
            val = None
            if key in aliases:
                for alias in aliases[key]:
                    if alias in data:
                        val = data[alias]
                        break
            else:
                val = data.get(key) or data.get(key.lower()) or data.get(key.upper())
                
            if isinstance(val, str):
                val = val.strip()
                
            if val is None or val == "" or val is False or val == 0:
                if key in ("JENIS_KEJADIAN", "KLASIFIKASI", "WAKTU_KEJADIAN", "LOKASI_KEJADIAN"):
                    return "Belum Diketahui"
                if key == "KRONOLOGI":
                    return "Belum Diketahui"
                if key == "HASIL":
                    return "Dalam pencarian / Pemantauan"
                return ""
                
            return str(val)

        # Regex pencarian {{VARIABLE}}
        pattern = re.compile(r"\{\{(.*?)\}\}")
        result = pattern.sub(replace_match, template)
        return result


message_formatter = MessageFormatterService()
