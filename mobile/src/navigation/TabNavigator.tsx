import React, { useState } from 'react';
import { View, StyleSheet, Text } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import Svg, { Path, Circle, Rect, G } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  DashboardScreen,
  SignalsScreen,
  SignalDetailScreen,
  SettingsScreen,
  WalletScreen,
  DepositScreen,
  WithdrawScreen,
  PredictionsScreen,
  IntelligenceScreen,
  HistoryScreen,
  EngineStatusScreen,
} from '../screens';
import { useTradingMode } from '../context/TradingModeContext';
import { TradingModeBanner } from '../components';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

// Custom Icons
const HomeIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M9 22V12h6v10"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const SignalsIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M22 12h-4l-3 9L9 3l-3 9H2"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const PredictIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={2} />
    <Path
      d="M12 6v6l4 2"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Circle cx="12" cy="12" r="3" stroke={color} strokeWidth={2} />
    <Path
      d="M12 2v2M12 20v2M2 12h2M20 12h2"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const WalletIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M21 12V7H5a2 2 0 010-4h14v4"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M3 5v14a2 2 0 002 2h16v-5"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Circle cx="18" cy="14" r="2" stroke={color} strokeWidth={2} />
  </Svg>
);

const IntelIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M9 18h6M10 22h4"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M12 2a7 7 0 00-4 12.73V16a1 1 0 001 1h6a1 1 0 001-1v-1.27A7 7 0 0012 2z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const SettingsIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <G stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z" />
      <Circle cx="12" cy="12" r="3" />
    </G>
  </Svg>
);

// Signals Stack Navigator (includes SignalDetail)
const SignalsStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      contentStyle: { backgroundColor: colors.lpBlack },
    }}
  >
    <Stack.Screen name="SignalsList" component={SignalsScreen} />
    <Stack.Screen name="SignalDetail" component={SignalDetailScreen} />
  </Stack.Navigator>
);

// Wallet Stack Navigator (includes Deposit/Withdraw)
const WalletStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      contentStyle: { backgroundColor: colors.lpBlack },
    }}
  >
    <Stack.Screen name="WalletMain" component={WalletScreen} />
    <Stack.Screen name="Deposit" component={DepositScreen} />
    <Stack.Screen name="Withdraw" component={WithdrawScreen} />
    <Stack.Screen name="History" component={HistoryScreen} />
  </Stack.Navigator>
);

// Settings Stack Navigator (includes Engine Status and History)
const SettingsStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      contentStyle: { backgroundColor: colors.lpBlack },
    }}
  >
    <Stack.Screen name="SettingsMain" component={SettingsScreen} />
    <Stack.Screen name="EngineStatus" component={EngineStatusScreen} />
    <Stack.Screen name="History" component={HistoryScreen} />
  </Stack.Navigator>
);

// Dashboard Stack Navigator (includes History link)
const DashboardStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      contentStyle: { backgroundColor: colors.lpBlack },
    }}
  >
    <Stack.Screen name="DashboardMain" component={DashboardScreen} />
    <Stack.Screen name="History" component={HistoryScreen} />
  </Stack.Navigator>
);

// Predict Stack Navigator
const PredictStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      contentStyle: { backgroundColor: colors.lpBlack },
    }}
  >
    <Stack.Screen name="PredictMain" component={PredictionsScreen} />
  </Stack.Navigator>
);

// Intel Stack Navigator
const IntelStack = () => (
  <Stack.Navigator
    screenOptions={{
      headerShown: false,
      contentStyle: { backgroundColor: colors.lpBlack },
    }}
  >
    <Stack.Screen name="IntelMain" component={IntelligenceScreen} />
  </Stack.Navigator>
);

// Trading Mode Banner Wrapper
const TradingModeBannerWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { mode, setMode, isLoading } = useTradingMode();

  const handleModeChange = (newMode: 'paper' | 'live') => {
    setMode(newMode);
  };

  if (isLoading) {
    return <>{children}</>;
  }

  return (
    <View style={{ flex: 1 }}>
      <TradingModeBanner mode={mode} onModeChange={handleModeChange} />
      {children}
    </View>
  );
};

export const TabNavigator: React.FC = () => {
  return (
    <TradingModeBannerWrapper>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarStyle: styles.tabBar,
          tabBarActiveTintColor: colors.lpCyan,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarShowLabel: true,
          tabBarLabelStyle: styles.tabBarLabel,
          tabBarItemStyle: styles.tabBarItem,
        }}
      >
        <Tab.Screen
          name="Home"
          component={DashboardStack}
          options={{
            tabBarIcon: ({ color, focused }) => (
              <View style={styles.iconContainer}>
                {focused && <View style={styles.activeIndicator} />}
                <HomeIcon color={color} size={22} />
              </View>
            ),
          }}
        />
        <Tab.Screen
          name="Signals"
          component={SignalsStack}
          options={{
            tabBarIcon: ({ color, focused }) => (
              <View style={styles.iconContainer}>
                {focused && <View style={styles.activeIndicator} />}
                <SignalsIcon color={color} size={22} />
              </View>
            ),
          }}
        />
        <Tab.Screen
          name="Predict"
          component={PredictStack}
          options={{
            tabBarIcon: ({ color, focused }) => (
              <View style={styles.iconContainer}>
                {focused && <View style={styles.activeIndicator} />}
                <PredictIcon color={color} size={22} />
              </View>
            ),
          }}
        />
        <Tab.Screen
          name="Wallet"
          component={WalletStack}
          options={{
            tabBarIcon: ({ color, focused }) => (
              <View style={styles.iconContainer}>
                {focused && <View style={styles.activeIndicator} />}
                <WalletIcon color={color} size={22} />
              </View>
            ),
          }}
        />
        <Tab.Screen
          name="Intel"
          component={IntelStack}
          options={{
            tabBarIcon: ({ color, focused }) => (
              <View style={styles.iconContainer}>
                {focused && <View style={styles.activeIndicator} />}
                <IntelIcon color={color} size={22} />
              </View>
            ),
          }}
        />
        <Tab.Screen
          name="Settings"
          component={SettingsStack}
          options={{
            tabBarIcon: ({ color, focused }) => (
              <View style={styles.iconContainer}>
                {focused && <View style={styles.activeIndicator} />}
                <SettingsIcon color={color} size={22} />
              </View>
            ),
          }}
        />
      </Tab.Navigator>
    </TradingModeBannerWrapper>
  );
};

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: colors.lpSurface,
    borderTopWidth: 0,
    height: 70,
    paddingBottom: 8,
    paddingTop: 4,
    position: 'absolute',
    elevation: 0,
    shadowOpacity: 0,
  },
  tabBarItem: {
    paddingTop: 4,
  },
  tabBarLabel: {
    ...typography.labelSM,
    fontSize: 10,
    marginTop: 2,
  },
  iconContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 4,
  },
  activeIndicator: {
    position: 'absolute',
    top: -2,
    width: 20,
    height: 2,
    backgroundColor: colors.lpCyan,
    borderRadius: 1,
  },
});
