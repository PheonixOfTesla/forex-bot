const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'https://forex-bot-ten.vercel.app';

export interface Signal {
  id: string;
  pair: string;
  direction: 'buy' | 'sell';
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  timestamp: string;
  status?: 'active' | 'executed' | 'skipped';
}

export interface Trade {
  id: string;
  pair: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price?: number;
  pnl?: number;
  pnl_pct?: number;
  confidence: number;
  status: 'open' | 'closed' | 'pending';
  opened_at: string;
  closed_at?: string;
}

export interface Position {
  pair: string;
  direction: 'long' | 'short';
  entry_price: number;
  current_price: number;
  pnl: number;
  pnl_pct: number;
  size: number;
}

export interface EngineStatus {
  status: 'running' | 'paused' | 'stopped';
  uptime: string;
  last_trade?: string;
  components: {
    name: string;
    status: 'active' | 'degraded' | 'down';
    latency?: number;
  }[];
}

export interface DashboardData {
  balance: number;
  equity: number;
  today_pnl: number;
  today_pnl_pct: number;
  win_rate: number;
  total_trades: number;
  open_positions_count: number;
  ml_signals: Signal[];
  open_positions: Position[];
}

export interface Settings {
  risk: {
    risk_per_trade: number;
    max_leverage: number;
    min_confidence: number;
    max_daily_loss: number;
    max_open_trades: number;
  };
  notifications: {
    telegram_enabled: boolean;
    trade_alerts: boolean;
    daily_summary: boolean;
  };
  trading: {
    auto_trade: boolean;
    pairs: { [key: string]: boolean };
  };
}

// Wallet Types
export type TransactionType = 'deposit' | 'withdrawal' | 'trade_pnl' | 'fee' | 'adjustment';
export type TransactionStatus = 'pending' | 'completed' | 'failed' | 'cancelled';
export type AccountMode = 'paper' | 'live';

export interface Transaction {
  id: string;
  type: TransactionType;
  amount: number;
  balance_after: number;
  status: TransactionStatus;
  description: string;
  created_at: string;
  completed_at?: string;
  reference?: string;
}

export interface WalletData {
  mode: AccountMode;
  balance: number;
  paper_balance: number;
  live_balance: number;
  available_balance: number;
  pending_deposits: number;
  pending_withdrawals: number;
  total_deposited: number;
  total_withdrawn: number;
  total_pnl: number;
  recent_transactions: Transaction[];
  last_updated: string;
}

export interface DepositResponse {
  success: boolean;
  transaction_id: string;
  amount: number;
  new_balance: number;
  status: TransactionStatus;
  message: string;
  broker_redirect_url?: string;
}

export interface WithdrawResponse {
  success: boolean;
  transaction_id: string;
  amount: number;
  new_balance: number;
  status: TransactionStatus;
  message: string;
  estimated_completion?: string;
  broker_redirect_url?: string;
}

export interface TransactionsResponse {
  transactions: Transaction[];
  total_count: number;
  page: number;
  page_size: number;
}

export interface BalanceHistoryPoint {
  timestamp: string;
  balance: number;
}

// Predictions Types
export interface Prediction {
  pair: string;
  timeframe: string;
  direction: 'UP' | 'DOWN';
  confidence: number;
  current_price: number;
  predicted_low: number;
  predicted_high: number;
  key_factors: string[];
  generated_at: string;
  valid_until: string;
}

export interface PredictionsResponse {
  predictions: Prediction[];
  total: number;
}

export interface PredictionAccuracy {
  overall_accuracy: {
    '1h': number;
    '4h': number;
    '24h': number;
  };
  by_pair: Record<string, {
    '1h': { accuracy: number; total_predictions: number };
    '4h': { accuracy: number; total_predictions: number };
    '24h': { accuracy: number; total_predictions: number };
  }>;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Dashboard
  async getDashboard(): Promise<DashboardData> {
    return this.fetch('/api/v1/dashboard');
  }

  async getBalanceHistory(days: number = 30): Promise<{ timestamp: string; balance: number }[]> {
    return this.fetch(`/api/v1/balance-history?days=${days}`);
  }

  // Signals
  async getSignals(): Promise<Signal[]> {
    return this.fetch('/api/v1/signals');
  }

