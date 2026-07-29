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
import { useNavigation } from '@react-navigation/native';
import Svg, { Path, Circle } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  PrimaryButton,
  GhostButton,
  BalanceSparkline,
  MetricCard,
} from '../components';
import {
  useWallet,
  useWalletBalanceHistory,
  usePaperBalance,
  usePaperPositions,
  usePaperHistory,
  useLearningAccuracy,
} from '../hooks/useApi';
import { Transaction, PaperPosition, PaperTrade } from '../services/api';

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

const BookOpenIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2V3zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7V3z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const TargetIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={2} />
    <Circle cx="12" cy="12" r="6" stroke={color} strokeWidth={2} />
    <Circle cx="12" cy="12" r="2" stroke={color} strokeWidth={2} />
  </Svg>
);

const CheckCircleIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M22 11.08V12a10 10 0 11-5.93-9.14"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M22 4L12 14.01l-3-3"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const XCircleIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={2} />
    <Path
      d="M15 9l-6 6M9 9l6 6"
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

// Paper Position Item
interface PaperPositionItemProps {
  position: PaperPosition;
}

const PaperPositionItem: React.FC<PaperPositionItemProps> = ({ position }) => {
  const isLong = position.direction === 'long';
  const directionColor = isLong ? colors.lpGreen : colors.lpRed;
  const pnlColor = position.pnl >= 0 ? colors.lpGreen : colors.lpRed;
  const pnlPrefix = position.pnl >= 0 ? '+' : '';

  return (
    <View style={styles.positionItem}>
      <View style={styles.positionHeader}>
        <View style={styles.positionPairRow}>
          <Text style={styles.positionPair}>{position.pair}</Text>
          <View style={[styles.directionBadge, { backgroundColor: `${directionColor}20` }]}>
            <Text style={[styles.directionText, { color: directionColor }]}>
              {isLong ? 'LONG' : 'SHORT'}
            </Text>
          </View>
        </View>
        <Text style={[styles.positionPnl, { color: pnlColor }]}>
          {pnlPrefix}${Math.abs(position.pnl).toFixed(2)}
        </Text>
      </View>
      <View style={styles.positionDetails}>
        <View style={styles.positionDetail}>
          <Text style={styles.positionDetailLabel}>Entry</Text>
          <Text style={styles.positionDetailValue}>{position.entry_price.toFixed(5)}</Text>
        </View>
        <View style={styles.positionDetail}>
          <Text style={styles.positionDetailLabel}>Current</Text>
          <Text style={styles.positionDetailValue}>{position.current_price.toFixed(5)}</Text>
        </View>
        <View style={styles.positionDetail}>
          <Text style={styles.positionDetailLabel}>P/L %</Text>
          <Text style={[styles.positionDetailValue, { color: pnlColor }]}>
            {pnlPrefix}{position.pnl_pct.toFixed(2)}%
          </Text>
        </View>
      </View>
    </View>
  );
};

// Paper Trade History Item
interface PaperTradeItemProps {
  trade: PaperTrade;
}

const PaperTradeItem: React.FC<PaperTradeItemProps> = ({ trade }) => {
  const isWin = trade.result === 'win';
  const isLoss = trade.result === 'loss';
  const resultColor = isWin ? colors.lpGreen : isLoss ? colors.lpRed : colors.textMuted;
  const pnlColor = trade.pnl >= 0 ? colors.lpGreen : colors.lpRed;
  const pnlPrefix = trade.pnl >= 0 ? '+' : '';

  return (
    <View style={styles.tradeHistoryItem}>
      <View style={[styles.tradeResultIcon, { backgroundColor: `${resultColor}20` }]}>
        {isWin ? (
          <CheckCircleIcon color={resultColor} size={20} />
        ) : isLoss ? (
          <XCircleIcon color={resultColor} size={20} />
        ) : (
          <TrendingUpIcon color={resultColor} size={20} />
        )}
      </View>
      <View style={styles.tradeInfo}>
        <View style={styles.tradeHeader}>
          <Text style={styles.tradePair}>{trade.pair}</Text>
          <Text style={[styles.tradeDirection, { color: trade.direction === 'long' ? colors.lpGreen : colors.lpRed }]}>
            {trade.direction.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.tradeDate}>{formatDate(trade.closed_at || trade.opened_at)}</Text>
      </View>
      <Text style={[styles.tradePnl, { color: pnlColor }]}>
        {pnlPrefix}${Math.abs(trade.pnl).toFixed(2)}
      </Text>
    </View>
  );
};

// Learning Accuracy Card
interface AccuracyCardProps {
  pair: string;
  accuracy: number;
  total: number;
}

