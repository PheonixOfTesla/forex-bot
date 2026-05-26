import React, { useCallback } from 'react';
import { StatusBar } from 'expo-status-bar';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
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
        <NavigationContainer theme={LightningTheme}>
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
