import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import Svg, { Path, Circle } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  PrimaryButton,
  GhostButton,
  BalanceSparkline,
  MetricCard,
} from '../components';
import { useWallet, useWalletBalanceHistory } from '../hooks/useApi';
import { Transaction } from '../services/api';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Icons
const WalletIconLarge = ({ color, size }: { color: string; size: number }) => (
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

const ArrowUpIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M12 19V5M5 12l7-7 7 7"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const ArrowDownIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M12 5v14M19 12l-7 7-7-7"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const TrendingUpIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M23 6l-9.5 9.5-5-5L1 18"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M17 6h6v6"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

// Transaction type styling
const getTransactionStyle = (type: string, amount: number) => {
  switch (type) {
    case 'deposit':
      return { color: colors.lpGreen, prefix: '+', Icon: ArrowDownIcon };
    case 'withdrawal':
      return { color: colors.lpRed, prefix: '', Icon: ArrowUpIcon };
    case 'trade_pnl':
      return {
        color: amount >= 0 ? colors.lpGreen : colors.lpRed,
        prefix: amount >= 0 ? '+' : '',
        Icon: TrendingUpIcon,
      };
    case 'fee':
      return { color: colors.lpAmber, prefix: '-', Icon: ArrowUpIcon };
    default:
      return { color: colors.textSecondary, prefix: '', Icon: ArrowDownIcon };
  }
};

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed':
      return colors.lpGreen;
    case 'pending':
      return colors.lpAmber;
    case 'failed':
      return colors.lpRed;
    default:
      return colors.textMuted;
  }
};

interface TransactionItemProps {
  transaction: Transaction;
}

