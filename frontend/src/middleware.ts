import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const host = (request.headers.get('host') || '').toLowerCase();

  // Ignore tunnels, preview platforms, and cloudflare quick tunnel
  if (
    host.includes('trycloudflare.com') ||
    host.includes('pages.dev') ||
    host.includes('vercel.app') ||
    host.includes('ngrok')
  ) {
    return NextResponse.next();
  }

  // Ignore raw IP addresses (IPv4 or IPv6 with optional port)
  const cleanHost = host.split(':')[0].replace(/^\[|\]$/g, '');
  if (/^\d+\.\d+\.\d+\.\d+$/.test(cleanHost) || cleanHost === 'localhost' || cleanHost === '127.0.0.1' || cleanHost.includes(':')) {
    return NextResponse.next();
  }

  // Get subdomain
  const parts = host.split('.');
  if (parts.length > 1) {
    const subdomain = parts[0];
    
    // Ignore internal next.js or dev domains
    const ignoredSubdomains = ['www', 'admin', 'localhost', '127', 'api', 'laporsar'];
    
    // Skip checking if it is a numeric IP or ignored subdomain
    if (!ignoredSubdomains.includes(subdomain) && !subdomain.match(/^\d+$/)) {
      // Set tenant cookie so that the client can read it securely
      const response = NextResponse.next();
      response.cookies.set('tenant-slug', subdomain, {
        path: '/',
        sameSite: 'lax',
        secure: process.env.NODE_ENV === 'production',
      });
      return response;
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};
