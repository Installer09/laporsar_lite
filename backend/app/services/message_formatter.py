import logging
import re
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Tembusan Basarnas Pusat (SOP Terbaru: Dicantumkan untuk semua jenis laporan)

# 1. TEMPLATE LAKA KAPAL
LAKA_KAPAL_TEMPLATE = """*INFO AWAL*
*LAKA KAPAL {{JUMLAH_SARANA}} ( {{JUMLAH_SARANA_HURUF}} ) UNIT {{DETAIL_JUDUL}}* 

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

*{{MOTTO_BARIS_1}}*
_{{MOTTO_BARIS_2}}_

Mhn izin melaporkan informasi awal Laka Kapal {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF_INLINE}}) unit {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}}

*PELAPOR*
> {{PELAPOR}}
 
*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}  

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING*
> {{HEADING}}

*JARAK*
> {{JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORANG*
- S : {{KORBAN_SELAMAT}} Orang
- MD : {{KORBAN_MENINGGAL}} Orang
- DP : {{KORBAN_HILANG}} Orang

*DATA KORBAN*
{{DATA_KORBAN}}
	
*DATA KAPAL*
{{DATA_KAPAL}}
	
*KRONOLOGI :*
{{KRONOLOGI}}

*Aksi:*
{{AKSI}}

*HASIL*
{{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR STANDBY*
{{ALUT_PALSAR}}

*CUACA*
{{CUACA}}

Demikian sebagai laporan.
*Mhn Ump*

Ttd
*{{TTD_KEPALA}}*"""

DEFAULT_TEMPLATE = LAKA_KAPAL_TEMPLATE

# 2. TEMPLATE LAKA PESAWAT
LAKA_PESAWAT_TEMPLATE = """*INFO AWAL*
*LAKA PESAWAT {{JUMLAH_SARANA}} ( {{JUMLAH_SARANA_HURUF}} ) UNIT {{DETAIL_JUDUL}}* 

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

*{{MOTTO_BARIS_1}}*
_{{MOTTO_BARIS_2}}_

Mhn izin melaporkan informasi awal Laka Pesawat {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF_INLINE}}) unit {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}}

*PELAPOR*
> {{PELAPOR}}
 
*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}  

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING*
> {{HEADING}}

*JARAK*
> {{JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORANG*
- S : {{KORBAN_SELAMAT}} Orang
- MD : {{KORBAN_MENINGGAL}} Orang
- DP : {{KORBAN_HILANG}} Orang

*DATA KORBAN*
{{DATA_KORBAN}}
	
*DATA PESAWAT*
{{DATA_PESAWAT}}
	
*KRONOLOGI :*
{{KRONOLOGI}}

*Aksi:*
{{AKSI}}

*HASIL*
{{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR STANDBY*
{{ALUT_PALSAR}}

*CUACA*
{{CUACA}}

Demikian sebagai laporan.
*Mhn Ump*

Ttd
*{{TTD_KEPALA}}*"""

# 3. TEMPLATE KPK
LAKA_KPK_TEMPLATE = """*INFO AWAL*
*KECELAKAAN DENGAN PENANGANAN KHUSUS {{JUMLAH_SARANA}} ( {{JUMLAH_SARANA_HURUF}} ) UNIT {{DETAIL_JUDUL}}* 

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

*{{MOTTO_BARIS_1}}*
_{{MOTTO_BARIS_2}}_

Mhn izin melaporkan informasi awal Kecelakaan Dengan Penanganan Khusus {{JUMLAH_SARANA}} ({{JUMLAH_SARANA_HURUF_INLINE}}) unit {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}}

*PELAPOR*
> {{PELAPOR}}
 
*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}  

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING*
> {{HEADING}}

*JARAK*
> {{JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORANG*
- S : {{KORBAN_SELAMAT}} Orang
- MD : {{KORBAN_MENINGGAL}} Orang
- DP : {{KORBAN_HILANG}} Orang

*DATA KORBAN*
{{DATA_KORBAN}}
	
*DATA KENDARAAN*
{{DATA_KENDARAAN}}
	
*KRONOLOGI :*
{{KRONOLOGI}}

*Aksi:*
{{AKSI}}

*HASIL*
{{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR STANDBY*
{{ALUT_PALSAR}}

*CUACA*
{{CUACA}}

Demikian sebagai laporan.
*Mhn Ump*

Ttd
*{{TTD_KEPALA}}*"""

# 4. TEMPLATE KMM
KMM_TEMPLATE = """*INFO AWAL*
*KMM {{JUMLAH_KORBAN_TOTAL}} ( {{JUMLAH_KORBAN_HURUF}} ) ORANG {{DETAIL_JUDUL}}* 

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

*{{MOTTO_BARIS_1}}*
_{{MOTTO_BARIS_2}}_

Mhn izin melaporkan informasi awal KMM {{JUMLAH_KORBAN_TOTAL}} ({{JUMLAH_KORBAN_HURUF_INLINE}}) orang {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}}

*PELAPOR*
> {{PELAPOR}}
 
*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}  

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING*
> {{HEADING}}

*JARAK*
> {{JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORANG*
- S : {{KORBAN_SELAMAT}} Orang
- MD : {{KORBAN_MENINGGAL}} Orang
- DP : {{KORBAN_HILANG}} Orang

*DATA KORBAN*
{{DATA_KORBAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*Aksi:*
{{AKSI}}

*HASIL*
{{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR STANDBY*
{{ALUT_PALSAR}}

*CUACA*
{{CUACA}}

Demikian sebagai laporan.
*Mhn Ump*

Ttd
*{{TTD_KEPALA}}*"""

