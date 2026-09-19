'use client';

import { createContext, useContext, useState, useEffect } from 'react';

interface LaporSarContextType {
  isLaporSarOpen: boolean;
  setIsLaporSarOpen: (open: boolean) => void;
  laporSarUserId: string;
  setLaporSarUserId: (id: string) => void;
  laporSarName: string;
  setLaporSarName: (name: string) => void;
  laporSarPhone: string;
  setLaporSarPhone: (phone: string) => void;
  selectedGlobalReport: any;
  setSelectedGlobalReport: (report: any) => void;
  isGlobalReportDetailOpen: boolean;
  setIsGlobalReportDetailOpen: (open: boolean) => void;
  clickedReportIds: string[];
  markReportAsRead: (reportId: string) => void;
  isLaporSarRegistered: boolean;
  setIsLaporSarRegistered: (registered: boolean) => void;
}

const LaporSarContext = createContext<LaporSarContextType | undefined>(undefined);

export function LaporSarProvider({ children }: { children: React.ReactNode }) {
  const [isLaporSarOpen, setIsLaporSarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('sarbot_is_lapor_sar_open') === 'true';
    }
    return false;
  });
  const [laporSarUserId, setLaporSarUserId] = useState(() => {
    if (typeof window !== 'undefined') {
      const savedUser = localStorage.getItem('sarbot_lapor_sar_user_id');
      if (savedUser) return savedUser;
      const newUser = 'web_user_' + Math.floor(10000 + Math.random() * 90000);
      localStorage.setItem('sarbot_lapor_sar_user_id', newUser);
      return newUser;
    }
    return '';
  });
  const [laporSarName, setLaporSarName] = useState(() => {
    if (typeof window !== 'undefined') {
      const savedName = localStorage.getItem('sarbot_lapor_sar_name');
      if (savedName && savedName !== 'Pelapor Web' && savedName !== 'Web User') {
        return savedName;
      }
    }
    return '';
  });
  const [laporSarPhone, setLaporSarPhone] = useState(() => {
    if (typeof window !== 'undefined') {
      const savedPhone = localStorage.getItem('sarbot_lapor_sar_phone');
      if (savedPhone && savedPhone !== '08123456789') {
        return savedPhone;
      }
    }
    return '';
  });
  const [isLaporSarRegistered, setIsLaporSarRegistered] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('sarbot_lapor_sar_registered') === 'true';
    }
    return false;
  });
  
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

  // Persist states to localStorage when they change
  useEffect(() => {
    localStorage.setItem('sarbot_is_lapor_sar_open', isLaporSarOpen.toString());
  }, [isLaporSarOpen]);

  useEffect(() => {
    if (laporSarUserId) {
      localStorage.setItem('sarbot_lapor_sar_user_id', laporSarUserId);
    }
  }, [laporSarUserId]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('sarbot_lapor_sar_registered', isLaporSarRegistered.toString());
    }
  }, [isLaporSarRegistered]);

  useEffect(() => {
    if (laporSarName) {
      localStorage.setItem('sarbot_lapor_sar_name', laporSarName);
    } else if (typeof window !== 'undefined') {
      localStorage.removeItem('sarbot_lapor_sar_name');
    }
  }, [laporSarName]);

  useEffect(() => {
    if (laporSarPhone) {
      localStorage.setItem('sarbot_lapor_sar_phone', laporSarPhone);
    } else if (typeof window !== 'undefined') {
      localStorage.removeItem('sarbot_lapor_sar_phone');
    }
  }, [laporSarPhone]);

  return (
    <LaporSarContext.Provider value={{
      isLaporSarOpen,
      setIsLaporSarOpen,
      laporSarUserId,
      setLaporSarUserId,
      laporSarName,
      setLaporSarName,
      laporSarPhone,
      setLaporSarPhone,
      selectedGlobalReport,
      setSelectedGlobalReport: handleSetSelectedGlobalReport,
      isGlobalReportDetailOpen,
      setIsGlobalReportDetailOpen,
      clickedReportIds,
      markReportAsRead,
      isLaporSarRegistered,
      setIsLaporSarRegistered
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
