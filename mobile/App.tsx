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

// Type definitions for navigation
type SignalsStackParamList = {
  SignalsList: undefined;
  SignalDetail: { signalId: string };
};

type RootTabParamList = {
  Home: undefined;
  Signals: undefined;
  Engine: undefined;
  History: undefined;
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
      Home: 'home',
      Signals: {
        path: 'signals',
        screens: {
          SignalsList: '',
          SignalDetail: 'detail/:signalId',
        },
      },
      Engine: 'engine',
      History: 'history',
      Settings: 'settings',
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
      <View style={styles.container} onLayout={onLayoutRootView}>
        <NavigationContainer theme={LightningTheme} linking={linking}>
          <TabNavigator />
        </NavigationContainer>
        <StatusBar style="light" />
      </View>
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