# 5. TEMPLATE BENCANA
BENCANA_TEMPLATE = """*INFO AWAL*
*BENCANA {{JUMLAH_KORBAN_TOTAL}} ( {{JUMLAH_KORBAN_HURUF}} ) ORANG {{DETAIL_JUDUL}}* 

*{{NAMA_INSTANSI}}*
{{HARI_TANGGAL}}

*{{MOTTO_BARIS_1}}*
_{{MOTTO_BARIS_2}}_

Mhn izin melaporkan informasi awal Bencana {{JUMLAH_KORBAN_TOTAL}} ({{JUMLAH_KORBAN_HURUF_INLINE}}) orang {{DETAIL_JUDUL_INLINE}}.

*INFO DITERIMA*
> PDTW {{WAKTU_INFO_DITERIMA}}

*PELAPOR*
> {{PELAPOR}}
 
*WAKTU KEJADIAN*
> PDTW {{WAKTU_KEJADIAN}}  

*LOKASI KEJADIAN*
> {{LOKASI_KEJADIAN}}

*KOORDINAT*
> {{KOORDINAT}}

*HEADING*
> {{HEADING}}

*JARAK*
> {{JARAK}}

*JUMLAH KORBAN = {{JUMLAH_KORBAN_TOTAL}} ORANG*
- S : {{KORBAN_SELAMAT}} Orang
- MD : {{KORBAN_MENINGGAL}} Orang
- DP : {{KORBAN_HILANG}} Orang

*DATA KORBAN*
{{DATA_KORBAN}}

*KRONOLOGI :*
{{KRONOLOGI}}

*Aksi:*
{{AKSI}}

*HASIL*
{{HASIL}}

*UNSUR*
{{UNSUR_SAR}}

*ALUT DAN PALSAR STANDBY*
{{ALUT_PALSAR}}

*CUACA*
{{CUACA}}

Demikian sebagai laporan.
*Mhn Ump*

Ttd
*{{TTD_KEPALA}}*"""

# Fallback template