const TransactionItem: React.FC<TransactionItemProps> = ({ transaction }) => {
  const style = getTransactionStyle(transaction.type, transaction.amount);
  const Icon = style.Icon;

  return (
    <View style={styles.transactionItem}>
      <View style={[styles.transactionIcon, { backgroundColor: `${style.color}20` }]}>
        <Icon color={style.color} size={20} />
      </View>
      <View style={styles.transactionInfo}>
        <Text style={styles.transactionDescription} numberOfLines={1}>
          {transaction.description}
        </Text>
        <View style={styles.transactionMeta}>
          <Text style={styles.transactionDate}>{formatDate(transaction.created_at)}</Text>
          <View style={[styles.statusBadge, { backgroundColor: `${getStatusColor(transaction.status)}20` }]}>
            <Text style={[styles.statusText, { color: getStatusColor(transaction.status) }]}>
              {transaction.status.toUpperCase()}
            </Text>
          </View>
        </View>
      </View>
      <Text style={[styles.transactionAmount, { color: style.color }]}>
        {style.prefix}${Math.abs(transaction.amount).toLocaleString('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}
      </Text>
    </View>
  );
};

export const WalletScreen: React.FC = () => {
  const router = useRouter();
  const { data: wallet, loading, refetch } = useWallet();
  const { data: balanceHistory } = useWalletBalanceHistory(30);

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handleDeposit = () => {
    router.push('/deposit' as any);
  };

  const handleWithdraw = () => {
    router.push('/withdraw' as any);
  };

  // Transform balance history for sparkline
  const sparklineData = balanceHistory?.map(p => p.balance) ?? [];

  // Calculate metrics
  const totalPnl = wallet?.total_pnl ?? 0;
  const pnlColor = totalPnl >= 0 ? colors.lpGreen : colors.lpRed;
  const pnlPrefix = totalPnl >= 0 ? '+' : '';

  const isPaperMode = wallet?.mode === 'paper';

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
          <Text style={styles.title}>Wallet</Text>
          <View style={styles.headerRight}>
            <View style={[styles.modeBadge, isPaperMode ? styles.paperBadge : styles.liveBadge]}>
              <Text style={[styles.modeBadgeText, { color: isPaperMode ? colors.lpAmber : colors.lpGreen }]}>
                {isPaperMode ? 'PAPER' : 'LIVE'}
              </Text>
            </View>
            <WalletIconLarge color={colors.lpGold} size={28} />
          </View>
        </View>

        {/* Balance Card */}
        <View style={styles.balanceCard}>
          <Text style={styles.balanceLabel}>
            {isPaperMode ? 'Paper Balance' : 'Live Balance'}
          </Text>
          <Text style={styles.balanceValue}>
            ${(wallet?.balance ?? 0).toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </Text>

          {/* Balance Details */}
          <View style={styles.balanceDetails}>
            <View style={styles.balanceDetailItem}>
              <Text style={styles.balanceDetailLabel}>Paper</Text>
              <Text style={[styles.balanceDetailValue, isPaperMode && styles.activeBalance]}>
                ${(wallet?.paper_balance ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </Text>
            </View>
            <View style={styles.balanceDetailDivider} />
            <View style={styles.balanceDetailItem}>
              <Text style={styles.balanceDetailLabel}>Live</Text>
              <Text style={[styles.balanceDetailValue, !isPaperMode && styles.activeBalance]}>
                ${(wallet?.live_balance ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </Text>
            </View>
          </View>

          {/* Balance Sparkline */}
          {sparklineData.length > 1 && (
            <View style={styles.sparklineContainer}>
              <BalanceSparkline
                data={sparklineData}
                width={SCREEN_WIDTH - spacing.xl * 2 - spacing.lg * 2}
                height={60}
                color={colors.lpCyan}
              />
            </View>
          )}
        </View>

        {/* P&L Stats */}
        <View style={styles.metricsRow}>
          <MetricCard
            value={`${pnlPrefix}$${Math.abs(totalPnl).toFixed(2)}`}
            label="Total P/L"
            valueColor={pnlColor}
            valueSize="sm"
            style={styles.metricCardHalf}
          />
          <MetricCard
            value={`$${(wallet?.available_balance ?? 0).toFixed(2)}`}
            label="Available"
            valueColor={colors.lpCyan}
            valueSize="sm"
            style={styles.metricCardHalf}
          />
        </View>

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <PrimaryButton
            title="DEPOSIT"
            onPress={handleDeposit}
            color={colors.lpGreen}
            style={styles.actionButton}
            size="lg"
          />
          <GhostButton
            title="WITHDRAW"
            onPress={handleWithdraw}
            style={styles.actionButton}
            size="lg"
          />
        </View>

        {/* Pending Section */}
        {((wallet?.pending_deposits ?? 0) > 0 || (wallet?.pending_withdrawals ?? 0) > 0) && (
          <View style={styles.pendingSection}>
            {(wallet?.pending_deposits ?? 0) > 0 && (
              <View style={styles.pendingItem}>
                <Text style={styles.pendingLabel}>Pending Deposits</Text>
                <Text style={[styles.pendingValue, { color: colors.lpGreen }]}>
                  +${wallet?.pending_deposits.toFixed(2)}
                </Text>
              </View>
            )}
            {(wallet?.pending_withdrawals ?? 0) > 0 && (
              <View style={styles.pendingItem}>
                <Text style={styles.pendingLabel}>Pending Withdrawals</Text>
                <Text style={[styles.pendingValue, { color: colors.lpAmber }]}>
                  -${wallet?.pending_withdrawals.toFixed(2)}
                </Text>
              </View>
            )}
          </View>
        )}

        {/* Recent Transactions */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>RECENT TRANSACTIONS</Text>
            <TouchableOpacity onPress={() => router.push('/transactions' as any)}>
              <Text style={styles.seeAllLink}>See All</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.transactionsList}>
            {(wallet?.recent_transactions ?? []).length === 0 ? (
              <View style={styles.emptyState}>
                <Text style={styles.emptyStateText}>No transactions yet</Text>
              </View>
            ) : (
              wallet?.recent_transactions.map((txn) => (
                <TransactionItem key={txn.id} transaction={txn} />
              ))
            )}
          </View>
        </View>

        {/* Summary Stats */}
        <View style={styles.summarySection}>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Total Deposited</Text>
            <Text style={styles.summaryValue}>
              ${(wallet?.total_deposited ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Text>
          </View>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Total Withdrawn</Text>
            <Text style={styles.summaryValue}>
              ${(wallet?.total_withdrawn ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </Text>
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
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  modeBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
  },
  paperBadge: {
    backgroundColor: `${colors.lpAmber}20`,
  },
  liveBadge: {
    backgroundColor: `${colors.lpGreen}20`,
  },
  modeBadgeText: {
    ...typography.labelSM,
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
  balanceDetails: {
    flexDirection: 'row',
    marginTop: spacing.lg,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
  },
  balanceDetailItem: {
    flex: 1,
    alignItems: 'center',
  },
  balanceDetailDivider: {
    width: 1,
    backgroundColor: colors.borderDark,
  },
  balanceDetailLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  balanceDetailValue: {
    ...typography.h4,
    color: colors.textSecondary,
  },
  activeBalance: {
    color: colors.lpCyan,
    fontWeight: '600',
  },
  sparklineContainer: {
    marginTop: spacing.lg,
  },
  metricsRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  metricCardHalf: {
    flex: 1,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
  actionButton: {
    flex: 1,
  },
  pendingSection: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    gap: spacing.sm,
  },
  pendingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  pendingLabel: {
    ...typography.bodySM,
    color: colors.textSecondary,
  },
  pendingValue: {
    ...typography.bodyLG,
    fontWeight: '600',
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
  },
  seeAllLink: {
    ...typography.bodySM,
    color: colors.lpCyan,
  },
  transactionsList: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  transactionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  transactionIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  transactionInfo: {
    flex: 1,
  },
  transactionDescription: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  transactionMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  transactionDate: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  statusText: {
    ...typography.labelSM,
    fontSize: 10,
  },
  transactionAmount: {
    ...typography.h4,
    fontWeight: '700',
  },
  emptyState: {
    padding: spacing.xxl,
    alignItems: 'center',
  },
  emptyStateText: {
    ...typography.bodyMD,
    color: colors.textMuted,
  },
  summarySection: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  summaryLabel: {
    ...typography.bodySM,
    color: colors.textSecondary,
  },
  summaryValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
  },
});

export default WalletScreen;
