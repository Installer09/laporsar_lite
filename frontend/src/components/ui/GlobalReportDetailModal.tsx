'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  X, User, Phone, AlertTriangle, Calendar, MapPin, Users, Info 
} from 'lucide-react';
import { useLaporSar } from '@/providers/LaporSarProvider';

export function GlobalReportDetailModal() {
  const { 
    selectedGlobalReport, 
    setSelectedGlobalReport, 
    isGlobalReportDetailOpen, 
    setIsGlobalReportDetailOpen 
  } = useLaporSar();

  const handleClose = () => {
    setIsGlobalReportDetailOpen(false);
    setSelectedGlobalReport(null);
  };

  return (
    <AnimatePresence>
      {isGlobalReportDetailOpen && selectedGlobalReport && (
        <>
          {/* Backdrop */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 bg-black z-50 cursor-pointer"
          />
          
          {/* Modal Dialog */}
          <motion.div 
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed inset-0 m-auto w-full max-w-xl h-fit max-h-[85vh] bg-white rounded-3xl shadow-2xl border border-gray-100 z-50 overflow-hidden flex flex-col"
          >
            {/* Modal Header */}
            <div className="p-5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-800">
                  <Info className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-gray-800 text-base">
                    Detail Laporan: {selectedGlobalReport.no_laporan}
                  </h3>
                  <p className="text-[11px] text-gray-500 mt-0.5">
                    Informasi kejadian terekstraksi oleh AI.
                  </p>
                </div>
              </div>
              <button 
                onClick={handleClose}
                className="p-1.5 text-gray-400 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-colors"
                title="Tutup detail laporan"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 text-gray-700 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <User className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-400 font-bold uppercase">Nama Pelapor</p>
                    <p className="font-bold text-gray-800 mt-0.5">{selectedGlobalReport.pelapor_nama}</p>
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <Phone className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-400 font-bold uppercase">Nomor Pelapor</p>
                    <p className="font-bold text-gray-800 mt-0.5 font-mono">{selectedGlobalReport.pelapor_nomor}</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <AlertTriangle className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-gray-400 font-bold uppercase truncate">Jenis Kejadian</p>
                    <p className="font-bold text-gray-800 mt-0.5 truncate">{selectedGlobalReport.jenis_kejadian}</p>
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <Calendar className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-gray-400 font-bold uppercase truncate">Waktu Kejadian</p>
                    <p className="font-bold text-gray-800 mt-0.5 truncate">{selectedGlobalReport.waktu}</p>
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <MapPin className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-[10px] text-gray-400 font-bold uppercase truncate">Lokasi Kejadian</p>
                    <p className="font-bold text-gray-800 mt-0.5 truncate">{selectedGlobalReport.lokasi_teks}</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <Users className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-400 font-bold uppercase">Data Korban</p>
                    <p className="font-bold text-gray-800 mt-0.5">{selectedGlobalReport.korban}</p>
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start gap-3">
                  <Info className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-[10px] text-gray-400 font-bold uppercase">Status Laporan</p>
                    <p className="font-bold text-gray-800 mt-0.5 uppercase tracking-wide">{selectedGlobalReport.status}</p>
                  </div>
                </div>
              </div>

              <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-100 space-y-1">
                <p className="text-[10px] text-gray-400 font-bold uppercase">Kronologi Detail</p>
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{selectedGlobalReport.kronologi}</p>
              </div>

              {selectedGlobalReport.gmaps_link && (
                <div className="p-3 bg-slate-50 text-slate-800 rounded-xl border border-slate-200 flex gap-2">
                  <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                  <div className="text-xs">
                    <p className="font-bold">Informasi Geospasial</p>
                    <a 
                      href={selectedGlobalReport.gmaps_link} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="underline mt-1 block font-semibold text-slate-900 hover:text-slate-700"
                    >
                      Buka Lokasi di Google Maps &rarr;
                    </a>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-100 bg-gray-50 flex items-center justify-end">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 border border-gray-200 hover:bg-gray-100 text-gray-600 font-semibold text-xs rounded-xl transition-all"
              >
                Tutup
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
