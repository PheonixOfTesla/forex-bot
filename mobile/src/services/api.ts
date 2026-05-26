/**
 * Lightning Bot API Client
 */

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export interface Signal {
  id: string;
  asset: string;
  direction: 'LONG' | 'SHORT';
  confidence: number;
  strategy: string;
  session: string;
  atr: number;
  volume: number;
  entry: number;
  stopLoss: number;
  takeProfit: number;
  riskReward: number;
  createdAt: string;
}

export interface Trade {
  id: string;
  asset: string;
  direction: 'LONG' | 'SHORT';
  pnl: number;
  confidence: number;
  entryPrice: number;
  exitPrice?: number;
  status: 'OPEN' | 'CLOSED' | 'PENDING';
  createdAt: string;
  closedAt?: string;
}

export interface EngineComponent {
  name: string;
  status: 'active' | 'down' | 'degraded';
  lastHeartbeat: string;
  details?: string;
}

export interface EngineStatus {
  status: 'LIVE' | 'PAUSED' | 'STOPPED';
  uptime: number;
  tradeCount: number;
  components: EngineComponent[];
}

export interface DashboardData {
  balance: number;
  todayPnl: number;
  winRate: number;
  openPositions: number;
  signals: Signal[];
  recentTrades: Trade[];
  balanceHistory: number[];
}

export interface RiskSettings {
  maxRiskPerTrade: number;
  maxDailyTrades: number;
  minConfidence: number;
  maxDrawdown: number;
}

export interface Settings {
  risk: RiskSettings;
  enabledAssets: string[];
  alertsEnabled: boolean;
  soundEnabled: boolean;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  // Dashboard
  async getDashboard(): Promise<DashboardData> {
    return this.request<DashboardData>('/api/dashboard');
  }

  // Signals
  async getSignals(): Promise<Signal[]> {
    return this.request<Signal[]>('/api/signals');
  }

  async getSignal(id: string): Promise<Signal> {
    return this.request<Signal>(`/api/signals/${id}`);
  }

  async executeSignal(id: string): Promise<Trade> {
    return this.request<Trade>(`/api/signals/${id}/execute`, {
      method: 'POST',
    });
  }

  async skipSignal(id: string): Promise<void> {
    return this.request<void>(`/api/signals/${id}/skip`, {
      method: 'POST',
    });
  }

  // Trades
  async getTrades(filter?: 'all' | 'wins' | 'losses'): Promise<Trade[]> {
    const query = filter && filter !== 'all' ? `?filter=${filter}` : '';
    return this.request<Trade[]>(`/api/trades${query}`);
  }

  async getTrade(id: string): Promise<Trade> {
    return this.request<Trade>(`/api/trades/${id}`);
  }

  // Engine
  async getEngineStatus(): Promise<EngineStatus> {
    return this.request<EngineStatus>('/api/engine/status');
  }

  async pauseEngine(): Promise<void> {
    return this.request<void>('/api/engine/pause', {
      method: 'POST',
    });
  }

  async resumeEngine(): Promise<void> {
    return this.request<void>('/api/engine/resume', {
      method: 'POST',
    });
  }

  async stopEngine(): Promise<void> {
    return this.request<void>('/api/engine/stop', {
      method: 'POST',
    });
  }

  // Settings
  async getSettings(): Promise<Settings> {
    return this.request<Settings>('/api/settings');
  }

  async updateSettings(settings: Partial<Settings>): Promise<Settings> {
    return this.request<Settings>('/api/settings', {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  }
}

export const api = new ApiClient(API_BASE_URL);
