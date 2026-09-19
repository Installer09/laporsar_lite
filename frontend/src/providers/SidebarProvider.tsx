'use client';

import { createContext, useContext, useState, useEffect } from 'react';

interface SidebarContextType {
  isSidebarOpen: boolean;
  setIsSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined);

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('sarbot_is_sidebar_open');
      if (saved !== null) {
        return saved === 'true';
      }
    }
    return true;
  });

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => {
      const newVal = !prev;
      localStorage.setItem('sarbot_is_sidebar_open', newVal.toString());
      return newVal;
    });
  };

  const handleSetOpen = (open: boolean) => {
    setIsSidebarOpen(open);
    localStorage.setItem('sarbot_is_sidebar_open', open.toString());
  };

  return (
    <SidebarContext.Provider value={{
      isSidebarOpen,
      setIsSidebarOpen: handleSetOpen,
      toggleSidebar
    }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const context = useContext(SidebarContext);
  if (!context) {
    throw new Error('useSidebar must be used within a SidebarProvider');
  }
  return context;
}
