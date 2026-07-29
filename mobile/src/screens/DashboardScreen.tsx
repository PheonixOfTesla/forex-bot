import React, { useCallback, useEffect } from 'react';
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
import {
  useDashboard,
  useClosePaperPosition,
  useAutopilotStatus,
  useStrategyLeaderboard,
} from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const REFRESH_INTERVAL_MS = 20000;

const formatCount = (n: number): string => {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
};

const formatStrategyName = (name: string): string =>
  name
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

export const DashboardScreen: React.FC = () => {
  const { data, loading, refetch } = useDashboard();
  const { data: autopilot, refetch: refetchAutopilot } = useAutopilotStatus();
  const { data: strategies, refetch: refetchStrategies } = useStrategyLeaderboard();
  const { close: closePosition } = useClosePaperPosition();
  const { isConnected } = useWebSocket({
    onBalanceUpdate: () => refetch(),
    onSignal: () => refetch(),
  });

  const refetchAll = useCallback(() => {
    refetch();
    refetchAutopilot();
    refetchStrategies();
  }, [refetch, refetchAutopilot, refetchStrategies]);

  // Keep the hub live: the systems keep working while you watch
  useEffect(() => {
    const interval = setInterval(refetchAll, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refetchAll]);

  const handleClosePosition = useCallback(async (positionId: string, exitPrice: number) => {
    const result = await closePosition(positionId, exitPrice);
    if (result?.success) {
      Alert.alert('Position Closed', `P&L: $${result.trade?.pnl?.toFixed(2) || '0.00'}`);
      refetchAll();
    } else {
      Alert.alert('Error', 'Failed to close position');
    }
  }, [closePosition, refetchAll]);

  // ---------------------------------------------------------------------------
  // Data shaping
  // ---------------------------------------------------------------------------

  const paper = autopilot?.paper_account;
  const learned = autopilot?.learned_config;
  const lab = autopilot?.strategy_lab;
  const champion = lab?.champion ?? null;

  const balance = paper?.balance ?? data?.balance ?? 0;
  const totalPnl = paper?.total_pnl ?? data?.today_pnl ?? 0;
  const winRate = paper?.win_rate ?? data?.win_rate ?? 0;
  const openPositionsCount = paper?.open_positions ?? data?.open_positions_count ?? 0;

  const signals = (data?.ml_signals ?? []).slice(0, 4).map((s: any, i: number) => ({
    id: s.id ?? `signal-${i}`,
    asset: s.pair,
    direction: s.direction === 'buy' ? ('LONG' as const) : ('SHORT' as const),
    confidence: s.confidence,
    strategy: s.strategy ? formatStrategyName(s.strategy) : 'ML Signal',
  }));

  const topStrategies = (strategies?.leaderboard ?? learned?.strategies ?? []).slice(0, 3);
  const bestPairs = learned?.best_pairs ?? [];
  const buyStats = learned?.by_direction?.buy;
  const sellStats = learned?.by_direction?.sell;

  const balanceHistory = [
    balance * 0.985,
    balance * 0.99,
    balance * 0.992,
    balance * 0.996,
    balance * 0.998,
    balance || 10000,
  ];

  const pnlColor = totalPnl >= 0 ? colors.lpGreen : colors.lpRed;
  const pnlPrefix = totalPnl >= 0 ? '+' : '';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={refetchAll}
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
          <View style={styles.balanceTopRow}>
            <View>
              <Text style={styles.balanceLabel}>
                {autopilot?.mode === 'live' ? 'LIVE BALANCE' : 'TEST BALANCE'}
              </Text>
              <Text style={styles.balanceValue}>
                ${balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </Text>
            </View>
            <View style={styles.balanceStats}>
              <Text style={[styles.pnlValue, { color: pnlColor }]}>
                {pnlPrefix}${Math.abs(totalPnl).toFixed(2)}
              </Text>
              <Text style={styles.pnlLabel}>Total P&L</Text>
            </View>
          </View>

          <View style={styles.sparklineContainer}>
            <BalanceSparkline
              data={balanceHistory}
              width={SCREEN_WIDTH - spacing.xl * 2 - spacing.lg * 2}
              height={48}
              color={colors.lpCyan}
            />
          </View>

          <View style={styles.heroMetricsRow}>
            <View style={styles.heroMetric}>
              <Text style={[styles.heroMetricValue, { color: colors.lpCyan }]}>
                {winRate.toFixed(1)}%
              </Text>
              <Text style={styles.heroMetricLabel}>Win Rate</Text>
            </View>
            <View style={styles.heroMetricDivider} />
            <View style={styles.heroMetric}>
              <Text style={styles.heroMetricValue}>{paper?.closed_trades ?? 0}</Text>
              <Text style={styles.heroMetricLabel}>Test Trades</Text>
            </View>
            <View style={styles.heroMetricDivider} />
            <View style={styles.heroMetric}>
              <Text style={styles.heroMetricValue}>{openPositionsCount}</Text>
              <Text style={styles.heroMetricLabel}>Open Now</Text>
            </View>
          </View>
        </View>

        {/* Systems Status */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>SYSTEMS</Text>
          <View style={styles.systemsRow}>
            {/* Autopilot */}
            <View style={[styles.systemCard, { borderTopColor: colors.lpPurple }]}>
              <View style={styles.systemHeader}>
                <View
                  style={[
                    styles.statusDot,
                    { backgroundColor: autopilot?.running ? colors.lpGreen : colors.lpRed },
                  ]}
                />
                <Text style={styles.systemName}>AUTOPILOT</Text>
              </View>
              <Text style={[styles.systemValue, { color: colors.lpPurple }]}>
                {autopilot ? formatCount(autopilot.trades_closed) : '—'}
              </Text>
              <Text style={styles.systemLabel}>
                {autopilot
                  ? `trades tested · ${autopilot.mode === 'live' ? 'LIVE' : 'SIM'}`
                  : 'connecting…'}
              </Text>
            </View>

            {/* Strategy Lab */}
            <View style={[styles.systemCard, { borderTopColor: colors.lpCyan }]}>
              <View style={styles.systemHeader}>
                <View
                  style={[
                    styles.statusDot,
                    { backgroundColor: lab?.enabled ? colors.lpGreen : colors.lpRed },
                  ]}
                />
                <Text style={styles.systemName}>STRAT LAB</Text>
              </View>
              <Text style={[styles.systemValue, { color: colors.lpCyan }]}>
                {lab ? formatCount(lab.total_variants_tested) : '—'}
              </Text>
              <Text style={styles.systemLabel}>
                {lab ? `strategies tested` : 'connecting…'}
              </Text>
            </View>

            {/* Learning */}
            <View style={[styles.systemCard, { borderTopColor: colors.lpGold }]}>
              <View style={styles.systemHeader}>
                <View
                  style={[
                    styles.statusDot,
                    {
                      backgroundColor: (learned?.total_outcomes ?? 0) > 0
                        ? colors.lpGreen
                        : colors.lpAmber,
                    },
                  ]}
                />
                <Text style={styles.systemName}>LEARNING</Text>
              </View>
              <Text style={[styles.systemValue, { color: colors.lpGold }]}>
                {learned ? `${learned.overall_win_rate.toFixed(0)}%` : '—'}
              </Text>
              <Text style={styles.systemLabel}>
                {learned ? `${formatCount(learned.total_outcomes)} outcomes` : 'connecting…'}
              </Text>
            </View>
          </View>
        </View>

        {/* Champion Strategy */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>CHAMPION STRATEGY</Text>
          {champion ? (
            <View style={styles.championCard}>
              <View style={styles.championHeader}>
                <View style={styles.championTitleRow}>
                  <Text style={styles.championTrophy}>🏆</Text>
                  <View>
                    <Text style={styles.championWinRate}>{champion.win_rate}% win rate</Text>
                    <Text style={styles.championSub}>
                      {champion.trades} backtested trades · {champion.avg_pips >= 0 ? '+' : ''}
                      {champion.avg_pips} avg pips
                    </Text>
                  </View>
                </View>
                {lab?.champion_applied && (
                  <View style={styles.appliedPill}>
                    <Text style={styles.appliedPillText}>ACTIVE</Text>
                  </View>
                )}
              </View>
              <View style={styles.championParams}>
                <View style={styles.championParam}>
                  <Text style={styles.championParamValue}>{champion.min_confidence}%</Text>
                  <Text style={styles.championParamLabel}>Min Conf</Text>
                </View>
                <View style={styles.championParam}>
                  <Text style={styles.championParamValue}>{champion.sl_atr}x</Text>
                  <Text style={styles.championParamLabel}>Stop ATR</Text>
                </View>
                <View style={styles.championParam}>
                  <Text style={styles.championParamValue}>{champion.tp_atr}x</Text>
                  <Text style={styles.championParamLabel}>Target ATR</Text>
                </View>
                <View style={styles.championParam}>
                  <Text style={styles.championParamValue}>
                    {lab ? formatCount(lab.total_batches) : '0'}
                  </Text>
                  <Text style={styles.championParamLabel}>Batches</Text>
                </View>
              </View>
            </View>
          ) : (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyText}>Evolving strategies…</Text>
              <Text style={styles.emptySubtext}>
                The lab is mass-testing candidates. First champion appears after enough
                winning backtests.
              </Text>
            </View>
          )}
        </View>

        {/* Top Strategies */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>TOP STRATEGIES</Text>
          {topStrategies.length > 0 ? (
            <View style={styles.strategiesList}>
              {topStrategies.map((s: any, i: number) => (
                <View key={s.strategy ?? i} style={styles.strategyRow}>
                  <View style={styles.strategyRank}>
                    <Text style={styles.strategyRankText}>{i + 1}</Text>
                  </View>
                  <View style={styles.strategyInfo}>
                    <View style={styles.strategyNameRow}>
                      <Text style={styles.strategyName}>
                        {formatStrategyName(s.strategy)}
                      </Text>
                      <Text
                        style={[
                          styles.strategyWinRate,
                          { color: s.win_rate >= 50 ? colors.lpGreen : colors.lpRed },
                        ]}
                      >
                        {s.win_rate}%
                      </Text>
                    </View>
                    <SignalConfidenceBar confidence={s.win_rate} height={4} />
                    <Text style={styles.strategyMeta}>
                      {s.total_trades} calls · {s.avg_profit_pips >= 0 ? '+' : ''}
                      {s.avg_profit_pips} avg pips
                    </Text>
                  </View>
                </View>
              ))}
              {(buyStats || sellStats) && (
                <View style={styles.directionBias}>
                  <Text style={styles.directionBiasText}>
                    Longs {buyStats ? `${buyStats.accuracy.toFixed(0)}% (${buyStats.total})` : '—'}
                    {'   ·   '}
                    Shorts {sellStats ? `${sellStats.accuracy.toFixed(0)}% (${sellStats.total})` : '—'}
                  </Text>
                </View>
              )}
            </View>
          ) : (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyText}>No strategy records yet</Text>
              <Text style={styles.emptySubtext}>
                The autopilot builds this leaderboard as its test trades close.
              </Text>
            </View>
          )}
        </View>

        {/* Best Pairs */}
        {bestPairs.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>BEST PAIRS</Text>
            <View style={styles.pairsRow}>
              {bestPairs.map((p) => (
                <View key={p.pair} style={styles.pairChip}>
                  <Text style={styles.pairChipName}>{p.pair}</Text>
                  <Text
                    style={[
                      styles.pairChipRate,
                      { color: p.win_rate >= 50 ? colors.lpGreen : colors.lpRed },
                    ]}
                  >
                    {p.win_rate}%
                  </Text>
                  <Text style={styles.pairChipTrades}>{p.trades} trades</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* ML Signals */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>LIVE SIGNALS</Text>
          {signals.length > 0 ? (
            <View style={styles.signalsList}>
              {signals.map((signal) => (
                <View key={signal.id} style={styles.signalCard}>
                  <View style={styles.signalHeader}>
                    <View style={styles.signalAssetRow}>
                      <Text style={styles.signalAsset}>{signal.asset}</Text>
                      <TradeDirectionPill direction={signal.direction} size="sm" />
                    </View>
                    <Text style={styles.signalConfidence}>{signal.confidence}%</Text>
                  </View>
                  <SignalConfidenceBar confidence={signal.confidence} height={6} />
                  <Text style={styles.signalStrategy}>{signal.strategy}</Text>
                </View>
              ))}
            </View>
          ) : (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyText}>Scanning markets…</Text>
              <Text style={styles.emptySubtext}>
                Signals appear when indicator confluence clears the confidence bar.
              </Text>
            </View>
          )}
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
            <View style={styles.emptyCard}>
              <Text style={styles.emptyText}>No open positions</Text>
              <Text style={styles.emptySubtext}>
                The autopilot opens test positions automatically when signals qualify.
              </Text>
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

  // Balance hero
  balanceCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    marginBottom: spacing.xl,
  },
  balanceTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
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
  balanceStats: {
    alignItems: 'flex-end',
    paddingTop: spacing.md,
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
    marginTop: spacing.md,
  },
  heroMetricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.lg,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
  },
  heroMetric: {
    flex: 1,
    alignItems: 'center',
  },
  heroMetricDivider: {
    width: 1,
    height: 28,
    backgroundColor: colors.borderDark,
  },
  heroMetricValue: {
    ...typography.h3,
    color: colors.textPrimary,
    fontWeight: '700',
  },
  heroMetricLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Sections
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },

  // Systems grid
  systemsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  systemCard: {
    flex: 1,
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    borderTopWidth: 2,
    padding: spacing.md,
  },
  systemHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginBottom: spacing.sm,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  systemName: {
    ...typography.labelSM,
    color: colors.textSecondary,
    letterSpacing: 0.5,
  },
  systemValue: {
    ...typography.h2,
    fontWeight: '700',
  },
  systemLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Champion
  championCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.lpGold,
    padding: spacing.lg,
  },
  championHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  championTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  championTrophy: {
    fontSize: 24,
  },
  championWinRate: {
    ...typography.h3,
    color: colors.lpGold,
    fontWeight: '700',
  },
  championSub: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  appliedPill: {
    backgroundColor: colors.lpGreen,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 3,
  },
  appliedPillText: {
    ...typography.labelSM,
    color: colors.lpBlack,
    fontWeight: '700',
  },
  championParams: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    paddingTop: spacing.md,
  },
  championParam: {
    flex: 1,
    alignItems: 'center',
  },
  championParamValue: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  championParamLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Strategies leaderboard
  strategiesList: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    gap: spacing.lg,
  },
  strategyRow: {
    flexDirection: 'row',
    gap: spacing.md,
    alignItems: 'center',
  },
  strategyRank: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.borderDark,
    alignItems: 'center',
    justifyContent: 'center',
  },
  strategyRankText: {
    ...typography.labelSM,
    color: colors.lpCyan,
    fontWeight: '700',
  },
  strategyInfo: {
    flex: 1,
    gap: 4,
  },
  strategyNameRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  strategyName: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  strategyWinRate: {
    ...typography.bodyLG,
    fontWeight: '700',
  },
  strategyMeta: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  directionBias: {
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    paddingTop: spacing.md,
    alignItems: 'center',
  },
  directionBiasText: {
    ...typography.bodySM,
    color: colors.textSecondary,
  },

  // Pairs
  pairsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  pairChip: {
    flex: 1,
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    alignItems: 'center',
  },
  pairChipName: {
    ...typography.labelSM,
    color: colors.textSecondary,
  },
  pairChipRate: {
    ...typography.h3,
    fontWeight: '700',
    marginTop: 2,
  },
  pairChipTrades: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Signals
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

  // Positions
  positionsList: {
    gap: spacing.sm,
  },

  // Empty states
  emptyCard: {
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
    textAlign: 'center',
  },
});