const AccuracyCard: React.FC<AccuracyCardProps> = ({ pair, accuracy, total }) => {
  const accuracyColor = accuracy >= 70 ? colors.lpGreen : accuracy >= 50 ? colors.lpAmber : colors.lpRed;

  return (
    <View style={styles.accuracyCard}>
      <View style={styles.accuracyHeader}>
        <Text style={styles.accuracyPair}>{pair}</Text>
        <Text style={[styles.accuracyValue, { color: accuracyColor }]}>
          {accuracy.toFixed(0)}%
        </Text>
      </View>
      <View style={styles.accuracyBarBg}>
        <View style={[styles.accuracyBarFill, { width: `${Math.min(accuracy, 100)}%`, backgroundColor: accuracyColor }]} />
      </View>
      <Text style={styles.accuracyTotal}>{total} signals</Text>
    </View>
  );
};

export const WalletScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const { data: wallet, loading, refetch } = useWallet();
  const { data: balanceHistory } = useWalletBalanceHistory(30);
  const { data: paperBalance, refetch: refetchPaperBalance } = usePaperBalance();
  const { data: paperPositions, refetch: refetchPaperPositions } = usePaperPositions();
  const { data: paperHistory, refetch: refetchPaperHistory } = usePaperHistory();
  const { data: learningAccuracy, refetch: refetchLearningAccuracy } = useLearningAccuracy();

  const onRefresh = useCallback(() => {
    refetch();
    refetchPaperBalance();
    refetchPaperPositions();
    refetchPaperHistory();
    refetchLearningAccuracy();
  }, [refetch, refetchPaperBalance, refetchPaperPositions, refetchPaperHistory, refetchLearningAccuracy]);

  const handleDeposit = () => {
    navigation.navigate('Deposit');
  };

  const handleWithdraw = () => {
    navigation.navigate('Withdraw');
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

        {/* Paper Trading Mode Badge */}
        {isPaperMode && (
          <View style={styles.paperModeSection}>
            <View style={styles.paperModeHeader}>
              <BookOpenIcon color={colors.lpAmber} size={24} />
              <View style={styles.paperModeInfo}>
                <Text style={styles.paperModeTitle}>Paper Trading Mode</Text>
                <Text style={styles.paperModeDesc}>
                  Practice trading with virtual funds - no real money at risk
                </Text>
              </View>
            </View>

            {/* Paper Trading Stats */}
            {paperBalance && (
              <View style={styles.paperStats}>
                <View style={styles.paperStatItem}>
                  <Text style={styles.paperStatLabel}>Equity</Text>
                  <Text style={styles.paperStatValue}>
                    ${paperBalance.equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </Text>
                </View>
                <View style={styles.paperStatItem}>
                  <Text style={styles.paperStatLabel}>Unrealized P/L</Text>
                  <Text style={[
                    styles.paperStatValue,
                    { color: paperBalance.unrealized_pnl >= 0 ? colors.lpGreen : colors.lpRed }
                  ]}>
                    {paperBalance.unrealized_pnl >= 0 ? '+' : ''}${paperBalance.unrealized_pnl.toFixed(2)}
                  </Text>
                </View>
                <View style={styles.paperStatItem}>
                  <Text style={styles.paperStatLabel}>Total Return</Text>
                  <Text style={[
                    styles.paperStatValue,
                    { color: paperBalance.pnl_percentage >= 0 ? colors.lpGreen : colors.lpRed }
                  ]}>
                    {paperBalance.pnl_percentage >= 0 ? '+' : ''}{paperBalance.pnl_percentage.toFixed(2)}%
                  </Text>
                </View>
              </View>
            )}
          </View>
        )}

        {/* Open Positions */}
        {isPaperMode && paperPositions && paperPositions.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>OPEN POSITIONS</Text>
              <Text style={styles.sectionCount}>{paperPositions.length}</Text>
            </View>
            <View style={styles.positionsList}>
              {paperPositions.map((position) => (
                <PaperPositionItem key={position.id} position={position} />
              ))}
            </View>
          </View>
        )}

        {/* Trade History */}
        {isPaperMode && paperHistory && paperHistory.trades.length > 0 && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>RECENT TRADES</Text>
              <View style={styles.winLossRow}>
                <Text style={[styles.winLossText, { color: colors.lpGreen }]}>
                  {paperHistory.wins}W
                </Text>
                <Text style={styles.winLossDivider}>/</Text>
                <Text style={[styles.winLossText, { color: colors.lpRed }]}>
                  {paperHistory.losses}L
                </Text>
                <Text style={styles.winRateText}>
                  ({paperHistory.win_rate.toFixed(0)}%)
                </Text>
              </View>
            </View>
            <View style={styles.tradeHistoryList}>
              {paperHistory.trades.slice(0, 5).map((trade) => (
                <PaperTradeItem key={trade.id} trade={trade} />
              ))}
            </View>
          </View>
        )}

        {/* Learning Accuracy */}
        {isPaperMode && learningAccuracy && (
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <View style={styles.sectionTitleRow}>
                <TargetIcon color={colors.lpCyan} size={18} />
                <Text style={[styles.sectionTitle, { marginLeft: spacing.sm }]}>LEARNING ACCURACY</Text>
              </View>
              <Text style={[styles.overallAccuracy, { color: learningAccuracy.overall_accuracy >= 70 ? colors.lpGreen : colors.lpAmber }]}>
                {learningAccuracy.overall_accuracy.toFixed(0)}%
              </Text>
            </View>
            <View style={styles.accuracyGrid}>
              {Object.entries(learningAccuracy.by_pair).slice(0, 4).map(([pair, data]) => (
                <AccuracyCard
                  key={pair}
                  pair={pair}
                  accuracy={data.accuracy}
                  total={data.total}
                />
              ))}
            </View>
            <View style={styles.learningInsight}>
              <Text style={styles.learningInsightText}>
                Based on {learningAccuracy.total_signals} signals, {learningAccuracy.correct_predictions} correct predictions
              </Text>
            </View>
          </View>
        )}

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
            <TouchableOpacity onPress={() => navigation.navigate('History')}>
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
  // Paper Trading Mode Section
  paperModeSection: {
    backgroundColor: `${colors.lpAmber}10`,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: `${colors.lpAmber}30`,
  },
  paperModeHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  paperModeInfo: {
    flex: 1,
    marginLeft: spacing.md,
  },
  paperModeTitle: {
    ...typography.h4,
    color: colors.lpAmber,
    marginBottom: spacing.xs,
  },
  paperModeDesc: {
    ...typography.bodySM,
    color: colors.textSecondary,
  },
  paperStats: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: `${colors.lpAmber}20`,
  },
  paperStatItem: {
    alignItems: 'center',
  },
  paperStatLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  paperStatValue: {
    ...typography.h4,
    color: colors.textPrimary,
  },
  // Positions Section
  sectionCount: {
    ...typography.bodySM,
    color: colors.lpCyan,
    backgroundColor: `${colors.lpCyan}20`,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  positionsList: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  positionItem: {
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  positionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  positionPairRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  positionPair: {
    ...typography.h4,
    color: colors.textPrimary,
  },
  directionBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  directionText: {
    ...typography.labelSM,
    fontSize: 10,
  },
  positionPnl: {
    ...typography.h4,
    fontWeight: '700',
  },
  positionDetails: {
    flexDirection: 'row',
    gap: spacing.lg,
  },
  positionDetail: {},
  positionDetailLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: 2,
  },
  positionDetailValue: {
    ...typography.bodySM,
    color: colors.textSecondary,
  },
  // Trade History Section
  winLossRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  winLossText: {
    ...typography.labelMD,
    fontWeight: '700',
  },
  winLossDivider: {
    ...typography.labelMD,
    color: colors.textMuted,
    marginHorizontal: 2,
  },
  winRateText: {
    ...typography.bodySM,
    color: colors.textMuted,
    marginLeft: spacing.sm,
  },
  tradeHistoryList: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    overflow: 'hidden',
  },
  tradeHistoryItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  tradeResultIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  tradeInfo: {
    flex: 1,
  },
  tradeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: 2,
  },
  tradePair: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  tradeDirection: {
    ...typography.labelSM,
    fontSize: 10,
  },
  tradeDate: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  tradePnl: {
    ...typography.h4,
    fontWeight: '700',
  },
  // Learning Accuracy Section
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  overallAccuracy: {
    ...typography.h3,
    fontWeight: '700',
  },
  accuracyGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  accuracyCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    width: (SCREEN_WIDTH - spacing.xl * 2 - spacing.sm) / 2 - 1,
  },
  accuracyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  accuracyPair: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  accuracyValue: {
    ...typography.h4,
    fontWeight: '700',
  },
  accuracyBarBg: {
    height: 4,
    backgroundColor: colors.borderDark,
    borderRadius: 2,
    marginBottom: spacing.xs,
    overflow: 'hidden',
  },
  accuracyBarFill: {
    height: '100%',
    borderRadius: 2,
  },
  accuracyTotal: {
    ...typography.labelSM,
    color: colors.textMuted,
  },
  learningInsight: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    alignItems: 'center',
  },
  learningInsightText: {
    ...typography.bodySM,
    color: colors.textSecondary,
    textAlign: 'center',
  },
});

export default WalletScreen;
