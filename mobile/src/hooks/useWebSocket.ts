import { useEffect, useRef, useState, useCallback } from 'react';
import { Signal, Trade, EngineStatus } from '../services/api';

// Derive WebSocket URL from API URL
const API_URL = process.env.EXPO_PUBLIC_API_URL || 'https://web-production-7d1c.up.railway.app';
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws';

// Reconnect settings
const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY = 2000;
const MAX_RECONNECT_DELAY = 30000;

type WebSocketMessage =
  | { type: 'signal'; data: Signal }
  | { type: 'trade_update'; data: Trade }
  | { type: 'engine_status'; data: EngineStatus }
  | { type: 'balance_update'; data: { balance: number; pnl: number } }
  | { type: 'heartbeat'; data: { timestamp: number } };

interface UseWebSocketOptions {
  onSignal?: (signal: Signal) => void;
  onTradeUpdate?: (trade: Trade) => void;
  onEngineStatus?: (status: EngineStatus) => void;
  onBalanceUpdate?: (data: { balance: number; pnl: number }) => void;
  autoReconnect?: boolean;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  isWebSocketLive: boolean;
  lastMessage: WebSocketMessage | null;
  error: Error | null;
  reconnect: () => void;
  disconnect: () => void;
}

export function useWebSocket(
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    onSignal,
    onTradeUpdate,
    onEngineStatus,
    onBalanceUpdate,
    autoReconnect = true,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // isConnected = REST API works (always true for UI purposes)
  // isWebSocketLive = actual WebSocket connection state
  const [isConnected] = useState(true);
  const [isWebSocketLive, setIsWebSocketLive] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!autoReconnect || !mountedRef.current) return;
    if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) return;

    clearReconnectTimeout();

    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.current),
      MAX_RECONNECT_DELAY
    );

    reconnectTimeout.current = setTimeout(() => {
      if (mountedRef.current) {
        reconnectAttempts.current++;
        connect();
      }
    }, delay);
  }, [autoReconnect, clearReconnectTimeout]);

  const connect = useCallback(() => {
    // Don't connect if already connected or connecting
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        if (!mountedRef.current) return;
        reconnectAttempts.current = 0;
        setIsWebSocketLive(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);

          switch (message.type) {
            case 'signal':
              onSignal?.(message.data);
              break;
            case 'trade_update':
              onTradeUpdate?.(message.data);
              break;
            case 'engine_status':
              onEngineStatus?.(message.data);
              break;
            case 'balance_update':
              onBalanceUpdate?.(message.data);
              break;
            case 'heartbeat':
              // Keep-alive acknowledged
              break;
          }
        } catch {
          // Silently ignore parse errors
        }
      };

      ws.onerror = () => {
        // Don't log - just track state
        if (!mountedRef.current) return;
        setError(new Error('WebSocket error'));
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        wsRef.current = null;
        setIsWebSocketLive(false);
        scheduleReconnect();
      };

      wsRef.current = ws;
    } catch {
      // Connection failed - schedule reconnect
      scheduleReconnect();
    }
  }, [onSignal, onTradeUpdate, onEngineStatus, onBalanceUpdate, scheduleReconnect]);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    reconnectAttempts.current = MAX_RECONNECT_ATTEMPTS; // Prevent auto-reconnect
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsWebSocketLive(false);
  }, [clearReconnectTimeout]);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttempts.current = 0;
    connect();
  }, [disconnect, connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearReconnectTimeout();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearReconnectTimeout]);

  return {
    isConnected,
    isWebSocketLive,
    lastMessage,
    error,
    reconnect,
    disconnect,
  };
}

// Hook for subscribing to specific message types
export function useWebSocketSignals(
  onNewSignal: (signal: Signal) => void
): { isConnected: boolean } {
  const { isConnected } = useWebSocket({
    onSignal: onNewSignal,
  });

  return { isConnected };
}

export function useWebSocketTradeUpdates(
  onTradeUpdate: (trade: Trade) => void
): { isConnected: boolean } {
  const { isConnected } = useWebSocket({
    onTradeUpdate,
  });

  return { isConnected };
}
