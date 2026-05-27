import { useEffect, useRef, useState, useCallback } from 'react';
import { Signal, Trade, EngineStatus } from '../services/api';

// Derive WebSocket URL from API URL
const API_URL = process.env.EXPO_PUBLIC_API_URL || 'https://web-production-7d1c.up.railway.app';
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws';

// Reconnect settings
const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_RECONNECT_DELAY = 3000;
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
  reconnectInterval?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
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
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    // Stop if max attempts reached
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      console.log('[WebSocket] Max reconnect attempts reached, giving up');
      return;
    }

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        console.log('[WebSocket] Connected');
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0; // Reset on successful connection
      };

      ws.onmessage = (event) => {
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
              // Keep-alive, no action needed
              break;
          }
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event);
        setError(new Error('WebSocket connection error'));
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        if (autoReconnect && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          // Exponential backoff: 3s, 6s, 12s, 24s, 30s (capped)
          const delay = Math.min(
            INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current - 1),
            MAX_RECONNECT_DELAY
          );
          console.log(`[WebSocket] Reconnecting in ${delay / 1000}s (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      wsRef.current = ws;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }, [
    onSignal,
    onTradeUpdate,
    onEngineStatus,
    onBalanceUpdate,
    autoReconnect,
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const reconnect = useCallback(() => {
    disconnect();
    connect();
  }, [disconnect, connect]);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
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