  async getSignal(id: string): Promise<Signal & { features?: any; strategy?: string }> {
    return this.fetch(`/api/v1/signals/${id}`);
  }

  async executeSignal(id: string): Promise<{ success: boolean; trade_id?: string }> {
    return this.fetch(`/api/v1/signals/${id}/execute`, { method: 'POST' });
  }

  async skipSignal(id: string): Promise<{ success: boolean }> {
    return this.fetch(`/api/v1/signals/${id}/skip`, { method: 'POST' });
  }

  // Engine
  async getEngineStatus(): Promise<EngineStatus> {
    return this.fetch('/api/v1/engine/status');
  }

  async pauseEngine(): Promise<{ success: boolean }> {
    return this.fetch('/api/v1/engine/pause', { method: 'POST' });
  }

  async resumeEngine(): Promise<{ success: boolean }> {
    return this.fetch('/api/v1/engine/resume', { method: 'POST' });
  }

  async emergencyStop(): Promise<{ success: boolean }> {
    return this.fetch('/api/v1/engine/emergency-stop', { method: 'POST' });
  }

  // Trades
  async getTrades(filter?: 'all' | 'wins' | 'losses'): Promise<Trade[]> {
    const query = filter && filter !== 'all' ? `?filter=${filter}` : '';
    return this.fetch(`/api/v1/trades${query}`);
  }

  async getTrade(id: string): Promise<Trade> {
    return this.fetch(`/api/v1/trades/${id}`);
  }

  // Settings
  async getSettings(): Promise<Settings> {
    return this.fetch('/api/v1/settings');
  }

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return this.fetch('/api/v1/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  // Performance
  async getPerformance(days: number = 30): Promise<any> {
    return this.fetch(`/api/v1/performance?days=${days}`);
  }

  // Wallet
  async getWallet(): Promise<WalletData> {
    return this.fetch('/api/v1/wallet');
  }

  async deposit(amount: number, paymentMethod?: string): Promise<DepositResponse> {
    return this.fetch('/api/v1/wallet/deposit', {
      method: 'POST',
      body: JSON.stringify({ amount, payment_method: paymentMethod }),
    });
  }

  async withdraw(amount: number, destination?: string): Promise<WithdrawResponse> {
    return this.fetch('/api/v1/wallet/withdraw', {
      method: 'POST',
      body: JSON.stringify({ amount, destination }),
    });
  }

  async getTransactions(
    page: number = 1,
    pageSize: number = 20,
    type?: TransactionType
  ): Promise<TransactionsResponse> {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (type) params.append('type', type);
    return this.fetch(`/api/v1/wallet/transactions?${params}`);
  }

  async getWalletBalanceHistory(days: number = 30): Promise<BalanceHistoryPoint[]> {
    return this.fetch(`/api/v1/wallet/balance-history?days=${days}`);
  }

  async setWalletMode(mode: AccountMode): Promise<{ success: boolean; current_mode: AccountMode; balance: number }> {
    return this.fetch(`/api/v1/wallet/mode?mode=${mode}`, { method: 'POST' });
  }

  // Predictions
  async getPredictions(pair?: string, timeframe?: string): Promise<PredictionsResponse> {
    const params = new URLSearchParams();
    if (pair) params.append('pair', pair);
    if (timeframe) params.append('timeframe', timeframe);
    const query = params.toString() ? `?${params}` : '';
    return this.fetch(`/api/v1/predictions${query}`);
  }

  async getPredictionAccuracy(): Promise<PredictionAccuracy> {
    return this.fetch('/api/v1/predictions/accuracy');
  }

  // Intelligence
  async getSentiment(): Promise<{ fear_greed_index: number; fear_greed_label: string; market_mood: string }> {
    return this.fetch('/api/v1/intelligence/sentiment');
  }

  async getIndicators(): Promise<{ indicators: any[]; updated_at: string }> {
    return this.fetch('/api/v1/intelligence/indicators');
  }

  async getInsights(): Promise<{ insights: any[]; total: number }> {
    return this.fetch('/api/v1/intelligence/insights');
  }

  async getPatterns(): Promise<{ patterns: any[]; total: number }> {
    return this.fetch('/api/v1/intelligence/patterns');
  }
}

export const api = new ApiClient();
export default api;
