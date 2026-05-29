import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TextInput,
  Alert,
  Modal,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, typography, spacing, borderRadius } from '../theme';
import { PrimaryButton, GhostButton, TradingModeToggle } from '../components';
import { useSettings, useUpdateSettings, useEngineControl } from '../hooks/useApi';
import { useTradingMode } from '../context/TradingModeContext';

const ASSETS = [
  { id: 'eurusd', name: 'EUR/USD', category: 'Forex' },
  { id: 'gbpusd', name: 'GBP/USD', category: 'Forex' },
  { id: 'usdjpy', name: 'USD/JPY', category: 'Forex' },
  { id: 'btcusd', name: 'BTC/USD', category: 'Crypto' },
  { id: 'ethusd', name: 'ETH/USD', category: 'Crypto' },
  { id: 'xrpusd', name: 'XRP/USD', category: 'Crypto' },
];

export const SettingsScreen: React.FC = () => {
  const { data: settings, refetch } = useSettings();
  const { update, loading: updating } = useUpdateSettings();
  const { pause, stop, loading: engineLoading } = useEngineControl();
  const { mode, apiKeys, setApiKeys, isLoading: modeLoading } = useTradingMode();

  const [showEmergencyModal, setShowEmergencyModal] = useState(false);

  // API Keys form state
  const [oandaAccountId, setOandaAccountId] = useState('');
  const [oandaAccessToken, setOandaAccessToken] = useState('');
  const [showAccessToken, setShowAccessToken] = useState(false);
  const [savingKeys, setSavingKeys] = useState(false);

  // Local state for form
  const [maxRiskPerTrade, setMaxRiskPerTrade] = useState('2');
  const [maxDailyTrades, setMaxDailyTrades] = useState('10');
  const [minConfidence, setMinConfidence] = useState('70');
  const [maxDrawdown, setMaxDrawdown] = useState('15');
  const [enabledAssets, setEnabledAssets] = useState<string[]>([
    'eurusd',
    'btcusd',
    'xrpusd',
  ]);
  const [alertsEnabled, setAlertsEnabled] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);

  // Load settings from API
  useEffect(() => {
    if (settings) {
      const s = settings as any;
      if (s.risk) {
        setMaxRiskPerTrade(String(s.risk.risk_per_trade_pct ?? s.risk.risk_per_trade ?? 2));
        setMaxDailyTrades(String(s.risk.max_open_positions ?? 10));
        setMinConfidence(String(s.risk.min_confidence_threshold ?? s.risk.min_confidence ?? 70));
        setMaxDrawdown(String(s.risk.max_drawdown_pct ?? s.risk.max_daily_loss ?? 15));
      }
      if (s.notifications) {
        setAlertsEnabled(s.notifications.telegram_enabled ?? true);
      }
    }
  }, [settings]);

  // Load API keys into form
  useEffect(() => {
    if (apiKeys) {
      setOandaAccountId(apiKeys.oandaAccountId || '');
      setOandaAccessToken(apiKeys.oandaAccessToken || '');
    }
  }, [apiKeys]);

  const handleSaveApiKeys = useCallback(async () => {
    if (!oandaAccountId.trim() || !oandaAccessToken.trim()) {
      Alert.alert('Validation Error', 'Please fill in both Account ID and Access Token.');
      return;
    }

    setSavingKeys(true);
    try {
      await setApiKeys({
        oandaAccountId: oandaAccountId.trim(),
        oandaAccessToken: oandaAccessToken.trim(),
      });
      Alert.alert('Success', 'API keys saved successfully.');
    } catch (error) {
      Alert.alert('Error', 'Failed to save API keys. Please try again.');
    } finally {
      setSavingKeys(false);
    }
  }, [oandaAccountId, oandaAccessToken, setApiKeys]);

  const maskToken = (token: string): string => {
    if (!token || token.length < 8) return token;
    return token.substring(0, 4) + '*'.repeat(token.length - 8) + token.substring(token.length - 4);
  };

  const toggleAsset = useCallback((assetId: string) => {
    setEnabledAssets((prev) =>
      prev.includes(assetId)
        ? prev.filter((id) => id !== assetId)
        : [...prev, assetId]
    );
  }, []);

  const handleSave = useCallback(async () => {
    await update({
      risk: {
        risk_per_trade: parseFloat(maxRiskPerTrade),
        max_open_trades: parseInt(maxDailyTrades, 10),
        min_confidence: parseInt(minConfidence, 10),
        max_daily_loss: parseFloat(maxDrawdown),
        max_leverage: 10,
      },
      notifications: {
        telegram_enabled: alertsEnabled,
        trade_alerts: alertsEnabled,
        daily_summary: true,
      },
      trading: {
        auto_trade: true,
        pairs: enabledAssets.reduce((acc, id) => ({ ...acc, [id]: true }), {}),
      },
    });
    Alert.alert('Success', 'Settings saved successfully');
  }, [
    maxRiskPerTrade,
    maxDailyTrades,
    minConfidence,
    maxDrawdown,
    enabledAssets,
    alertsEnabled,
    update,
  ]);

  const handlePauseEngine = useCallback(async () => {
    Alert.alert(
      'Pause Engine',
      'This will pause all trading activity. Are you sure?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Pause',
          onPress: async () => {
            const success = await pause();
            if (success) {
              Alert.alert('Engine Paused', 'Trading has been paused.');
              refetch();
            }
          },
        },
      ]
    );
  }, [pause, refetch]);

  const handleEmergencyStop = useCallback(async () => {
    const success = await stop();
    setShowEmergencyModal(false);
    if (success) {
      Alert.alert(
        'Emergency Stop Activated',
        'All positions will be closed and trading is halted.'
      );
      refetch();
    }
  }, [stop, refetch]);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Settings</Text>
        </View>

        {/* Trading Mode Section - TOP PRIORITY */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>TRADING MODE</Text>
          {modeLoading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator color={colors.lpCyan} />
            </View>
          ) : (
            <>
              <TradingModeToggle />

              {/* API Keys Section - Only show when Live mode is selected or keys need configuration */}
              <View style={styles.card}>
                <View style={styles.apiKeysHeader}>
                  <Text style={styles.apiKeysTitle}>OANDA API Configuration</Text>
                  {mode === 'live' && (
                    <View style={styles.liveIndicator}>
                      <Text style={styles.liveIndicatorText}>REQUIRED</Text>
                    </View>
                  )}
                </View>

                <View style={styles.inputRow}>
                  <Text style={styles.inputLabel}>Account ID</Text>
                  <View style={styles.apiInputWrapper}>
                    <TextInput
                      style={styles.apiInput}
                      value={oandaAccountId}
                      onChangeText={setOandaAccountId}
                      placeholder="XXX-XXX-XXXXXXXX-XXX"
                      placeholderTextColor={colors.textMuted}
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                  </View>
                </View>

                <View style={[styles.inputRow, { borderBottomWidth: 0 }]}>
                  <Text style={styles.inputLabel}>Access Token</Text>
                  <View style={styles.apiInputWrapper}>
                    <TextInput
                      style={styles.apiInput}
                      value={showAccessToken ? oandaAccessToken : maskToken(oandaAccessToken)}
                      onChangeText={setOandaAccessToken}
                      placeholder="Enter your access token"
                      placeholderTextColor={colors.textMuted}
                      secureTextEntry={!showAccessToken}
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                    <TouchableOpacity
                      style={styles.showTokenButton}
                      onPress={() => setShowAccessToken(!showAccessToken)}
                    >
                      <Text style={styles.showTokenText}>
                        {showAccessToken ? 'HIDE' : 'SHOW'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </View>

                <TouchableOpacity
                  style={[
                    styles.saveKeysButton,
                    savingKeys && styles.saveKeysButtonDisabled,
                  ]}
                  onPress={handleSaveApiKeys}
                  disabled={savingKeys}
                >
                  {savingKeys ? (
                    <ActivityIndicator color={colors.lpBlack} size="small" />
                  ) : (
                    <Text style={styles.saveKeysButtonText}>SAVE API KEYS</Text>
                  )}
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>

        {/* Risk Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>RISK MANAGEMENT</Text>
          <View style={styles.card}>
            <View style={styles.inputRow}>
              <Text style={styles.inputLabel}>Max Risk Per Trade</Text>
              <View style={styles.inputWrapper}>
                <TextInput
                  style={styles.input}
                  value={maxRiskPerTrade}
                  onChangeText={setMaxRiskPerTrade}
                  keyboardType="decimal-pad"
                  placeholderTextColor={colors.textMuted}
                />
                <Text style={styles.inputSuffix}>%</Text>
              </View>
            </View>

            <View style={styles.inputRow}>
              <Text style={styles.inputLabel}>Max Daily Trades</Text>
              <View style={styles.inputWrapper}>
                <TextInput
                  style={styles.input}
                  value={maxDailyTrades}
                  onChangeText={setMaxDailyTrades}
                  keyboardType="number-pad"
                  placeholderTextColor={colors.textMuted}
                />
              </View>
            </View>

            <View style={styles.inputRow}>
              <Text style={styles.inputLabel}>Min Confidence</Text>
              <View style={styles.inputWrapper}>
                <TextInput
                  style={styles.input}
                  value={minConfidence}
                  onChangeText={setMinConfidence}
                  keyboardType="number-pad"
                  placeholderTextColor={colors.textMuted}
                />
                <Text style={styles.inputSuffix}>%</Text>
              </View>
            </View>

            <View style={[styles.inputRow, { borderBottomWidth: 0 }]}>
              <Text style={styles.inputLabel}>Max Drawdown</Text>
              <View style={styles.inputWrapper}>
                <TextInput
                  style={styles.input}
                  value={maxDrawdown}
                  onChangeText={setMaxDrawdown}
                  keyboardType="decimal-pad"
                  placeholderTextColor={colors.textMuted}
                />
                <Text style={styles.inputSuffix}>%</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Asset Toggles */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>TRADING ASSETS</Text>
          <View style={styles.card}>
            {ASSETS.map((asset, index) => (
              <View
                key={asset.id}
                style={[
                  styles.toggleRow,
                  index === ASSETS.length - 1 && { borderBottomWidth: 0 },
                ]}
              >
                <View>
                  <Text style={styles.toggleLabel}>{asset.name}</Text>
                  <Text style={styles.toggleCategory}>{asset.category}</Text>
                </View>
                <Switch
                  value={enabledAssets.includes(asset.id)}
                  onValueChange={() => toggleAsset(asset.id)}
                  trackColor={{ false: colors.borderDark, true: colors.lpCyan + '50' }}
                  thumbColor={
                    enabledAssets.includes(asset.id)
                      ? colors.lpCyan
                      : colors.textMuted
                  }
                />
              </View>
            ))}
          </View>
        </View>

        {/* Alert Settings */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>NOTIFICATIONS</Text>
          <View style={styles.card}>
            <View style={styles.toggleRow}>
              <Text style={styles.toggleLabel}>Push Alerts</Text>
              <Switch
                value={alertsEnabled}
                onValueChange={setAlertsEnabled}
                trackColor={{ false: colors.borderDark, true: colors.lpCyan + '50' }}
                thumbColor={alertsEnabled ? colors.lpCyan : colors.textMuted}
              />
            </View>
            <View style={[styles.toggleRow, { borderBottomWidth: 0 }]}>
              <Text style={styles.toggleLabel}>Sound Effects</Text>
              <Switch
                value={soundEnabled}
                onValueChange={setSoundEnabled}
                trackColor={{ false: colors.borderDark, true: colors.lpCyan + '50' }}
                thumbColor={soundEnabled ? colors.lpCyan : colors.textMuted}
              />
            </View>
          </View>
        </View>

        {/* Save Button */}
        <PrimaryButton
          title="SAVE SETTINGS"
          onPress={handleSave}
          loading={updating}
          style={styles.saveButton}
          size="lg"
        />

        {/* Engine Controls */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ENGINE CONTROL</Text>
          <View style={styles.engineButtons}>
            <GhostButton
              title="PAUSE ENGINE"
              onPress={handlePauseEngine}
              color={colors.lpAmber}
              loading={engineLoading}
              style={styles.pauseButton}
              size="lg"
            />
            <PrimaryButton
              title="EMERGENCY STOP"
              onPress={() => setShowEmergencyModal(true)}
              color={colors.lpRed}
              style={styles.stopButton}
              size="lg"
            />
          </View>
        </View>
      </ScrollView>

      {/* Emergency Stop Modal */}
      <Modal
        visible={showEmergencyModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowEmergencyModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Emergency Stop</Text>
            <Text style={styles.modalText}>
              This will immediately close all open positions and halt all trading
              activity. This action cannot be undone.
            </Text>
            <Text style={styles.modalWarning}>Are you absolutely sure?</Text>
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.modalCancelButton}
                onPress={() => setShowEmergencyModal(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalConfirmButton}
                onPress={handleEmergencyStop}
              >
                <Text style={styles.modalConfirmText}>CONFIRM STOP</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.lpBlack,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: spacing.xl,
    paddingBottom: 100,
  },
  header: {
    marginBottom: spacing.xl,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  card: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  inputRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  inputLabel: {
    ...typography.bodyLG,
    color: colors.textPrimary,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
  },
  input: {
    ...typography.h4,
    color: colors.lpCyan,
    width: 60,
    textAlign: 'right',
    paddingVertical: spacing.sm,
  },
  inputSuffix: {
    ...typography.bodyMD,
    color: colors.textMuted,
    marginLeft: spacing.xs,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  toggleLabel: {
    ...typography.bodyLG,
    color: colors.textPrimary,
  },
  toggleCategory: {
    ...typography.bodySM,
    color: colors.textMuted,
    marginTop: 2,
  },
  saveButton: {
    marginBottom: spacing.xxl,
  },
  engineButtons: {
    gap: spacing.md,
  },
  pauseButton: {
    borderColor: colors.lpAmber,
  },
  stopButton: {},
  loadingContainer: {
    padding: spacing.xl,
    alignItems: 'center',
  },
  apiKeysHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  apiKeysTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
  },
  liveIndicator: {
    backgroundColor: colors.lpRed + '30',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  liveIndicatorText: {
    ...typography.labelSM,
    color: colors.lpRed,
  },
  apiInputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    marginLeft: spacing.md,
  },
  apiInput: {
    ...typography.bodyMD,
    color: colors.lpCyan,
    flex: 1,
    paddingVertical: spacing.md,
  },
  showTokenButton: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  showTokenText: {
    ...typography.labelSM,
    color: colors.textMuted,
  },
  saveKeysButton: {
    backgroundColor: colors.lpCyan,
    margin: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  saveKeysButtonDisabled: {
    opacity: 0.6,
  },
  saveKeysButtonText: {
    ...typography.labelLG,
    color: colors.lpBlack,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  modalContent: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    width: '100%',
    borderWidth: 1,
    borderColor: colors.lpRed,
  },
  modalTitle: {
    ...typography.h2,
    color: colors.lpRed,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  modalText: {
    ...typography.bodyLG,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  modalWarning: {
    ...typography.h4,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  modalCancelButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.textMuted,
    alignItems: 'center',
  },
  modalCancelText: {
    ...typography.labelLG,
    color: colors.textSecondary,
  },
  modalConfirmButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.lpRed,
    alignItems: 'center',
  },
  modalConfirmText: {
    ...typography.labelLG,
    color: colors.textPrimary,
  },
});
