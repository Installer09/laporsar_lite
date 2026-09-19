'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft, 
  HelpCircle, 
  ShieldAlert, 
  Code, 
  Phone, 
  ChevronDown, 
  Copy, 
  Check, 
  BookOpen, 
  Search,
  Building,
  Anchor,
  Activity
} from 'lucide-react';

export default function HelpCenter() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);

  const copyWidgetCode = () => {
    const code = `<iframe src="https://jakarta.laporsar.id/widget/lapor" width="100%" height="600" style="border:none; border-radius:16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.05);" allow="geolocation"></iframe>`;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const faqs = [
    {
      q: "Apa itu Layanan Lapor SAR?",
      a: "Lapor SAR adalah portal resmi terintegrasi yang dikembangkan untuk mempercepat penyampaian laporan musibah darurat (seperti kecelakaan kapal, kecelakaan penerbangan, bencana alam, atau kondisi membahayakan manusia) langsung ke Command Center BASARNAS setempat secara real-time."
    },
    {
      q: "Bagaimana cara kerja Widget Lapor SAR?",
      a: "Widget Lapor SAR adalah aplikasi pelaporan mandiri berbentuk iframe yang dapat disematkan (embedded) di website instansi Anda. Ketika masyarakat melaporkan kejadian melalui widget tersebut, sistem cerdas kami mendeteksi lokasi pelapor, merangkum kronologi kejadian menggunakan AI, dan langsung mengirimkan tiket darurat ke Command Center Kantor SAR terdekat."
    },
    {
      q: "Bagaimana cara memasang widget di website instansi kami?",
      a: "Sangat mudah! Pertama, lakukan pendaftaran akun pelapor melalui tombol 'Daftar Pelapor' di halaman utama. Setelah akun disetujui, Anda akan mendapatkan kode integrasi khusus di dashboard Anda. Cukup salin kode iframe tersebut dan tempel (paste) ke dalam editor HTML website Anda."
    },
    {
      q: "Apakah layanan pelaporan dan integrasi widget dipungut biaya?",
      a: "Tidak. Seluruh layanan Lapor SAR, termasuk pendaftaran, penggunaan dashboard, integrasi widget, dan operasi Pencarian dan Pertolongan (SAR) oleh BASARNAS adalah GRATIS dan bebas dari biaya apapun demi keselamatan masyarakat."
    },
    {
      q: "Seberapa cepat respon tim SAR setelah laporan dikirim?",
      a: "Laporan yang masuk ke Command Center akan segera diverifikasi oleh operator siaga dalam hitungan menit. Setelah divalidasi, Kantor SAR terdekat akan langsung mengaktifkan rencana operasi pertolongan dan mengoordinasikan alut (alat utama) serta unsur SAR terdekat ke lokasi kejadian."
    },
    {
      q: "Mengapa sistem memerlukan izin akses lokasi (Geolocation)?",
      a: "Akses lokasi diperlukan agar sistem dapat menentukan koordinat presisi Lintang (Latitude) dan Bujur (Longitude) lokasi musibah secara otomatis. Hal ini sangat krusial dalam mempercepat proses pencarian, terutama di wilayah perairan atau lokasi terpencil yang sulit dideskripsikan dengan teks."
    }
  ];

  const filteredFaqs = faqs.filter(faq => 
    faq.q.toLowerCase().includes(searchQuery.toLowerCase()) || 
    faq.a.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen w-screen relative overflow-x-hidden bg-gradient-to-br from-slate-50 via-white to-slate-50/50 font-sans flex flex-col justify-between">
      {/* Background Glowing Blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] rounded-full bg-gradient-to-tr from-orange-400/5 to-red-500/5 blur-[130px] pointer-events-none z-0" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[700px] h-[700px] rounded-full bg-gradient-to-tr from-blue-500/5 to-orange-400/5 blur-[150px] pointer-events-none z-0" />

      {/* 1. Top Navigation Header */}
      <header className="w-full z-10 bg-white/80 backdrop-blur-md border-b border-slate-200/80 py-4 px-6 sm:px-8 flex items-center justify-between shadow-sm sticky top-0">
        <button 
          onClick={() => router.push('/')}
          className="flex items-center gap-2 text-slate-700 hover:text-orange-600 transition-colors font-extrabold text-xs cursor-pointer group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Kembali ke Portal
        </button>

        <div className="flex items-center gap-3 select-none">
          <div className="inline-flex items-center justify-center shrink-0">
            <img 
              src="/logo.png" 
              alt="Logo BASARNAS" 
              className="w-8 h-8 object-contain" 
            />
          </div>
          <span className="text-xs font-black text-slate-800 tracking-tight font-sans">
            Pusat Bantuan <span className="bg-gradient-to-r from-orange-500 to-red-600 bg-clip-text text-transparent">Lapor SAR</span>
          </span>
        </div>
      </header>

      {/* 2. Hero Help Banner */}
      <section className="w-full max-w-5xl mx-auto px-6 pt-12 pb-8 text-center z-10 space-y-6">
        <div className="space-y-3">
          <h1 className="text-3xl sm:text-4xl font-black text-slate-900 tracking-tight font-sans">
            Ada yang Bisa Kami Bantu?
          </h1>
          <p className="text-slate-500 text-sm sm:text-base max-w-2xl mx-auto font-medium leading-relaxed">
            Temukan panduan resmi seputar penggunaan sistem, integrasi widget tombol darurat di website Anda, dan prosedur standar pelaporan operasi pertolongan.
          </p>
        </div>

        {/* Search Input bar */}
        <div className="max-w-xl mx-auto relative group">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <Search className="w-4.5 h-4.5 text-slate-400 group-focus-within:text-orange-550 transition-colors" />
          </div>
          <input
            type="text"
            placeholder="Cari pertanyaan, panduan, atau topik bantuan..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-3 bg-white border border-slate-200 rounded-2xl shadow-sm focus:outline-none focus:border-orange-500/50 focus:ring-4 focus:ring-orange-500/10 text-xs sm:text-sm font-medium text-slate-700 transition-all font-sans"
          />
        </div>
      </section>

      {/* 3. Help Guides & Core Topics */}
      <main className="flex-1 w-full max-w-5xl mx-auto px-6 py-6 z-10 space-y-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1: Emergency Guide */}
          <div className="p-6 bg-white border border-slate-200/80 rounded-2xl shadow-sm flex flex-col justify-between space-y-4">
            <div className="space-y-3 text-left">
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-650 flex items-center justify-center font-bold">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-extrabold text-slate-800">Panduan Kondisi Darurat</h3>
              <p className="text-xs text-slate-450 font-medium leading-relaxed">
                Panduan praktis tindakan pertama ketika menghadapi kecelakaan kapal, kecelakaan penerbangan, kondisi membahayakan manusia, atau bencana alam.
              </p>
            </div>
            <div className="pt-2">
              <span className="text-[10px] font-extrabold text-red-650 flex items-center gap-1.5">
                <Phone className="w-3 h-3 animate-bounce" /> Call Center BASARNAS: Siaga 115
              </span>
            </div>
          </div>

          {/* Card 2: Widget Integration Code */}
          <div className="p-6 bg-white border border-slate-200/80 rounded-2xl shadow-sm flex flex-col justify-between space-y-4">
            <div className="space-y-3 text-left">
              <div className="w-10 h-10 rounded-xl bg-orange-50 text-orange-600 flex items-center justify-center font-bold">
                <Code className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-extrabold text-slate-800">Integrasi Widget Lapor</h3>
              <p className="text-xs text-slate-450 font-medium leading-relaxed">
                Salin sebaris kode integrasi iframe Lapor SAR untuk dipasang pada platform media berita, portal desa, atau web instansi daerah Anda.
              </p>
            </div>
            <div className="pt-2">
              <button 
                onClick={copyWidgetCode}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg text-[10px] font-extrabold text-slate-700 transition-all cursor-pointer"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-green-600" /> Tersalin!
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" /> Salin Kode Iframe
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Card 3: Operation Center */}
          <div className="p-6 bg-white border border-slate-200/80 rounded-2xl shadow-sm flex flex-col justify-between space-y-4">
            <div className="space-y-3 text-left">
              <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
                <Building className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-extrabold text-slate-800">Wilayah Kerja SAR</h3>
              <p className="text-xs text-slate-450 font-medium leading-relaxed">
                Daftar Kantor Pencarian dan Pertolongan (Kantor UPT) di seluruh Indonesia. Pastikan koordinat dan wilayah operasional terdaftar dengan benar.
              </p>
            </div>
            <div className="pt-2">
              <button
                onClick={() => router.push('/')}
                className="text-[10px] font-extrabold text-blue-600 hover:text-blue-700 transition-colors flex items-center gap-1"
              >
                <Activity className="w-3.5 h-3.5" /> Lihat Peta Wilayah &rarr;
              </button>
            </div>
          </div>
        </div>

        {/* 4. Interactive Accordion FAQ Section */}
        <section className="space-y-6 pt-6">
          <div className="text-center md:text-left space-y-1.5">
            <h2 className="text-lg font-black text-slate-900 flex items-center justify-center md:justify-start gap-2">
              <HelpCircle className="w-5 h-5 text-orange-550" /> Pertanyaan Sering Diajukan (FAQ)
            </h2>
            <p className="text-xs text-slate-500 font-medium">
              Informasi lengkap seputar mekanisme sistem dan pengajuan integrasi tombol darurat.
            </p>
          </div>

          <div className="border border-slate-200/80 bg-white rounded-2xl divide-y divide-slate-100 overflow-hidden shadow-sm">
            {filteredFaqs.length > 0 ? (
              filteredFaqs.map((faq, index) => {
                const isOpen = activeFaq === index;
                return (
                  <div key={index} className="transition-all bg-white hover:bg-slate-50/20">
                    <button
                      onClick={() => setActiveFaq(isOpen ? null : index)}
                      className="w-full px-6 py-4 flex items-center justify-between gap-4 text-left cursor-pointer focus:outline-none"
                    >
                      <span className="text-xs sm:text-sm font-extrabold text-slate-800">
                        {faq.q}
                      </span>
                      <ChevronDown 
                        className={`w-4 h-4 text-slate-400 shrink-0 transition-transform duration-300 ${
                          isOpen ? 'rotate-180 text-orange-500' : ''
                        }`} 
                      />
                    </button>
                    
                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="px-6 pb-4 pt-1 text-xs sm:text-sm font-medium text-slate-500 leading-relaxed border-t border-slate-50/50 bg-slate-50/30">
                            {faq.a}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })
            ) : (
              <div className="p-8 text-center text-xs font-bold text-slate-450">
                Tidak ada FAQ yang cocok dengan kata kunci pencarian Anda.
              </div>
            )}
          </div>
        </section>

        {/* 5. Detailed Widget Integration Steps */}
        <section className="bg-slate-900 text-slate-100 p-6 sm:p-8 rounded-2xl shadow-xl space-y-6 text-left relative overflow-hidden">
          {/* Subtle Glow Accent inside Dark box */}
          <div className="absolute top-[-50%] right-[-20%] w-[350px] h-[350px] rounded-full bg-gradient-to-tr from-orange-500/20 to-red-500/20 blur-[80px] pointer-events-none z-0" />
          
          <div className="space-y-2 relative z-10">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-orange-500/10 border border-orange-500/20 text-[10px] font-bold text-orange-400">
              <Code className="w-3.5 h-3.5" /> Panduan Developer & Webmaster
            </div>
            <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight">
              Langkah Integrasi Widget Lapor SAR
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 font-medium">
              Ikuti 3 langkah mudah berikut untuk mengaktifkan pelaporan musibah langsung dari website Anda.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10 pt-2 font-medium">
            <div className="space-y-2 bg-white/5 border border-white/10 p-4 rounded-xl">
              <div className="w-6 h-6 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold font-sans">
                1
              </div>
              <h4 className="text-xs font-extrabold text-white">Daftarkan Akun</h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Lakukan registrasi Akun Instansi di halaman utama. Isi detail UPT wilayah dan penanggung jawab operasional.
              </p>
            </div>
            
            <div className="space-y-2 bg-white/5 border border-white/10 p-4 rounded-xl">
              <div className="w-6 h-6 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold font-sans">
                2
              </div>
              <h4 className="text-xs font-extrabold text-white">Salin Kode Iframe</h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Salin kode integration snippet yang tersedia di atas atau yang tertera di dashboard pengelolaan widget akun Anda.
              </p>
            </div>

            <div className="space-y-2 bg-white/5 border border-white/10 p-4 rounded-xl">
              <div className="w-6 h-6 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold font-sans">
                3
              </div>
              <h4 className="text-xs font-extrabold text-white">Tempel di Website</h4>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Sisipkan kode tersebut ke bagian halaman laporan atau sidebar website Anda. Widget siap digunakan masyarakat.
              </p>
            </div>
          </div>

          {/* Copyable Code Block */}
          <div className="bg-slate-950/80 border border-white/5 p-4 rounded-xl relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 font-mono text-[10px] text-slate-300">
            <div className="overflow-x-auto w-full select-all pb-2 sm:pb-0">
              <code>{`<iframe src="https://jakarta.laporsar.id/widget/lapor" width="100%" height="600" allow="geolocation"></iframe>`}</code>
            </div>
            <button 
              onClick={copyWidgetCode}
              className="px-3 py-1.5 bg-orange-500 hover:bg-orange-655 hover:scale-[1.02] text-white font-bold text-[10px] rounded-lg transition-all cursor-pointer flex items-center gap-1.5 shrink-0 self-end sm:self-center font-sans"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5" /> Tersalin
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" /> Salin Kode
                </>
              )}
            </button>
          </div>
        </section>
      </main>

      {/* 6. Footer */}
      <footer className="w-full z-10 bg-slate-50 border-t border-slate-200/60 py-6 px-8 flex flex-col sm:flex-row items-center justify-between gap-4 mt-8">
        <p className="text-[10px] text-slate-450 font-bold flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-slate-400" /> Direktorat Sistem Komunikasi - BASARNAS RI
        </p>
        <p className="text-[10px] text-slate-450 font-semibold font-sans">
          © {new Date().getFullYear()} BASARNAS. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
