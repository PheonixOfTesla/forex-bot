import React, { useCallback } from 'react';
import { StatusBar } from 'expo-status-bar';
import { View, StyleSheet, ActivityIndicator, Platform } from 'react-native';
import { NavigationContainer, DefaultTheme, LinkingOptions } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import {
  useFonts,
  Rajdhani_400Regular,
  Rajdhani_500Medium,
  Rajdhani_600SemiBold,
  Rajdhani_700Bold,
} from '@expo-google-fonts/rajdhani';
import * as SplashScreen from 'expo-splash-screen';

import { TabNavigator } from './src/navigation';
import { colors } from './src/theme';
import { TradingModeProvider } from './src/context/TradingModeContext';

// Type definitions for navigation
type SignalsStackParamList = {
  SignalsList: undefined;
  SignalDetail: { signalId: string };
};

type WalletStackParamList = {
  WalletMain: undefined;
  Deposit: undefined;
  Withdraw: undefined;
};

type SettingsStackParamList = {
  SettingsMain: undefined;
  EngineStatus: undefined;
  History: undefined;
};

type DashboardStackParamList = {
  DashboardMain: undefined;
  History: undefined;
};

type PredictStackParamList = {
  PredictMain: undefined;
};

type IntelStackParamList = {
  IntelMain: undefined;
};

type RootTabParamList = {
  Home: undefined;
  Signals: undefined;
  Predict: undefined;
  Wallet: undefined;
  Intel: undefined;
  Settings: undefined;
};

// Linking configuration for web navigation
const linking: LinkingOptions<RootTabParamList> = {
  prefixes: [
    // Add your app's URL scheme here
    'forexbot://',
    // Web URLs - only add on web platform
    ...(Platform.OS === 'web' ? [typeof window !== 'undefined' ? window.location.origin : ''] : []),
  ],
  config: {
    screens: {
      Home: {
        path: 'home',
        screens: {
          DashboardMain: '',
          History: 'history',
        },
      },
      Signals: {
        path: 'signals',
        screens: {
          SignalsList: '',
          SignalDetail: 'detail/:signalId',
        },
      },
      Predict: {
        path: 'predict',
        screens: {
          PredictMain: '',
        },
      },
      Wallet: {
        path: 'wallet',
        screens: {
          WalletMain: '',
          Deposit: 'deposit',
          Withdraw: 'withdraw',
        },
      },
      Intel: {
        path: 'intel',
        screens: {
          IntelMain: '',
        },
      },
      Settings: {
        path: 'settings',
        screens: {
          SettingsMain: '',
          EngineStatus: 'engine',
          History: 'history',
        },
      },
    },
  },
};

// Prevent splash screen from auto-hiding
SplashScreen.preventAutoHideAsync();

// Custom dark theme for Lightning Bot
const LightningTheme = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.lpCyan,
    background: colors.lpBlack,
    card: colors.lpSurface,
    text: colors.textPrimary,
    border: colors.borderDark,
    notification: colors.lpCyan,
  },
};

export default function App() {
  const [fontsLoaded] = useFonts({
    Rajdhani_400Regular,
    Rajdhani_500Medium,
    Rajdhani_600SemiBold,
    Rajdhani_700Bold,
  });

  const onLayoutRootView = useCallback(async () => {
    if (fontsLoaded) {
      await SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.lpCyan} />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <TradingModeProvider>
        <View style={styles.container} onLayout={onLayoutRootView}>
          <NavigationContainer theme={LightningTheme} linking={linking}>
            <TabNavigator />
          </NavigationContainer>
          <StatusBar style="light" />
        </View>
      </TradingModeProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.lpBlack,
  },
  loading: {
    flex: 1,
    backgroundColor: colors.lpBlack,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
