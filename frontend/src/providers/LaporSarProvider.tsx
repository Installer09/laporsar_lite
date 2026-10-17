'use client';

import { createContext, useContext, useState } from 'react';

interface LaporSarContextType {
  selectedGlobalReport: any;
  setSelectedGlobalReport: (report: any) => void;
  isGlobalReportDetailOpen: boolean;
  setIsGlobalReportDetailOpen: (open: boolean) => void;
  clickedReportIds: string[];
  markReportAsRead: (reportId: string) => void;
}

const LaporSarContext = createContext<LaporSarContextType | undefined>(undefined);

export function LaporSarProvider({ children }: { children: React.ReactNode }) {
  const [selectedGlobalReport, setSelectedGlobalReport] = useState<any>(null);
  const [isGlobalReportDetailOpen, setIsGlobalReportDetailOpen] = useState(false);
  const [clickedReportIds, setClickedReportIds] = useState<string[]>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('clicked_reports');
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch (e) {
          console.error(e);
        }
      }
    }
    return [];
  });

  const markReportAsRead = (reportId: string) => {
    const reportIdStr = String(reportId);
    setClickedReportIds((prev) => {
      if (prev.includes(reportIdStr)) return prev;
      const newClicked = [...prev, reportIdStr];
      if (typeof window !== 'undefined') {
        localStorage.setItem('clicked_reports', JSON.stringify(newClicked));
      }
      return newClicked;
    });
  };

  const handleSetSelectedGlobalReport = (report: any) => {
    setSelectedGlobalReport(report);
    if (report?.id) {
      markReportAsRead(String(report.id));
    }
  };

  return (
    <LaporSarContext.Provider value={{
      selectedGlobalReport,
      setSelectedGlobalReport: handleSetSelectedGlobalReport,
      isGlobalReportDetailOpen,
      setIsGlobalReportDetailOpen,
      clickedReportIds,
      markReportAsRead,
    }}>
      {children}
    </LaporSarContext.Provider>
  );
}

export function useLaporSar() {
  const context = useContext(LaporSarContext);
  if (!context) {
    throw new Error('useLaporSar must be used within a LaporSarProvider');
  }
  return context;
}
