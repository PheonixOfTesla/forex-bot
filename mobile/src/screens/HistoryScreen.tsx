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

  // Mock data for development
  const trades = data || [
    {
      id: '1',
      asset: 'EUR/USD',
      direction: 'LONG' as const,
      pnl: 245.32,
      confidence: 87,
      entryPrice: 1.0892,
      exitPrice: 1.0952,
      status: 'CLOSED' as const,
      createdAt: '2024-01-15T09:30:00Z',
      closedAt: '2024-01-15T14:45:00Z',
    },
    {
      id: '2',
      asset: 'BTC/USD',
      direction: 'SHORT' as const,
      pnl: -89.5,
      confidence: 72,
      entryPrice: 42500,
      exitPrice: 42890,
      status: 'CLOSED' as const,
      createdAt: '2024-01-15T08:15:00Z',
      closedAt: '2024-01-15T10:30:00Z',
    },
    {
      id: '3',
      asset: 'XRP/USD',
      direction: 'LONG' as const,
      pnl: 156.78,
      confidence: 91,
      entryPrice: 0.612,
      exitPrice: 0.648,
      status: 'CLOSED' as const,
      createdAt: '2024-01-14T16:00:00Z',
      closedAt: '2024-01-15T02:15:00Z',
    },
    {
      id: '4',
      asset: 'GBP/USD',
      direction: 'SHORT' as const,
      pnl: 312.45,
      confidence: 85,
      entryPrice: 1.2750,
      exitPrice: 1.2680,
      status: 'CLOSED' as const,
      createdAt: '2024-01-14T11:30:00Z',
      closedAt: '2024-01-14T15:45:00Z',
    },
    {
      id: '5',
      asset: 'ETH/USD',
      direction: 'LONG' as const,
      pnl: -45.2,
      confidence: 68,
      entryPrice: 2340,
      exitPrice: 2315,
      status: 'CLOSED' as const,
      createdAt: '2024-01-13T22:00:00Z',
      closedAt: '2024-01-14T08:30:00Z',
    },
  ];

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
