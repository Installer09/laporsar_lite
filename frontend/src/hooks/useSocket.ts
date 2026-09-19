'use client';

import { useEffect, useRef, useState } from 'react';

type SocketMessage = {
  type: string;
  payload: any;
};

export function useSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<SocketMessage | null>(null);
  const [reconnectCount, setReconnectCount] = useState(0);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

    const getWsUrl = () => {
      if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8000/api` : 'http://localhost:8000/api');
      let wsUrl = '';
      if (apiUrl.startsWith('http')) {
        // e.g. http://localhost:8000/api -> ws://localhost:8000/api/ws
        wsUrl = apiUrl.replace(/^http/, 'ws').replace(/\/api\/?$/, '/api/ws');
      } else {
        // fallback
        wsUrl = typeof window !== 'undefined' ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000/api/ws` : 'ws://localhost:8000/api/ws';
      }

      return token ? `${wsUrl}?token=${token}` : wsUrl;
    };

    const wsUrl = getWsUrl();
    console.log(`Connecting to WebSocket: ${wsUrl.split('?')[0]}`);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected successfully');
      setIsConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const message: SocketMessage = JSON.parse(event.data);
        setLastMessage(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        setReconnectCount((prev) => prev + 1);
      }, 3000);
    };

    socketRef.current = socket;

    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [reconnectCount]);

  return { isConnected, lastMessage };
}
