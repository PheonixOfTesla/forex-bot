import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Pressable,
  Platform,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import Svg, { Path, Circle } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  SignalConfidenceBar,
  TradeDirectionPill,
  StatusBadge,
} from '../components';
import { useSignals, useWallet, useExecutePaperTrade } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';
import { Signal } from '../services/api';

// Icons
const PlayIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M5 3l14 9-14 9V3z"
      fill={color}
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const CheckIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M20 6L9 17l-5-5"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

type SignalsStackParamList = {
  SignalsList: undefined;
  SignalDetail: { signalId: string };
};

export const SignalsScreen: React.FC = () => {
  const navigation = useNavigation<NativeStackNavigationProp<SignalsStackParamList>>();
  const { data, loading, refetch } = useSignals();
  const { data: wallet } = useWallet();
  const { execute: executePaperTrade, loading: executing } = useExecutePaperTrade();
  const [executedSignals, setExecutedSignals] = useState<Set<string>>(new Set());
  const [executingSignalId, setExecutingSignalId] = useState<string | null>(null);
  const { isConnected } = useWebSocket({
    onSignal: () => refetch(),
  });

  const isPaperMode = wallet?.mode === 'paper';

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleExecutePaperTrade = useCallback(async (signalId: string, event: any) => {
    event.stopPropagation();
    if (executedSignals.has(signalId) || executing) return;

    setExecutingSignalId(signalId);
    const result = await executePaperTrade(signalId);
    setExecutingSignalId(null);

    if (result?.success) {
      setExecutedSignals(prev => new Set([...prev, signalId]));
    }
  }, [executedSignals, executing, executePaperTrade]);

  // Transform API signals to UI format
  const signals = (data ?? []).map((s: any, i: number) => {
    const rr = s.risk_reward_ratio ?? (s.take_profit && s.stop_loss && s.entry_price
      ? Math.abs(s.take_profit - s.entry_price) / Math.abs(s.stop_loss - s.entry_price)
      : 2.0);
    return {
      id: s.id ?? `signal-${i}`,
      asset: s.pair,
      direction: (s.direction === 'buy' ? 'LONG' : 'SHORT') as 'LONG' | 'SHORT',
      confidence: s.confidence,
      strategy: s.strategy?.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) ?? 'ML Signal',
      session: s.status ?? 'Active',
      atr: 0,
      volume: 0,
      entry: s.entry_price,
      stopLoss: s.stop_loss,
      takeProfit: s.take_profit,
      riskReward: rr,
      createdAt: s.created_at ?? s.timestamp ?? new Date().toISOString(),
    };
  });

  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    return `${Math.floor(diffMin / 60)}h ago`;
  };

  const handleSignalPress = (signalId: string) => {
    navigation.navigate('SignalDetail', { signalId });
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={onRefresh}
            tintColor={colors.lpCyan}
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>ML Signals</Text>
          <StatusBadge status={isConnected ? 'LIVE' : 'STOPPED'} />
        </View>

        {/* Signal Count */}
        <View style={styles.countRow}>
          <Text style={styles.countText}>
            {signals.length} active signal{signals.length !== 1 ? 's' : ''}
          </Text>
        </View>

        {/* Signals List */}
        <View style={styles.signalsList}>
          {signals.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>No Active Signals</Text>
              <Text style={styles.emptyText}>
                The ML engine is analyzing markets. New signals will appear here.
              </Text>
            </View>
          ) : (
            signals.map((signal) => (
              <Pressable
                key={signal.id}
                style={({ pressed }) => [
                  styles.signalCard,
                  pressed && styles.signalCardPressed,
                  Platform.OS === 'web' && styles.signalCardWeb,
                ]}
                onPress={() => handleSignalPress(signal.id)}
              >
                <View style={styles.signalHeader}>
                  <View style={styles.signalAssetRow}>
                    <Text style={styles.signalAsset}>{signal.asset}</Text>
                    <TradeDirectionPill direction={signal.direction} size="sm" />
                  </View>
                  <Text style={styles.signalTime}>{formatTime(signal.createdAt)}</Text>
                </View>

                <View style={styles.confidenceRow}>
                  <Text style={styles.confidenceValue}>{signal.confidence}%</Text>
                  <View style={styles.confidenceBarWrapper}>
                    <SignalConfidenceBar
                      confidence={signal.confidence}
                      height={8}
                    />
                  </View>
                </View>

                <View style={styles.signalDetails}>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Strategy</Text>
                    <Text style={styles.detailValue}>{signal.strategy}</Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>R:R</Text>
                    <Text style={styles.detailValue}>
                      1:{signal.riskReward.toFixed(1)}
                    </Text>
                  </View>
                  <View style={styles.detailItem}>
                    <Text style={styles.detailLabel}>Session</Text>
                    <Text style={styles.detailValue}>{signal.session}</Text>
                  </View>
                </View>

                {/* Paper Trade Execution Button */}
                {isPaperMode && (
                  <View style={styles.paperTradeSection}>
                    {executedSignals.has(signal.id) ? (
                      <View style={styles.executedBadge}>
                        <CheckIcon color={colors.lpGreen} size={16} />
                        <Text style={styles.executedText}>Executed</Text>
                      </View>
                    ) : (
                      <TouchableOpacity
                        style={styles.executeButton}
                        onPress={(e) => handleExecutePaperTrade(signal.id, e)}
                        disabled={executing && executingSignalId === signal.id}
                      >
                        {executing && executingSignalId === signal.id ? (
                          <ActivityIndicator size="small" color={colors.lpBlack} />
                        ) : (
                          <>
                            <PlayIcon color={colors.lpBlack} size={14} />
                            <Text style={styles.executeButtonText}>Execute Paper Trade</Text>
                          </>
                        )}
                      </TouchableOpacity>
                    )}
                  </View>
                )}

                <View style={styles.tapHint}>
                  <Text style={styles.tapHintText}>Tap to view details</Text>
                </View>
              </Pressable>
            ))
          )}
        </View>
      </ScrollView>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  countRow: {
    marginBottom: spacing.xl,
  },
  countText: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  signalsList: {
    gap: spacing.md,
  },
  signalCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    borderLeftWidth: 3,
    borderLeftColor: colors.lpCyan,
  },
  signalCardPressed: {
    opacity: 0.7,
    backgroundColor: colors.borderDark,
  },
  signalCardWeb: {
    cursor: 'pointer',
    transition: 'opacity 0.2s ease',
  } as any,
  signalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  signalAssetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  signalAsset: {
    ...typography.h3,
    color: colors.textPrimary,
  },
  signalTime: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  confidenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  confidenceValue: {
    ...typography.h2,
    color: colors.lpCyan,
    fontWeight: '700',
    width: 60,
  },
  confidenceBarWrapper: {
    flex: 1,
  },
  signalDetails: {
    flexDirection: 'row',
    gap: spacing.lg,
    marginBottom: spacing.md,
  },
  detailItem: {
    flex: 1,
  },
  detailLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: 2,
  },
  detailValue: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  tapHint: {
    alignItems: 'center',
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
  },
  tapHintText: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: spacing.xxxl,
  },
  emptyTitle: {
    ...typography.h3,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  emptyText: {
    ...typography.bodyMD,
    color: colors.textMuted,
    textAlign: 'center',
  },
  // Paper Trade Execution Styles
  paperTradeSection: {
    paddingTop: spacing.md,
    marginTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
  },
  executeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.lpCyan,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
  },
  executeButtonText: {
    ...typography.labelMD,
    color: colors.lpBlack,
    fontWeight: '600',
  },
  executedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: `${colors.lpGreen}20`,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    gap: spacing.sm,
  },
  executedText: {
    ...typography.labelMD,
    color: colors.lpGreen,
    fontWeight: '600',
  },
});
