import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type TradingMode = 'paper' | 'live';

export interface ApiKeys {
  oandaAccountId: string;
  oandaAccessToken: string;
}

interface TradingModeContextType {
  mode: TradingMode;
  apiKeys: ApiKeys;
  isLoading: boolean;
  setMode: (mode: TradingMode) => Promise<void>;
  setApiKeys: (keys: ApiKeys) => Promise<void>;
  validateApiKeys: () => boolean;
  clearApiKeys: () => Promise<void>;
}

const STORAGE_KEYS = {
  MODE: '@trading_mode',
  API_KEYS: '@trading_api_keys',
};

const DEFAULT_API_KEYS: ApiKeys = {
  oandaAccountId: '',
  oandaAccessToken: '',
};

const TradingModeContext = createContext<TradingModeContextType | undefined>(
  undefined
);

interface TradingModeProviderProps {
  children: ReactNode;
}

export const TradingModeProvider: React.FC<TradingModeProviderProps> = ({
  children,
}) => {
  const [mode, setModeState] = useState<TradingMode>('paper');
  const [apiKeys, setApiKeysState] = useState<ApiKeys>(DEFAULT_API_KEYS);
  const [isLoading, setIsLoading] = useState(true);

  // Load persisted state on mount
  useEffect(() => {
    const loadPersistedState = async () => {
      try {
        const [storedMode, storedKeys] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.MODE),
          AsyncStorage.getItem(STORAGE_KEYS.API_KEYS),
        ]);

        if (storedMode) {
          setModeState(storedMode as TradingMode);
        }

        if (storedKeys) {
          setApiKeysState(JSON.parse(storedKeys));
        }
      } catch (error) {
        console.error('Error loading trading mode state:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadPersistedState();
  }, []);

  const setMode = useCallback(async (newMode: TradingMode) => {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.MODE, newMode);
      setModeState(newMode);
    } catch (error) {
      console.error('Error saving trading mode:', error);
      throw error;
    }
  }, []);

  const setApiKeys = useCallback(async (keys: ApiKeys) => {
    try {
      await AsyncStorage.setItem(STORAGE_KEYS.API_KEYS, JSON.stringify(keys));
      setApiKeysState(keys);
    } catch (error) {
      console.error('Error saving API keys:', error);
      throw error;
    }
  }, []);

  const validateApiKeys = useCallback(() => {
    return (
      apiKeys.oandaAccountId.trim().length > 0 &&
      apiKeys.oandaAccessToken.trim().length > 0
    );
  }, [apiKeys]);

  const clearApiKeys = useCallback(async () => {
    try {
      await AsyncStorage.removeItem(STORAGE_KEYS.API_KEYS);
      setApiKeysState(DEFAULT_API_KEYS);
    } catch (error) {
      console.error('Error clearing API keys:', error);
      throw error;
    }
  }, []);

  const value: TradingModeContextType = {
    mode,
    apiKeys,
    isLoading,
    setMode,
    setApiKeys,
    validateApiKeys,
    clearApiKeys,
  };

  return (
    <TradingModeContext.Provider value={value}>
      {children}
    </TradingModeContext.Provider>
  );
};

export const useTradingMode = (): TradingModeContextType => {
  const context = useContext(TradingModeContext);
  if (context === undefined) {
    throw new Error('useTradingMode must be used within a TradingModeProvider');
  }
  return context;
};

export default TradingModeContext;
