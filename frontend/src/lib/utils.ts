import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function decodeJwt(token: string): any {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    let base64Url = parts[1];
    let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4) {
      base64 += '=';
    }
    const jsonPayload = decodeURIComponent(
      window.atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error('Failed to decode JWT:', e);
    return null;
  }
}

export function getTenantRedirectUrl(targetTenant: string | null): string {
  if (typeof window === 'undefined') return '/';
  
  const host = window.location.host;
  const hostname = window.location.hostname.toLowerCase();
  const protocol = window.location.protocol;
  const port = window.location.port;

  // For local development, IPs, tunnels, and LAN environments, keep origin intact
  if (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.match(/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/) ||
    hostname.includes('trycloudflare.com') ||
    hostname.includes('pages.dev') ||
    hostname.includes('vercel.app') ||
    hostname.includes('ngrok') ||
    hostname.endsWith('.lan') ||
    hostname === 'laporsar.lan'
  ) {
    return `${protocol}//${host}`;
  }
  
  const cleanTarget = (!targetTenant || targetTenant === 'pusat') ? null : targetTenant;
  const portSuffix = port ? `:${port}` : '';
  let newHost = host;
  
  if (hostname.endsWith('localhost')) {
    if (cleanTarget) {
      newHost = `${cleanTarget}.localhost${portSuffix}`;
    } else {
      newHost = `localhost${portSuffix}`;
    }
  } else {
    const parts = hostname.split('.');
    
    // Check if current hostname is a root domain or subdomain
    // Root domains: laporsar.lan (2 parts), laporsar.basarnas.go.id (starts with laporsar)
    const isRootDomain = parts[0] === 'laporsar' || parts[0] === 'www' || parts.length <= 2;
    
    const baseDomain = isRootDomain 
      ? (parts[0] === 'www' ? parts.slice(1).join('.') : hostname)
      : parts.slice(1).join('.');
    
    if (cleanTarget) {
      newHost = `${cleanTarget}.${baseDomain}${portSuffix}`;
    } else {
      newHost = `${baseDomain}${portSuffix}`;
    }
  }
  
  return `${protocol}//${newHost}`;
}

export const tenantJurisdictionKeywords: Record<string, string[]> = {
  natuna: [
    'natuna', 
    'anambas', 
    'tarempa', 
    'ranai', 
    'subi', 
    'midai', 
    'serasan', 
    'bunguran',
    'kepulauan anambas'
  ]
};

export function resolveTenantFromCity(cityInput: string, tenantsList: any[]): string {
  const cleanInput = (cityInput || '').toLowerCase().trim();
  if (!cleanInput) return 'pusat';
  
  for (const [slug, keywords] of Object.entries(tenantJurisdictionKeywords)) {
    const tenantExists = tenantsList.some(t => t.slug === slug);
    if (tenantExists) {
      for (const keyword of keywords) {
        if (cleanInput.includes(keyword)) {
          return slug;
        }
      }
    }
  }
  
  for (const tenant of tenantsList) {
    if (tenant.slug !== 'pusat') {
      const cleanTenantName = tenant.name.toLowerCase();
      const cleanName = cleanTenantName.replace(/kantor|sar|kelas|basarnas/gi, '').trim();
      const keywordsInName = cleanName.split(/\s+/);
      for (const kw of keywordsInName) {
        if (kw.length > 2 && cleanInput.includes(kw)) {
          return tenant.slug;
        }
      }
    }
  }
  
  return 'pusat';
}

/**
 * Sanitize cell values for CSV export to prevent CSV Formula Injection (CWE-1236).
 * Prepends a single quote if the string begins with =, +, -, @, \t, or \r.
 */
export function sanitizeCsvCell(val: any): string {
  if (val === null || val === undefined) return '';
  const str = String(val).replace(/\r\n|\r|\n/g, ' ').trim();
  if (str.length > 0 && ['=', '+', '-', '@', '\t', '\r'].includes(str[0])) {
    return `'${str}`;
  }
  return str;
}

