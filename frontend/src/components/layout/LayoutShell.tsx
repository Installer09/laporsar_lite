'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { GlobalReportDetailModal } from "@/components/ui/GlobalReportDetailModal";
import { decodeJwt, getTenantRedirectUrl } from '@/lib/utils';
import { getTenantSlug } from '@/lib/api';

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const currentTenant = getTenantSlug();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isAuthorized, setIsAuthorized] = useState<boolean>(true);
  const [userRole, setUserRole] = useState<string | null>(null);

  const isStaticPublicPage = pathname === '/login' || pathname === '/register' || pathname === '/help-center' || pathname === '/widget-registration' || pathname === '/location-picker';
  const isPublicPage = isStaticPublicPage;

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isStaticPublicPage = pathname === '/login' || pathname === '/register' || pathname === '/help-center' || pathname === '/widget-registration' || pathname === '/location-picker';
      
      const urlParams = new URLSearchParams(window.location.search);
      const isLogout = urlParams.get('logout') === 'true';
      if (isLogout) {
        localStorage.removeItem('token');
        sessionStorage.removeItem('logging_out');
        const params = new URLSearchParams(window.location.search);
        params.delete('logout');
        const searchStr = params.toString();
        const newUrl = window.location.pathname + (searchStr ? `?${searchStr}` : '');
        window.history.replaceState({}, document.title, newUrl);
      }

      const urlToken = urlParams.get('token');
      if (urlToken) {
        localStorage.setItem('token', urlToken);
        const params = new URLSearchParams(window.location.search);
        params.delete('token');
        const searchStr = params.toString();
        const newUrl = window.location.pathname + (searchStr ? `?${searchStr}` : '');
        window.history.replaceState({}, document.title, newUrl);
      }

      const token = localStorage.getItem('token');
      const isPublicPageLocal = isStaticPublicPage || (pathname === '/' && !currentTenant && !token);

      if (token) {
        try {
          const payload = decodeJwt(token);
          if (payload) {
            setUserRole(payload.role);
            if (!isPublicPageLocal) {
              const tokenSlug = payload.tenant_slug ? payload.tenant_slug.toLowerCase().trim() : 'pusat';
              const normalizedTokenTenant = (tokenSlug === 'pusat' || tokenSlug === '') ? 'pusat' : tokenSlug;
              
              const slug = getTenantSlug();
              const currentSlug = slug ? slug.toLowerCase().trim() : 'pusat';
              const normalizedCurrentTenant = (currentSlug === 'pusat' || currentSlug === '') ? 'pusat' : currentSlug;
              
              if (normalizedTokenTenant !== normalizedCurrentTenant) {
                const redirectUrl = getTenantRedirectUrl(payload.tenant_slug);
                if (redirectUrl !== window.location.origin) {
                  const targetUrl = new URL(`${redirectUrl}${window.location.pathname}${window.location.search}`);
                  if (token) {
                    targetUrl.searchParams.set('token', token);
                  }
                  window.location.href = targetUrl.toString();
                  return;
                }
              }
            }

            const role = payload.role;
            
            let authorized = true;
            
            if (!isPublicPageLocal) {
              const cleanRole = role ? String(role).toLowerCase().replace(/[\s_-]/g, '') : '';
              const isSuperAdmin = cleanRole === 'superadmin' || role === 'Super Admin';
              const isOperator = cleanRole === 'operator';
              const isUser = cleanRole === 'user';
              const tokenTenant = payload.tenant_slug ? payload.tenant_slug.toLowerCase().trim() : null;
              const isPusatOrGlobal = !tokenTenant || tokenTenant === 'pusat';

              if (pathname.startsWith('/admin')) {
                // Admin page is strictly for Global / Pusat Super Admin
                if (!isSuperAdmin || !isPusatOrGlobal) {
                  authorized = false;
                }
              } else if (isUser) {
                // User can only access dashboard '/'
                if (pathname !== '/') {
                  authorized = false;
                }
              } else if (isOperator) {
                // Operator cannot access settings
                if (pathname.startsWith('/settings')) {
                  authorized = false;
                }
              }

              // Prevent non-pusat regional tenants from accessing national-dashboard path
              if (pathname.startsWith('/national-dashboard')) {
                if (!isPusatOrGlobal) {
                  authorized = false;
                }
              }
            }

            if (!authorized) {
              setIsAuthorized(false);
              router.push('/');
            } else {
              setIsAuthorized(true);
              setIsAuthenticated(true);
            }
          } else {
            setUserRole(null);
            setIsAuthenticated(false);
            if (sessionStorage.getItem('logging_out') !== 'true') {
              if (!isPublicPageLocal) {
                router.push('/login');
              }
            }
          }
        } catch (e) {
          console.error('Failed to parse token in LayoutShell:', e);
          setUserRole(null);
          setIsAuthenticated(false);
          if (sessionStorage.getItem('logging_out') !== 'true') {
            if (!isPublicPageLocal) {
              router.push('/login');
            }
          }
        }
      } else {
        setUserRole(null);
        setIsAuthenticated(false);
        if (sessionStorage.getItem('logging_out') !== 'true') {
          if (!isPublicPageLocal) {
            router.push('/login');
          }
        }
      }
    }
  }, [pathname, router]);

  if (isPublicPage) {
    return (
      <div className="flex-1 overflow-y-auto h-full w-full bg-gray-50">
        {children}
      </div>
    );
  }

  // 1. Wait until authentication state is resolved from client/localStorage
  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-slate-600"></div>
      </div>
    );
  }

  // 2. Root domain landing page strictly when verified unauthenticated:
  // render children directly without sidebar/header
  if (pathname === '/' && !currentTenant && isAuthenticated === false) {
    return (
      <div className="flex-1 overflow-y-auto h-full w-full">
        {children}
      </div>
    );
  }

  // 3. Unauthorized or unauthenticated
  if (!isAuthenticated || !isAuthorized) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-slate-600"></div>
      </div>
    );
  }

  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-y-auto p-8">
          {children}
        </main>
      </div>
      <GlobalReportDetailModal />
    </>
  );
}

