import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Dimensions,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  StatusBadge,
  MetricCard,
  SignalConfidenceBar,
  TradeDirectionPill,
  BalanceSparkline,
  LightningIcon,
  OpenPositionCard,
} from '../components';
import { useDashboard, useClosePaperPosition } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export const DashboardScreen: React.FC = () => {
  const { data, loading, refetch } = useDashboard();
  const { close: closePosition, loading: closingPosition } = useClosePaperPosition();
  const { isConnected } = useWebSocket({
    onBalanceUpdate: () => refetch(),
    onSignal: () => refetch(),
  });

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleClosePosition = useCallback(async (positionId: string, exitPrice: number) => {
    const result = await closePosition(positionId, exitPrice);
    if (result?.success) {
      Alert.alert('Position Closed', `P&L: $${result.trade?.pnl?.toFixed(2) || '0.00'}`);
      refetch();
    } else {
      Alert.alert('Error', 'Failed to close position');
    }
  }, [closePosition, refetch]);

  // Transform API data to UI format
  const dashboard = {
    balance: data?.balance ?? 0,
    todayPnl: data?.today_pnl ?? 0,
    winRate: data?.win_rate ?? 0,
    openPositions: data?.open_positions_count ?? 0,
    signals: (data?.ml_signals ?? []).map((s: any, i: number) => ({
      id: s.id ?? `signal-${i}`,
      asset: s.pair,
      direction: s.direction === 'buy' ? 'LONG' as const : 'SHORT' as const,
      confidence: s.confidence,
      strategy: 'ML Signal',
    })),
    recentTrades: (data?.open_positions ?? []).map((p: any, i: number) => ({
      id: p.id ?? `pos-${i}`,
      asset: p.pair,
      direction: (p.direction === 'buy' || p.direction === 'long') ? 'LONG' as const : 'SHORT' as const,
      pnl: p.unrealized_pnl ?? p.pnl ?? 0,
      status: 'OPEN' as const,
    })),
    balanceHistory: [
      data?.balance ? data.balance * 0.95 : 10000,
      data?.balance ? data.balance * 0.96 : 10100,
      data?.balance ? data.balance * 0.97 : 10200,
      data?.balance ? data.balance * 0.98 : 10300,
      data?.balance ? data.balance * 0.99 : 10400,
      data?.balance ?? 10500,
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
          <View style={styles.titleRow}>
            <LightningIcon size={28} gradient />
            <Text style={styles.title}>Lightning Trading</Text>
          </View>
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
          {(data?.open_positions ?? []).length > 0 ? (
            <View style={styles.positionsList}>
              {(data?.open_positions ?? []).map((position: any) => (
                <OpenPositionCard
                  key={position.id}
                  position={{
                    id: position.id,
                    pair: position.pair,
                    direction: position.direction,
                    entry_price: position.entry_price,
                    current_price: position.current_price,
                    size: position.size,
                    pnl: position.pnl ?? position.unrealized_pnl ?? 0,
                    stop_loss: position.stop_loss,
                    take_profit: position.take_profit,
                    opened_at: position.opened_at,
                  }}
                  onClose={handleClosePosition}
                />
              ))}
            </View>
          ) : (
            <View style={styles.emptyPositions}>
              <Text style={styles.emptyText}>No open positions</Text>
              <Text style={styles.emptySubtext}>Execute a signal to open a position</Text>
            </View>
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
    marginBottom: spacing.xl,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
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
  emptyPositions: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: 'center',
  },
  emptyText: {
    ...typography.bodyLG,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  emptySubtext: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
});
