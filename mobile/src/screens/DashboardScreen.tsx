import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  StatusBadge,
  MetricCard,
  SignalConfidenceBar,
  TradeDirectionPill,
  BalanceSparkline,
} from '../components';
import { useDashboard } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export const DashboardScreen: React.FC = () => {
  const { data, loading, refetch } = useDashboard();
  const { isConnected } = useWebSocket({
    onBalanceUpdate: () => refetch(),
    onSignal: () => refetch(),
  });

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  // Mock data for development
  const dashboard = data || {
    balance: 12547.82,
    todayPnl: 342.18,
    winRate: 68,
    openPositions: 3,
    signals: [
      {
        id: '1',
        asset: 'EUR/USD',
        direction: 'LONG' as const,
        confidence: 87,
        strategy: 'Trend Following',
      },
      {
        id: '2',
        asset: 'BTC/USD',
        direction: 'SHORT' as const,
        confidence: 72,
        strategy: 'Mean Reversion',
      },
    ],
    recentTrades: [
      {
        id: '1',
        asset: 'XRP/USD',
        direction: 'LONG' as const,
        pnl: 124.5,
        status: 'OPEN' as const,
      },
      {
        id: '2',
        asset: 'EUR/USD',
        direction: 'SHORT' as const,
        pnl: -45.2,
        status: 'OPEN' as const,
      },
    ],
    balanceHistory: [
      12000, 12100, 12050, 12200, 12150, 12300, 12400, 12350, 12500, 12547,
    ],
  };

  const pnlColor = dashboard.todayPnl >= 0 ? colors.lpGreen : colors.lpRed;
  const pnlPrefix = dashboard.todayPnl >= 0 ? '+' : '';

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
          <Text style={styles.title}>Lightning Bot</Text>
          <StatusBadge status={isConnected ? 'LIVE' : 'STOPPED'} />
        </View>

        {/* Balance Hero */}
        <View style={styles.balanceCard}>
          <Text style={styles.balanceLabel}>Total Balance</Text>
          <Text style={styles.balanceValue}>
            ${dashboard.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </Text>
          <View style={styles.pnlRow}>
            <Text style={[styles.pnlValue, { color: pnlColor }]}>
              {pnlPrefix}${Math.abs(dashboard.todayPnl).toFixed(2)}
            </Text>
            <Text style={styles.pnlLabel}>Today</Text>
          </View>

          {/* Balance Sparkline */}
          <View style={styles.sparklineContainer}>
            <BalanceSparkline
              data={dashboard.balanceHistory}
              width={SCREEN_WIDTH - spacing.xl * 2 - spacing.lg * 2}
              height={60}
              color={colors.lpCyan}
            />
          </View>
        </View>

        {/* Metrics Row */}
        <View style={styles.metricsRow}>
          <MetricCard
            value={`${dashboard.winRate}%`}
            label="Win Rate"
            valueColor={colors.lpCyan}
            valueSize="sm"
            style={styles.metricCardHalf}
          />
          <MetricCard
            value={dashboard.openPositions}
            label="Open Positions"
            valueColor={colors.textPrimary}
            valueSize="sm"
            style={styles.metricCardHalf}
          />
        </View>

        {/* ML Signals Panel */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ML SIGNALS</Text>
          <View style={styles.signalsList}>
            {dashboard.signals.map((signal) => (
              <View key={signal.id} style={styles.signalCard}>
                <View style={styles.signalHeader}>
                  <View style={styles.signalAssetRow}>
                    <Text style={styles.signalAsset}>{signal.asset}</Text>
                    <TradeDirectionPill direction={signal.direction} size="sm" />
                  </View>
                  <Text style={styles.signalConfidence}>{signal.confidence}%</Text>
                </View>
                <SignalConfidenceBar
                  confidence={signal.confidence}
                  height={6}
                />
                <Text style={styles.signalStrategy}>{signal.strategy}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Open Positions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>OPEN POSITIONS</Text>
          <View style={styles.positionsList}>
            {dashboard.recentTrades
              .filter((t) => t.status === 'OPEN')
              .map((trade) => {
                const isProfit = trade.pnl >= 0;
                return (
                  <View
                    key={trade.id}
                    style={[
                      styles.positionCard,
                      {
                        borderLeftColor: isProfit
                          ? colors.lpGreen
                          : colors.lpRed,
                      },
                    ]}
                  >
                    <View style={styles.positionLeft}>
                      <Text style={styles.positionAsset}>{trade.asset}</Text>
                      <TradeDirectionPill direction={trade.direction} size="sm" />
                    </View>
                    <Text
                      style={[
                        styles.positionPnl,
                        { color: isProfit ? colors.lpGreen : colors.lpRed },
                      ]}
                    >
                      {isProfit ? '+' : ''}${trade.pnl.toFixed(2)}
                    </Text>
                  </View>
                );
              })}
          </View>
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
    marginBottom: spacing.xl,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  balanceCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    marginBottom: spacing.lg,
  },
  balanceLabel: {
    ...typography.labelSM,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  balanceValue: {
    ...typography.heroLG,
    color: colors.lpGold,
  },
  pnlRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  pnlValue: {
    ...typography.h3,
    fontWeight: '700',
  },
  pnlLabel: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  sparklineContainer: {
    marginTop: spacing.lg,
  },
  metricsRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
  metricCardHalf: {
    flex: 1,
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  signalsList: {
    gap: spacing.md,
  },
  signalCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  signalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  signalAssetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  signalAsset: {
    ...typography.h4,
    color: colors.textPrimary,
  },
  signalConfidence: {
    ...typography.h3,
    color: colors.lpCyan,
    fontWeight: '700',
  },
  signalStrategy: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  positionsList: {
    gap: spacing.sm,
  },
  positionCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    borderLeftWidth: 3,
    padding: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  positionLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  positionAsset: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  positionPnl: {
    ...typography.h4,
    fontWeight: '700',
  },
});
