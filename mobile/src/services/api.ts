const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'https://web-production-7d1c.up.railway.app';

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
}

export const api = new ApiClient();
export default api;
