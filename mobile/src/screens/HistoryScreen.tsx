import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, typography, spacing, borderRadius } from '../theme';
import { TradeRow } from '../components';
import { useTrades } from '../hooks/useApi';

type FilterType = 'all' | 'wins' | 'losses';

const filters: { key: FilterType; label: string }[] = [
  { key: 'all', label: 'ALL' },
  { key: 'wins', label: 'WINS' },
  { key: 'losses', label: 'LOSSES' },
];

export const HistoryScreen: React.FC = () => {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const { data, loading, refetch } = useTrades(activeFilter);

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  // Transform API data to UI format
  const trades = (data ?? []).map((t: any) => ({
    id: t.id,
    asset: t.pair,
    direction: (t.direction === 'long' || t.direction === 'buy') ? 'LONG' as const : 'SHORT' as const,
    pnl: t.pnl ?? 0,
    confidence: t.confidence ?? 0,
    entryPrice: t.entry_price,
    exitPrice: t.exit_price,
    status: t.status === 'closed' ? 'CLOSED' as const : 'OPEN' as const,
    createdAt: t.opened_at,
    closedAt: t.closed_at ?? t.opened_at,
  }));

  const filteredTrades = trades.filter((trade) => {
    if (activeFilter === 'wins') return trade.pnl >= 0;
    if (activeFilter === 'losses') return trade.pnl < 0;
    return true;
  });

  const formatDate = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Calculate stats
  const totalPnl = filteredTrades.reduce((sum, t) => sum + t.pnl, 0);
  const winCount = filteredTrades.filter((t) => t.pnl >= 0).length;
  const winRate = filteredTrades.length > 0
    ? Math.round((winCount / filteredTrades.length) * 100)
    : 0;

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
          <Text style={styles.title}>Trade History</Text>
        </View>

        {/* Filter Tabs */}
        <View style={styles.filterTabs}>
          {filters.map((filter) => {
            const isActive = activeFilter === filter.key;
            return (
              <TouchableOpacity
                key={filter.key}
                style={[styles.filterTab, isActive && styles.filterTabActive]}
                onPress={() => setActiveFilter(filter.key)}
                activeOpacity={0.7}
              >
                <Text
                  style={[
                    styles.filterTabText,
                    isActive && styles.filterTabTextActive,
                  ]}
                >
                  {filter.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Stats Summary */}
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>Total P&L</Text>
            <Text
              style={[
                styles.statValue,
                { color: totalPnl >= 0 ? colors.lpGreen : colors.lpRed },
              ]}
            >
              {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
            </Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>Win Rate</Text>
            <Text style={[styles.statValue, { color: colors.lpCyan }]}>
              {winRate}%
            </Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>Trades</Text>
            <Text style={[styles.statValue, { color: colors.textPrimary }]}>
              {filteredTrades.length}
            </Text>
          </View>
        </View>

        {/* Trades List */}
        <View style={styles.tradesList}>
          {filteredTrades.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>No trades found</Text>
            </View>
          ) : (
            filteredTrades.map((trade) => (
              <TradeRow
                key={trade.id}
                asset={trade.asset}
                direction={trade.direction}
                pnl={trade.pnl}
                date={formatDate(trade.closedAt || trade.createdAt)}
                confidence={trade.confidence}
                onPress={() => {
                  // Navigate to trade detail
                }}
              />
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
    marginBottom: spacing.xl,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  filterTabs: {
    flexDirection: 'row',
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    padding: spacing.xs,
    marginBottom: spacing.xl,
  },
  filterTab: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    borderRadius: borderRadius.sm,
  },
  filterTabActive: {
    backgroundColor: colors.lpBlack,
    borderBottomWidth: 2,
    borderBottomColor: colors.lpCyan,
  },
  filterTabText: {
    ...typography.labelMD,
    color: colors.textMuted,
  },
  filterTabTextActive: {
    color: colors.lpCyan,
  },
  statsRow: {
    flexDirection: 'row',
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statDivider: {
    width: 1,
    backgroundColor: colors.borderDark,
  },
  statLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  statValue: {
    ...typography.h3,
    fontWeight: '700',
  },
  tradesList: {
    gap: spacing.sm,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: spacing.xxxl,
  },
  emptyText: {
    ...typography.bodyLG,
    color: colors.textMuted,
  },
});
