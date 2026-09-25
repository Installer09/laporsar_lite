'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, 
  FileText, 
  Users, 
  Settings, 
  BookOpen, 
  Activity,
  MessageCircle,
  LogOut,
  Shield,
  Globe,
  HardDrive
} from 'lucide-react';
import { cn, decodeJwt } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { useSidebar } from '@/providers/SidebarProvider';
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getIdentity, getBackendUrl } from '@/lib/api';

const menuItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/', section: 'Operasional' },
  { icon: FileText, label: 'Laporan Masuk', href: '/reports', section: 'Operasional' },
  { icon: MessageCircle, label: 'Chat Manual', href: '/chat', section: 'Operasional' },
  { icon: Users, label: 'Database Kontak', href: '/contacts', section: 'Operasional' },
  { icon: BookOpen, label: 'Kamus Istilah', href: '/knowledge', section: 'Pengayaan Data' },
  { icon: HardDrive, label: 'Penyimpanan Berkas', href: '/storage', section: 'Sistem' },
  { icon: Settings, label: 'Pengaturan', href: '/settings', section: 'Sistem' },
];

export function Sidebar() {
  const pathname = usePathname();
  const { isSidebarOpen } = useSidebar();
  const [userRole, setUserRole] = useState<string | null>(null);
  const [tenantSlug, setTenantSlug] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  const { data: identityData } = useQuery({
    queryKey: ['identity'],
    queryFn: getIdentity,
  });

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      const payload = decodeJwt(token);
      if (payload) {
        setUserRole(payload.role);
        setTenantSlug(payload.tenant_slug || null);
      }
    }
    setIsLoaded(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const dynamicMenuItems = isLoaded
    ? menuItems.filter((item) => {
        if (userRole === 'User') {
          return item.href === '/';
        }
        if (userRole === 'Operator') {
          return item.href !== '/settings';
        }
        return true;
      })
    : [];



  const isSuperAdmin = userRole === 'Super Admin' || userRole === 'super_admin' || userRole === 'SuperAdmin';
  const isPusatOrGlobal = !tenantSlug || tenantSlug === 'pusat';

  if (isSuperAdmin && isPusatOrGlobal) {
    dynamicMenuItems.push({ icon: Shield, label: 'Administrator', href: '/admin', section: 'Sistem' });
  }

  const sections = ['Operasional', 'Pengayaan Data', 'Sistem'];

  return (
    <motion.div 
      animate={{ width: isSidebarOpen ? 256 : 72 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="h-screen bg-white text-slate-700 flex flex-col border-r border-slate-200/80 shrink-0 overflow-hidden"
    >
      {/* Brand Header */}
      <div className={cn(
        "p-4 flex items-center border-b border-slate-200/80 overflow-hidden h-20 shrink-0",
        isSidebarOpen ? "gap-3 px-6" : "justify-center px-2"
      )}>
        {identityData?.identitas_logo_path ? (
          <img 
            src={`${getBackendUrl().replace(/\/api\/?$/, '')}/${identityData.identitas_logo_path}`} 
            alt="Logo" 
            className="w-10 h-10 object-contain rounded-lg shrink-0 shadow-md p-0.5 border border-slate-100" 
          />
        ) : (
          <div className="w-10 h-10 bg-orange-600 rounded-lg flex items-center justify-center shrink-0 shadow-lg shadow-orange-600/10">
            <Activity className="text-white w-6 h-6" />
          </div>
        )}
        <AnimatePresence initial={false}>
          {isSidebarOpen && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: 'auto' }}
              exit={{ opacity: 0, width: 0 }}
              transition={{ duration: 0.2 }}
              className="flex flex-col whitespace-nowrap min-w-0"
            >
              <h1 className="font-bold text-base text-slate-900 tracking-wide leading-tight">Lapor SAR</h1>
              <p className="text-[10px] text-slate-500 font-medium tracking-wider">COMMAND CENTER V3</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      
      {/* Navigation Menu */}
      <nav className="flex-1 py-4 px-3 space-y-3 overflow-y-auto overflow-x-hidden">
        {sections.map((section, idx) => {
          const sectionItems = dynamicMenuItems.filter((item) => item.section === section);
          if (sectionItems.length === 0) return null;

          return (
            <div key={section} className="space-y-1">
              {idx > 0 && !isSidebarOpen && (
                <div className="border-t border-slate-150 my-2 mx-1" />
              )}
              <AnimatePresence initial={false}>
                {isSidebarOpen && (
                  <motion.div 
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-2 mt-3 whitespace-nowrap"
                  >
                    {section}
                  </motion.div>
                )}
              </AnimatePresence>

              {sectionItems.map((item) => {
                const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
                return (
                  <Link key={item.href} href={item.href} className="block relative">
                    {isActive && (
                      <motion.div
                        layoutId="active-nav-bg"
                        className="absolute inset-0 bg-orange-50 rounded-lg border border-orange-100/50"
                        initial={false}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                      />
                    )}
                    <div className={cn(
                      "relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                      isSidebarOpen ? "justify-start" : "justify-center",
                      isActive ? "text-orange-600" : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    )}
                    title={!isSidebarOpen ? item.label : undefined}
                    >
                      <item.icon className={cn("w-5 h-5 shrink-0 transition-colors duration-200", isActive ? "text-orange-500" : "text-slate-400")} />
                      <AnimatePresence initial={false}>
                        {isSidebarOpen && (
                          <motion.span
                            initial={{ opacity: 0, width: 0 }}
                            animate={{ opacity: 1, width: 'auto' }}
                            exit={{ opacity: 0, width: 0 }}
                            transition={{ duration: 0.2 }}
                            className="whitespace-nowrap truncate min-w-0"
                          >
                            {item.label}
                          </motion.span>
                        )}
                      </AnimatePresence>
                    </div>
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>
      

    </motion.div>
  );
}
