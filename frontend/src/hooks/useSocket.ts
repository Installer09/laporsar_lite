'use client';

import { useEffect, useRef, useState } from 'react';
import { getWsUrl } from '@/lib/api';

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
    const wsUrl = getWsUrl(token);
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
