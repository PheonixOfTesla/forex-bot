import { useState, useEffect, useCallback } from 'react';
import {
  api,
  DashboardData,
  Signal,
  Trade,
  EngineStatus,
  Settings,
  WalletData,
  DepositResponse,
  WithdrawResponse,
  TransactionsResponse,
  TransactionType,
  AccountMode,
  BalanceHistoryPoint,
  PredictionsResponse,
  PredictionAccuracy,
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

  const execute = useCallback(async (id: string): Promise<{ success: boolean; trade_id?: string } | null> => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.executeSignal(id);
      return result;
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
      await api.emergencyStop();
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

// Wallet
export function useWallet(): UseApiState<WalletData> {
  return useApiCall(() => api.getWallet(), []);
}

export function useWalletBalanceHistory(days: number = 30): UseApiState<BalanceHistoryPoint[]> {
  return useApiCall(() => api.getWalletBalanceHistory(days), [days]);
}

export function useTransactions(
  page: number = 1,
  pageSize: number = 20,
  type?: TransactionType
): UseApiState<TransactionsResponse> {
  return useApiCall(() => api.getTransactions(page, pageSize, type), [page, pageSize, type]);
}

export function useDeposit() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const deposit = useCallback(
    async (amount: number, paymentMethod?: string): Promise<DepositResponse | null> => {
      try {
        setLoading(true);
        setError(null);
        const result = await api.deposit(amount, paymentMethod);
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

  return { deposit, loading, error };
}

export function useWithdraw() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const withdraw = useCallback(
    async (amount: number, destination?: string): Promise<WithdrawResponse | null> => {
      try {
        setLoading(true);
        setError(null);
        const result = await api.withdraw(amount, destination);
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

  return { withdraw, loading, error };
}

export function useSetWalletMode() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const setMode = useCallback(
    async (mode: AccountMode): Promise<{ success: boolean; balance: number } | null> => {
      try {
        setLoading(true);
        setError(null);
        const result = await api.setWalletMode(mode);
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

  return { setMode, loading, error };
}

// Predictions
export function usePredictions(
  pair?: string,
  timeframe?: string
): UseApiState<PredictionsResponse> {
  return useApiCall(() => api.getPredictions(pair, timeframe), [pair, timeframe]);
}

export function usePredictionAccuracy(): UseApiState<PredictionAccuracy> {
  return useApiCall(() => api.getPredictionAccuracy(), []);
}

// Intelligence
export function useSentiment(): UseApiState<{ fear_greed_index: number; fear_greed_label: string; market_mood: string }> {
  return useApiCall(() => api.getSentiment(), []);
}

export function useMarketSentiment(): UseApiState<any> {
  return useApiCall(() => api.getSentiment(), []);
}

export function useIndicators(): UseApiState<{ indicators: any[]; updated_at: string }> {
  return useApiCall(() => api.getIndicators(), []);
}

export function useTechnicalIndicators(): UseApiState<any> {
  return useApiCall(() => api.getIndicators(), []);
}

export function useInsights(): UseApiState<{ insights: any[]; total: number }> {
  return useApiCall(() => api.getInsights(), []);
}

export function useAIInsights(): UseApiState<any> {
  return useApiCall(() => api.getInsights(), []);
}

export function usePatterns(): UseApiState<{ patterns: any[]; total: number }> {
  return useApiCall(() => api.getPatterns(), []);
}

export function useDetectedPatterns(): UseApiState<any> {
  return useApiCall(() => api.getPatterns(), []);
}