class MessageFormatterService:
    @staticmethod
    def number_to_words(n: int) -> str:
        """Translates an integer into official Indonesian words."""
        if n == 0:
            return "NIHIL"
        
        satuan = ["", "SATU", "DUA", "TIGA", "EMPAT", "LIMA", "ENAM", "TUJUH", "DELAPAN", "SEMBILAN", "SEPULUH", "SEBELAS"]
        if n < 12:
            return satuan[n]
        elif n < 20:
            return MessageFormatterService.number_to_words(n - 10) + " BELAS"
        elif n < 100:
            utama = n // 10
            sisa = n % 10
            hasil = satuan[utama] + " PULUH"
            if sisa > 0:
                hasil += " " + satuan[sisa]
            return hasil
        elif n < 200:
            return "SERATUS " + MessageFormatterService.number_to_words(n - 100)
        elif n < 1000:
            utama = n // 100
            sisa = n % 100
            hasil = satuan[utama] + " RATUS"
            if sisa > 0:
                hasil += " " + MessageFormatterService.number_to_words(sisa)
            return hasil
        return str(n)

    # Backward compatibility alias
    angka_ke_kata = number_to_words

    @staticmethod
    def format_day_date(dt: datetime, upper: bool = False) -> str:
        """Formats datetime into Indonesian Day, Date Month Year string."""
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

    # Backward compatibility alias
    format_hari_tanggal = format_day_date

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
    def calculate_vehicle_count(data: dict, classification: str) -> int:
        """Calculates the count of vehicles/assets involved safely."""
        if "jumlah_sarana" in data and data["jumlah_sarana"]:
            try:
                return int(data["jumlah_sarana"])
            except:
                pass
        
        key_map = {
            "KAPAL": ["data_kapal", "vessel_data"],
            "PESAWAT": ["data_pesawat", "aircraft_data"],
            "ALAT": ["data_alat", "equipment_data"]
        }
        
        target_keys = ["data_kapal", "vessel_data"]
        for k, v in key_map.items():
            if k in classification.upper():
                target_keys = v
                break
            
        vessel_data = None
        for tk in target_keys:
            if tk in data and data[tk]:
                vessel_data = data[tk]
                break
        if not vessel_data:
            # check inside metadata_kejadian / incident_metadata
            meta = data.get("incident_metadata") or data.get("metadata_kejadian", {})
            for tk in target_keys:
                if tk in meta and meta[tk]:
                    vessel_data = meta[tk]
                    break
            
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

    # Backward compatibility alias
    hitung_sarana = calculate_vehicle_count

    def format_vessel_data(self, data_kapal) -> str:
        """Memformat data kapal secara terperinci sesuai format formal Basarnas."""
        nama = "-"
        gt = "-"
        flag = "Indonesia"
        jenis = ""
        rute = ""
        imo = None
        call_sign = None
        telp = None

        if isinstance(data_kapal, str):
            lines = [line.strip() for line in data_kapal.split("\n") if line.strip()]
            for line in lines:
                if ":" in line:
                    k, v = [part.strip() for part in line.split(":", 1)]
                    k_upper = k.upper().replace("*", "").replace("-", "").strip()
                    if k_upper in ("NAMA", "NAMA KAPAL"):
                        nama = v or "-"
                    elif k_upper in ("GT", "KAPASITAS", "GROSS TONNAGE"):
                        gt = v or "-"
                    elif k_upper in ("FLAG", "BENDERA", "KEBANGSAAN"):
                        flag = v or "Indonesia"
                    elif k_upper in ("TYPE", "JENIS", "JENIS KAPAL", "KAPAL"):
                        jenis = v or ""
                    elif k_upper in ("RUTE", "TRAYEK", "ASAL", "TUJUAN"):
                        rute = v or ""
                    elif k_upper == "IMO":
                        imo = v or None
                    elif k_upper in ("CALL SIGN", "CALLSIGN"):
                        call_sign = v or None
                    elif k_upper in ("TELEPON SATELIT", "TELP"):
                        telp = v or None
                else:
                    line_lower = line.lower()
                    if any(term in line_lower for term in ("pompong", "speedboat", "perahu", "kapal", "yacht", "tugboat", "tongkang")):
                        jenis = line

        elif isinstance(data_kapal, dict):
            nama = data_kapal.get("nama_kapal") or data_kapal.get("nama") or "-"
            gt = data_kapal.get("gt") or data_kapal.get("kapasitas") or "-"
            flag = data_kapal.get("flag") or data_kapal.get("bendera") or "Indonesia"
            jenis = data_kapal.get("type") or data_kapal.get("jenis_kapal") or data_kapal.get("jenis") or ""
            rute = data_kapal.get("rute") or ""
            imo = data_kapal.get("imo") or data_kapal.get("imo_kapal")
            call_sign = data_kapal.get("call_sign") or data_kapal.get("callsign")
            telp = data_kapal.get("telepon_satelit") or data_kapal.get("telp")

        # Normalize default "-"
        if not nama or str(nama).strip() in ("", "-"): nama = "-"
        if not gt or str(gt).strip() in ("", "-"): gt = "-"
        if not flag or str(flag).strip() in ("", "-"): flag = "Indonesia"
        if str(jenis).strip() in ("-", "None"): jenis = ""
        if str(rute).strip() in ("-", "None"): rute = ""

        base_lines = [
            f"* Nama: {nama}",
            f"* GT : {gt}",
            f"* Flag : {flag}",
            f"* Type : {jenis}".rstrip(),
            f"* Rute : {rute}".rstrip()
        ]
        if imo and str(imo).strip() not in ("", "-"):
            base_lines.append(f"* IMO : {imo}")
        if call_sign and str(call_sign).strip() not in ("", "-"):
            base_lines.append(f"* Call Sign: {call_sign}")
        if telp and str(telp).strip() not in ("", "-"):
            base_lines.append(f"* Telepon Satelit: {telp}")

        return "\n".join(base_lines)

    # Backward compatibility alias
    format_data_kapal = format_vessel_data

    def format_aircraft_data(self, data_pesawat) -> str:
        """Memformat data pesawat secara terperinci sesuai format formal Basarnas."""
        nama = "-"
        call_sign = "-"
        flag = "Indonesia"
        jenis = ""
        rute = ""
        operator = None

        if isinstance(data_pesawat, str):
            lines = [line.strip() for line in data_pesawat.split("\n") if line.strip()]
            for line in lines:
                if ":" in line:
                    k, v = [part.strip() for part in line.split(":", 1)]
                    k_upper = k.upper().replace("*", "").replace("-", "").strip()
                    if k_upper in ("NAMA", "NAMA PESAWAT"):
                        nama = v or "-"
                    elif k_upper in ("REGISTER", "CALL SIGN", "CALLSIGN"):
                        call_sign = v or "-"
                    elif k_upper in ("FLAG", "BENDERA", "KEBANGSAAN"):
                        flag = v or "Indonesia"
                    elif k_upper in ("TYPE", "JENIS", "JENIS PESAWAT"):
                        jenis = v or ""
                    elif k_upper in ("RUTE", "TRAYEK"):
                        rute = v or ""
                    elif k_upper == "OPERATOR":
                        operator = v or None
        elif isinstance(data_pesawat, dict):
            nama = data_pesawat.get("nama_pesawat") or data_pesawat.get("nama") or "-"
            call_sign = data_pesawat.get("call_sign") or data_pesawat.get("register") or "-"
            flag = data_pesawat.get("flag") or data_pesawat.get("bendera") or "Indonesia"
            jenis = data_pesawat.get("type") or data_pesawat.get("jenis_pesawat") or data_pesawat.get("jenis") or ""
            rute = data_pesawat.get("rute") or data_pesawat.get("rute_pesawat") or ""
            operator = data_pesawat.get("operator")

        if not nama or str(nama).strip() in ("", "-"): nama = "-"
        if not call_sign or str(call_sign).strip() in ("", "-"): call_sign = "-"
        if not flag or str(flag).strip() in ("", "-"): flag = "Indonesia"
        if str(jenis).strip() in ("-", "None"): jenis = ""
        if str(rute).strip() in ("-", "None"): rute = ""

        base_lines = [
            f"* Nama: {nama}",
            f"* Register / Call Sign: {call_sign}",
            f"* Flag : {flag}",
            f"* Type : {jenis}".rstrip(),
            f"* Rute : {rute}".rstrip()
        ]
        if operator and str(operator).strip() not in ("", "-"):
            base_lines.append(f"* Operator: {operator}")

        return "\n".join(base_lines)

    # Backward compatibility alias
    format_data_pesawat = format_aircraft_data

    def format_equipment_data(self, data_alat) -> str:
        """Memformat data sarana / kendaraan KPK secara terperinci."""
        nama = "-"
        jenis = "-"
        nopol = "-"
        warna = "-"

        if isinstance(data_alat, str):
            lines = [line.strip() for line in data_alat.split("\n") if line.strip()]
            for line in lines:
                if ":" in line:
                    k, v = [part.strip() for part in line.split(":", 1)]
                    k_upper = k.upper().replace("*", "").replace("-", "").strip()
                    if k_upper in ("JENIS", "JENIS KENDARAAN"):
                        jenis = v or "-"
                    elif k_upper in ("NOPOL", "NOMOR POLISI", "NO POLISI"):
                        nopol = v or "-"
                    elif k_upper in ("WARNA", "WARNA KENDARAAN"):
                        warna = v or "-"
                    elif k_upper in ("PEMILIK", "NAMA"):
                        nama = v or "-"
        elif isinstance(data_alat, dict):
            nama = data_alat.get("nama") or data_alat.get("pemilik") or "-"
            jenis = data_alat.get("jenis_kendaraan") or data_alat.get("jenis") or "-"
            nopol = data_alat.get("nopol") or data_alat.get("no_polisi") or "-"
            warna = data_alat.get("warna_kendaraan") or data_alat.get("warna") or "-"

        return (
            f"* Jenis Kendaraan : {jenis}\n"
            f"* Nomor Polisi : {nopol}\n"
            f"* Warna : {warna}\n"
            f"* Pemilik : {nama}".rstrip()
        )

    # Backward compatibility alias
    format_data_alat = format_equipment_data

    def format_victim_details(self, data_korban) -> str:
        """Memformat data korban secara ringkas untuk placeholder RINCIAN_KORBAN."""
        if isinstance(data_korban, str):
            try:
                data_korban = json.loads(data_korban)
            except Exception:
                pass
                
        if isinstance(data_korban, dict) and "daftar_korban" in data_korban:
            data_korban = data_korban["daftar_korban"]
            
        if not isinstance(data_korban, list) or len(data_korban) == 0:
            return "- Belum ada data korban."
            
        blocks = []
        for v in data_korban:
            if isinstance(v, dict):
                nama = v.get("nama") or v.get("nama_korban") or ""
                jk = v.get("jenis_kelamin") or v.get("jk") or ""
                umur = v.get("umur") or ""
                alamat = v.get("alamat") or ""
                
                details = []
                if jk:
                    details.append(str(jk).strip())
                if umur:
                    u_str = str(umur).strip()
                    if not u_str.endswith("Thn") and not u_str.endswith("tahun"):
                        u_str = f"{u_str} Thn"
                    details.append(u_str)
                    
                detail_str = f" ({'/'.join(details)})" if details else ""
                blocks.append(f"- Nama : {nama}{detail_str}\n- Alamat : {alamat}")
            elif isinstance(v, str):
                blocks.append(f"- Nama : {v.strip()}\n- Alamat : ")
                
        return "\n\n".join(blocks)

    # Backward compatibility alias
    format_rincian_korban = format_victim_details

    def format_victim_data(self, data_korban: list, is_kmm_bencana: bool = True, total_korban: int = None) -> str:
        """Memformat data korban secara dinamis dengan format berpenomoran resmi Basarnas."""
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
            block = (
                "1. \tNama: Belum diketahui\n"
                "\tJenis Kelamin : -"
            )
            return block

        if isinstance(data_korban, str):
            try:
                parsed = json.loads(data_korban)
                if isinstance(parsed, list):
                    return self.format_data_korban(parsed, is_kmm_bencana, total_korban)
            except Exception:
                pass
            
            # Non-JSON string
            lines = [line.strip() for line in data_korban.split("\n") if line.strip()]
            formatted_lines = []
            for i, line in enumerate(lines, 1):
                if re.match(r'^\d+\.', line):
                    formatted_lines.append(line)
                else:
                    clean_line = line.lstrip("*- \t")
                    formatted_lines.append(f"{i}. \tNama: {clean_line}\n\tJenis Kelamin : -")
            return "\n\n".join(formatted_lines)

        # It's a list of parsed victims
        formatted_blocks = []
        parsed_count = len(data_korban)
        
        if parsed_count == 0:
            return (
                "1. \tNama: Belum diketahui\n"
                "\tJenis Kelamin : -"
            )
            
        for idx in range(1, parsed_count + 1):
            victim_info = data_korban[idx - 1]
                
            if isinstance(victim_info, dict):
                nama = victim_info.get("nama") or victim_info.get("nama_korban") or ""
                jk = victim_info.get("jenis_kelamin") or victim_info.get("jk") or ""
                umur = victim_info.get("umur") or ""
                alamat = victim_info.get("alamat") or ""
                ciri = victim_info.get("ciri_ciri") or victim_info.get("ciri") or ""
                
                # Normalisasi nilai default "-" / empty
                if not nama or str(nama).strip() in ("", "-"):
                    nama = "Belum diketahui"
                if jk == "-": jk = ""
                if umur == "-": umur = ""
                if alamat == "-": alamat = ""
                if ciri == "-": ciri = ""
                
                # Normalisasi Jenis Kelamin (Laki - Laki / Perempuan)
                jk_norm = "-"
                if jk:
                    jk_upper = str(jk).strip().upper()
                    if jk_upper in ("LAKI-LAKI", "LAKI LAKI", "PRIA", "COWOK", "L", "LAKI"):
                        jk_norm = "Laki - Laki"
                    elif jk_upper in ("PEREMPUAN", "WANITA", "CEWEK", "P"):
                        jk_norm = "Perempuan"
                    else:
                        jk_norm = str(jk).strip()
                        
                block_lines = [
                    f"{idx}. \tNama: {nama}",
                    f"\tJenis Kelamin : {jk_norm}"
                ]
                if umur:
                    umur_str = str(umur).strip()
                    if not re.search(r'\b(thn|tahun)\b', umur_str, re.IGNORECASE):
                        umur_str = f"{umur_str} Thn"
                    block_lines.append(f"\tUmur : {umur_str}")
                if alamat:
                    block_lines.append(f"\tAlamat : {alamat}")
                if ciri:
                    block_lines.append(f"\tCiri-ciri: {ciri}")
                    
                formatted_blocks.append("\n".join(block_lines))
                
            elif isinstance(victim_info, str) and victim_info.strip() not in ("", "-"):
                clean_v = victim_info.strip().lstrip("*- ")
                formatted_blocks.append(f"{idx}. \tNama: {clean_v}\n\tJenis Kelamin : -")
            else:
                formatted_blocks.append(f"{idx}. \tNama: Belum diketahui\n\tJenis Kelamin : -")
            
        return "\n\n".join(formatted_blocks)

    # Backward compatibility aliases
    format_data_korban = format_victim_data
    format_korban = format_victim_data

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
        
        # If already formatted as PDTW (MMDD HHMM <TZ> or MMDDHHMM <TZ>)
        if re.match(r'^\d{4}\s+\d{4}\s+[G-J]$', w_clean, re.IGNORECASE):
            return w_clean.upper()
        if re.match(r'^\d{8}\s+[G-J]$', w_clean, re.IGNORECASE):
            return f"{w_clean[:4]} {w_clean[4:8]} {w_clean[8:].strip().upper()}"
        if re.match(r'^PDTW\s+\d{4}\s+\d{4}\s+[G-J]$', w_clean, re.IGNORECASE):
            return re.sub(r'^PDTW\s+', '', w_clean, flags=re.IGNORECASE).upper()
        if re.match(r'^PDTW\s+\d{8}\s+[G-J]$', w_clean, re.IGNORECASE):
            core = re.sub(r'^PDTW\s+', '', w_clean, flags=re.IGNORECASE).strip()
            return f"{core[:4]} {core[4:8]} {core[8:].strip().upper()}"
            
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
            korban_total_val = int(data.get("JUMLAH_KORBAN_TOTAL") or data.get("total_victims") or data.get("korban_total") or 0)
        except:
            pass

        if korban_total_val == 0:
            # Hitung dari data_korban jika ada
            korban_list = data.get("victim_data") or data.get("data_korban") or data.get("data_korban_payload")
            if isinstance(korban_list, list):
                korban_total_val = len(korban_list)
            elif isinstance(korban_list, dict) and "daftar_korban" in korban_list:
                korban_total_val = len(korban_list["daftar_korban"])

        jumlah_korban_huruf = self.angka_ke_kata(korban_total_val)
        jumlah_korban_huruf_inline = jumlah_korban_huruf.title()

        # Bangun Detail Judul Dinamis
        lokasi_raw = data.get("LOKASI_KEJADIAN") or data.get("location_text") or data.get("lokasi_teks") or ""
        
        # Bersihkan jenis kejadian untuk judul (prioritaskan sub_jenis_kejadian / sub_incident_type jika tersedia)
        sub_jenis = str(
            data.get("sub_incident_type")
            or data.get("sub_jenis_kejadian")
            or (data.get("metadata_kejadian", {}) or {}).get("sub_jenis_kejadian")
            or (data.get("incident_metadata", {}) or {}).get("sub_jenis_kejadian")
            or ""
        ).upper().strip()
        clean_jenis = sub_jenis or str(data.get("incident_type") or data.get("jenis_kejadian") or data.get("KLASIFIKASI") or "").upper()
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
            kronologi = str(data.get("KRONOLOGI") or data.get("chronology") or data.get("kronologi") or "").upper()
            
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
                dk = str(data.get("data_kapal") or data.get("metadata_kejadian", {}).get("data_kapal") or data.get("incident_metadata", {}).get("data_kapal") or "").lower()
                dp = str(data.get("data_pesawat") or data.get("metadata_kejadian", {}).get("data_pesawat") or data.get("incident_metadata", {}).get("data_pesawat") or "").lower()
                
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
                pos_sar = data.get("nearest_sar_post") or data.get("pos_sar_terdekat") or ""
                if "ANAMBAS" in lokasi_upper or "JEMAJA" in lokasi_upper or "ANAMBAS" in pos_sar.upper() or "JEMAJA" in pos_sar.upper():
                    lokasi_upper = f"{lokasi_upper} KABUPATEN KEPULAUAN ANAMBAS"
                elif "NATUNA" in lokasi_upper or "NATUNA" in pos_sar.upper():
                    lokasi_upper = f"{lokasi_upper} KABUPATEN NATUNA"
            
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
                return data.get("NAMA_INSTANSI") or "Badan Nasional Pencarian dan Pertolongan"
            if key == "MOTTO_BARIS_1":
                motto = data.get("MOTTO_INSTANSI") or "Avignam Jagat Samagram\nSelamatlah Alam Semesta"
                lines = [line.strip().strip("*_ ") for line in motto.split("\n") if line.strip()]
                return lines[0] if lines else "Avignam Jagat Samagram"
            if key == "MOTTO_BARIS_2":
                motto = data.get("MOTTO_INSTANSI") or "Avignam Jagat Samagram\nSelamatlah Alam Semesta"
                lines = [line.strip().strip("*_ ") for line in motto.split("\n") if line.strip()]
                return lines[1] if len(lines) > 1 else "Selamatlah Alam Semesta"
            if key == "MOTTO_INSTANSI":
                motto = data.get("MOTTO_INSTANSI") or "Avignam Jagat Samagram\nSelamatlah Alam Semesta"
                lines = [line.strip().strip("*_ ") for line in motto.split("\n") if line.strip()]
                return "\n".join(f"*{line}*" for line in lines)
            if key == "TTD_KEPALA":
                ttd = data.get("TTD_KEPALA") or "SIAGA SAR 01"
                ttd_str = str(ttd).strip()
                if "01" in ttd_str and not ttd_str.upper().startswith("KPP ") and not ttd_str.upper().startswith("SIAGA "):
                    ttd_str = f"KPP {ttd_str}"
                return ttd_str
            
            # 1. Penanganan Tanggal
            if key == "HARI_TANGGAL":
                return hari_tanggal

            if key == "WAKTU_KEJADIAN":
                w_str = data.get("WAKTU_KEJADIAN") or data.get("waktu") or data.get("waktu_kejadian") or ""
                return self.to_basarnas_pdtw(w_str, dt_obj, koordinat_lng=lng_val)

            if key == "WAKTU_INFO_DITERIMA":
                wi_str = data.get("WAKTU_INFO_DITERIMA") or data.get("waktu_info_diterima") or ""
                return self.to_basarnas_pdtw(wi_str, dt_obj, koordinat_lng=lng_val)
                
            if key == "PELAPOR":
                p_val = data.get("PELAPOR") or data.get("pelapor") or data.get("reporter")
                if not p_val or str(p_val).strip() in ("", "-", "None"):
                    nama_p = data.get("reporter_name") or data.get("pelapor_nama") or "Belum Diketahui"
                    telp_p = data.get("reporter_phone") or data.get("pelapor_nomor") or "-"
                    return f"{nama_p} ( {telp_p} )"
                p_str = str(p_val).strip()
                match_p = re.match(r'^(.*?)\s*\((.*?)\)$', p_str)
                if match_p:
                    return f"{match_p.group(1).strip()} ( {match_p.group(2).strip()} )"
                return p_str

            if key == "KOORDINAT":
                lat = data.get("latitude") or data.get("koordinat_lat")
                lng = data.get("longitude") or data.get("koordinat_lng")
                if not lat or not lng:
                    direct_coord = data.get("KOORDINAT") or data.get("koordinat") or data.get("coordinates") or ""
                    from app.services.geo_service import parse_coordinates
                    coords = parse_coordinates(str(direct_coord))
                    if coords:
                        lat, lng = coords
                if lat and lng:
                    try:
                        return self.decimal_to_dms(float(lat), float(lng))
                    except Exception:
                        pass
                direct_coord = data.get("KOORDINAT") or data.get("koordinat") or data.get("coordinates") or "Belum Diketahui"
                return str(direct_coord)
                
            # 2. Penanganan Judul Dinamis
            if key == "DETAIL_JUDUL":
                return detail_judul
            if key == "DETAIL_JUDUL_INLINE":
                return detail_judul.title()
            if key == "KLASIFIKASI_INLINE":
                return active_klasifikasi.title()
            if key == "JUMLAH_SARANA":
                return str(jumlah_sarana)
            if key == "JUMLAH_SARANA_HURUF":
                return jumlah_sarana_huruf
            if key == "JUMLAH_SARANA_HURUF_INLINE":
                return jumlah_sarana_huruf.title()
            if key == "JUMLAH_KORBAN_HURUF":
                return jumlah_korban_huruf
            if key == "JUMLAH_KORBAN_HURUF_INLINE":
                return jumlah_korban_huruf_inline
            if key == "JUMLAH_KORBAN_TOTAL":
                return str(korban_total_val)

            # 3. Penanganan Korban Detail
            if key == "RINCIAN_KORBAN":
                korban_list = data.get("victim_data") or data.get("data_korban")
                if korban_list is None:
                    korban_list = data.get("incident_metadata", {}).get("data_korban") or data.get("metadata_kejadian", {}).get("data_korban")
                return self.format_rincian_korban(korban_list)

            if key == "DATA_KORBAN":
                korban_list = data.get("victim_data") or data.get("data_korban")
                if korban_list is None:
                    korban_list = data.get("incident_metadata", {}).get("data_korban") or data.get("metadata_kejadian", {}).get("data_korban")
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
                    "KORBAN_SELAMAT": ["survived_victims", "korban_selamat", "korban_s"],
                    "KORBAN_MENINGGAL": ["deceased_victims", "korban_meninggal", "korban_md"],
                    "KORBAN_HILANG": ["missing_victims", "korban_hilang", "korban_dp"]
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
            if key in ("DATA_KAPAL", "DATA_PESAWAT", "DATA_KENDARAAN", "DATA_SARANA"):
                meta = data.get("incident_metadata") or data.get("metadata_kejadian") or {}
                if key == "DATA_KAPAL" or active_klasifikasi == "LAKA KAPAL":
                    val = data.get("data_kapal") or meta.get("data_kapal") or data.get("DATA_KAPAL")
                    return self.format_data_kapal(val)
                elif key == "DATA_PESAWAT" or active_klasifikasi == "LAKA PESAWAT":
                    val = data.get("data_pesawat") or meta.get("data_pesawat") or data.get("DATA_PESAWAT")
                    return self.format_data_pesawat(val)
                elif key in ("DATA_KENDARAAN", "DATA_SARANA") or active_klasifikasi == "KPK":
                    val = data.get("data_alat") or meta.get("data_alat") or data.get("DATA_KENDARAAN")
                    return self.format_data_alat(val)
                return "- "

            # 6. Heading dan Jarak Terpisah & Terintegrasi
            pos_sar = data.get("nearest_sar_post") or data.get("pos_sar_terdekat") or "Pos SAR Terdekat"
            
            if key == "HEADING":
                heading = data.get("heading_degree") or data.get("HEADING") or data.get("heading") or data.get("heading_ke_lokasi")
                if heading and str(heading).strip() not in ("", "-", "None", "Tidak terdeteksi"):
                    h_str = str(heading).strip()
                    if "dari" in h_str.lower():
                        return f"{h_str}." if not h_str.endswith(".") else h_str
                    h_clean = h_str.replace("°", "").strip()
                    return f"{h_clean}° dari {pos_sar}."
                hj = data.get("HEADING_JARAK") or data.get("heading_jarak")
                if hj:
                    hj_match = re.search(r'Heading\s+([0-9.,]+°?)\s+dan\s+Jarak\s+([0-9.,]+(?:\s*NM)?)\s+dari\s+(.+)', str(hj), re.IGNORECASE)
                    if hj_match:
                        h_val = hj_match.group(1).replace("°", "").strip()
                        return f"{h_val}° dari {hj_match.group(3).strip()}."
                    if "/" in str(hj):
                        h_part = hj.split("/")[0].strip()
                        if h_part and h_part != "-":
                            return f"{h_part.replace('°', '')}° dari {pos_sar}."
                return f"- dari {pos_sar}."

            if key == "JARAK":
                jarak = data.get("distance_nm") or data.get("JARAK") or data.get("jarak") or data.get("jarak_ke_lokasi")
                if jarak and str(jarak).strip() not in ("", "-", "None", "Tidak terdeteksi"):
                    j_str = str(jarak).strip()
                    if "dari" in j_str.lower():
                        return j_str
                    j_clean = re.sub(r'(?i)\s*nm', '', j_str).strip()
                    return f"{j_clean} Nm dari {pos_sar}"
                hj = data.get("HEADING_JARAK") or data.get("heading_jarak")
                if hj:
                    hj_match = re.search(r'Heading\s+([0-9.,]+°?)\s+dan\s+Jarak\s+([0-9.,]+(?:\s*NM)?)\s+dari\s+(.+)', str(hj), re.IGNORECASE)
                    if hj_match:
                        j_val = re.sub(r'(?i)\s*nm', '', hj_match.group(2)).strip()
                        return f"{j_val} Nm dari {hj_match.group(3).strip()}"
                    if "/" in str(hj):
                        parts = hj.split("/")
                        if len(parts) >= 2:
                            j_part = re.sub(r'(?i)\s*nm', '', parts[1]).strip()
                            if j_part and j_part != "-":
                                return f"{j_part} Nm dari {pos_sar}"
                return f"- Nm dari {pos_sar}"

            if key == "HEADING_JARAK":
                heading = data.get("heading_degree") or data.get("heading") or data.get("heading_ke_lokasi")
                jarak = data.get("distance_nm") or data.get("jarak") or data.get("jarak_ke_lokasi")
                if heading and jarak:
                    heading_str = str(heading).replace("°", "") + "°"
                    jarak_str = str(jarak).upper().replace("NM", "").strip() + " NM"
                    return f"Heading {heading_str} dan Jarak {jarak_str} dari {pos_sar}"
                direct_hj = data.get("HEADING_JARAK") or data.get("heading_jarak")
                if direct_hj and direct_hj.strip() != "" and direct_hj != "Tidak terdeteksi":
                    if "/" in direct_hj:
                        parts = [p.strip() for p in direct_hj.split("/")]
                        if len(parts) >= 2:
                            return f"Heading {parts[0]}° dan Jarak {parts[1]} NM dari {pos_sar}"
                    return direct_hj
                return f"Tidak terdeteksi (Koordinat belum terisi)"

            # 7. Unsur SAR, Alut, Aksi, Hasil Formatter
            if key in ("UNSUR_SAR", "UNSUR"):
                val = data.get("resources_deployed") or data.get("UNSUR_SAR") or data.get("unsur_sar") or data.get("UNSUR") or data.get("unsur")
                if not val or str(val).strip() == "":
                    return "* Pos SAR Terdekat;\n* Potensi SAR Terdekat."
                
                raw_items = []
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            raw_items.append(item.get("nama") or item.get("name") or str(item))
                        else:
                            raw_items.append(str(item))
                elif isinstance(val, str):
                    raw_items = [line.strip() for line in val.split("\n") if line.strip()]
                    
                lines = [re.sub(r'^[\*\-\d\.\s]+', '', it).strip().rstrip(';.,') for it in raw_items if it.strip()]
                formatted_unsur = []
                for i, item in enumerate(lines):
                    sep = "." if i == len(lines) - 1 else ";"
                    formatted_unsur.append(f"* {item}{sep}")
                return "\n".join(formatted_unsur)

            if key in ("ALUT_PALSAR", "ALUT"):
                val = data.get("resources_deployed") or data.get("ALUT_PALSAR") or data.get("alut_palsar") or data.get("ALUT") or data.get("alut")
                if not val or str(val).strip() == "":
                    return "* RIB Pos SAR\n* Palsar Air\n* Pal Komunikasi\n* Pal Keselamatan lainnya"
                    
                raw_items = []
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            raw_items.append(item.get("nama") or item.get("name") or str(item))
                        else:
                            raw_items.append(str(item))
                elif isinstance(val, str):
                    raw_items = [line.strip() for line in val.split("\n") if line.strip()]
                    
                formatted_alut = []
                for it in raw_items:
                    clean_it = re.sub(r'^[\*\-\d\.\s]+', '', it).strip()
                    if clean_it:
                        formatted_alut.append(f"* {clean_it}")
                return "\n".join(formatted_alut)

            if key in ("KRONOLOGI", "AKSI", "HASIL"):
                key_en_map = {"KRONOLOGI": "chronology", "AKSI": "action", "HASIL": "result"}
                val = data.get(key) or data.get(key.lower()) or (data.get(key_en_map.get(key, "")) if key_en_map.get(key) else None)
                if not val or str(val).strip() in ("", "-", "None"):
                    if key == "HASIL":
                        return "* Dalam pencarian / Pemantauan."
                    return "* Belum Diketahui"
                if isinstance(val, str):
                    lines = [line.strip() for line in val.split("\n") if line.strip()]
                    formatted_lines = []
                    for line in lines:
                        if not line.startswith("*"):
                            formatted_lines.append(f"* {line}")
                        else:
                            formatted_lines.append(line)
                    return "\n".join(formatted_lines)

            if key == "CUACA":
                val = data.get("CUACA") or data.get("cuaca")
                if not val or str(val).strip() in ("", "-", "None"):
                    return (
                        "* Cuaca : Cerah berawan\n"
                        "* Gelombang : 0.4 - 1 m\n"
                        "* Suhu\t: 32°C\n"
                        "* Kecepatan angin : 1 - 3 Kts\n"
                        "* Arah Angin : Barat"
                    )
                if isinstance(val, str):
                    lines = [line.strip() for line in val.split("\n") if line.strip()]
                    formatted_weather = []
                    for line in lines:
                        if not line.startswith("*"):
                            formatted_weather.append(f"* {line}")
                        else:
                            formatted_weather.append(line)
                    return "\n".join(formatted_weather)
                return str(val)

            # 8. Alias mapping default
            aliases = {
                "JENIS_KEJADIAN": ["incident_type", "jenis_kejadian", "JENIS_KEJADIAN", "KLASIFIKASI", "klasifikasi"],
                "KLASIFIKASI": ["incident_type", "KLASIFIKASI", "klasifikasi", "jenis_kejadian", "JENIS_KEJADIAN"],
                "WAKTU_KEJADIAN": ["incident_time", "waktu", "WAKTU_KEJADIAN", "waktu_kejadian"],
                "LOKASI_KEJADIAN": ["location_text", "lokasi_teks", "LOKASI_KEJADIAN", "lokasi_kejadian", "lokasi"],
                "KRONOLOGI": ["chronology", "kronologi", "KRONOLOGI"],
                "KOORDINAT": ["coordinates", "coordinate", "koordinat", "KOORDINAT"],
                "CUACA": ["weather", "cuaca", "CUACA"],
                "JUDUL_KEJADIAN": ["incident_title", "judul_kejadian", "JUDUL_KEJADIAN"],
                "WAKTU_INFO_DITERIMA": ["info_received_time", "waktu_info_diterima", "WAKTU_INFO_DITERIMA"],
                "PELAPOR": ["reporter_name", "reporter", "pelapor", "PELAPOR"],
                "HASIL": ["result", "hasil", "HASIL"]
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
