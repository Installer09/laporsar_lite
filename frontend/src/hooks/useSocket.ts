'use client';

import { useEffect, useState } from 'react';
import { getWsUrl } from '@/lib/api';

export type SocketMessage = {
  type?: string;
  event?: string;
  payload?: any;
  [key: string]: any;
};

type MessageListener = (msg: SocketMessage) => void;
type StatusListener = (connected: boolean) => void;

class SocketManager {
  private static instance: SocketManager;
  private socket: WebSocket | null = null;
  private messageListeners: Set<MessageListener> = new Set();
  private statusListeners: Set<StatusListener> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isConnected = false;
  private lastMessage: SocketMessage | null = null;
  private subscriberCount = 0;
  private isExplicitlyClosed = false;

  public static getInstance(): SocketManager {
    if (!SocketManager.instance) {
      SocketManager.instance = new SocketManager();
    }
    return SocketManager.instance;
  }

  public getConnected(): boolean {
    return this.isConnected;
  }

  public getLastMessage(): SocketMessage | null {
    return this.lastMessage;
  }

  public subscribe(onMessage: MessageListener, onStatus: StatusListener): () => void {
    this.subscriberCount++;
    this.messageListeners.add(onMessage);
    this.statusListeners.add(onStatus);

    // Provide initial state
    onStatus(this.isConnected);
    if (this.lastMessage) {
      onMessage(this.lastMessage);
    }

    if (!this.socket || this.socket.readyState === WebSocket.CLOSED) {
      this.connect();
    }

    return () => {
      this.messageListeners.delete(onMessage);
      this.statusListeners.delete(onStatus);
      this.subscriberCount = Math.max(0, this.subscriberCount - 1);

      if (this.subscriberCount === 0) {
        // Disconnect after idle grace period to save resources
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      }
    };
  }

  private connect() {
    if (typeof window === 'undefined') return;
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.isExplicitlyClosed = false;
    const token = localStorage.getItem('token');
    const wsUrl = getWsUrl(token);

    try {
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        this.isConnected = true;
        this.statusListeners.forEach((fn) => fn(true));
      };

      socket.onmessage = (event) => {
        try {
          const parsed: SocketMessage = JSON.parse(event.data);
          this.lastMessage = parsed;
          this.messageListeners.forEach((fn) => fn(parsed));
        } catch {
          // Non-JSON or raw ping/pong message
        }
      };

      socket.onclose = () => {
        this.isConnected = false;
        this.statusListeners.forEach((fn) => fn(false));
        this.socket = null;

        // Only schedule reconnect if there are active subscribers and wasn't explicitly closed
        if (this.subscriberCount > 0 && !this.isExplicitlyClosed) {
          this.reconnectTimer = setTimeout(() => {
            this.connect();
          }, 3000);
        }
      };

      socket.onerror = () => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.close();
        }
      };

      this.socket = socket;
    } catch {
      this.isConnected = false;
      this.statusListeners.forEach((fn) => fn(false));
    }
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}

export function useSocket() {
  const manager = SocketManager.getInstance();
  const [isConnected, setIsConnected] = useState<boolean>(manager.getConnected());
  const [lastMessage, setLastMessage] = useState<SocketMessage | null>(manager.getLastMessage());

  useEffect(() => {
    const unsubscribe = manager.subscribe(
      (msg) => setLastMessage(msg),
      (status) => setIsConnected(status)
    );
    return () => {
      unsubscribe();
    };
  }, [manager]);

  return { isConnected, lastMessage };
}
