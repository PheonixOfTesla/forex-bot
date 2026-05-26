import { useState, useEffect, useCallback } from 'react';
import {
  api,
  DashboardData,
  Signal,
  Trade,
  EngineStatus,
  Settings,
} from '../services/api';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

function useApiCall<T>(
  apiCall: () => Promise<T>,
  dependencies: unknown[] = []
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiCall();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, dependencies);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// Dashboard
export function useDashboard(): UseApiState<DashboardData> {
  return useApiCall(() => api.getDashboard(), []);
}

// Signals
export function useSignals(): UseApiState<Signal[]> {
  return useApiCall(() => api.getSignals(), []);
}

export function useSignal(id: string): UseApiState<Signal> {
  return useApiCall(() => api.getSignal(id), [id]);
}

export function useExecuteSignal() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async (id: string): Promise<Trade | null> => {
    try {
      setLoading(true);
      setError(null);
      const trade = await api.executeSignal(id);
      return trade;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { execute, loading, error };
}

export function useSkipSignal() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const skip = useCallback(async (id: string): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      await api.skipSignal(id);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { skip, loading, error };
}

// Trades
export function useTrades(
  filter: 'all' | 'wins' | 'losses' = 'all'
): UseApiState<Trade[]> {
  return useApiCall(() => api.getTrades(filter), [filter]);
}

export function useTrade(id: string): UseApiState<Trade> {
  return useApiCall(() => api.getTrade(id), [id]);
}

// Engine
export function useEngineStatus(): UseApiState<EngineStatus> {
  return useApiCall(() => api.getEngineStatus(), []);
}

export function useEngineControl() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const pause = useCallback(async (): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      await api.pauseEngine();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const resume = useCallback(async (): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      await api.resumeEngine();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const stop = useCallback(async (): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      await api.stopEngine();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { pause, resume, stop, loading, error };
}

// Settings
export function useSettings(): UseApiState<Settings> {
  return useApiCall(() => api.getSettings(), []);
}

export function useUpdateSettings() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const update = useCallback(
    async (settings: Partial<Settings>): Promise<Settings | null> => {
      try {
        setLoading(true);
        setError(null);
        const result = await api.updateSettings(settings);
        return result;
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return { update, loading, error };
}
