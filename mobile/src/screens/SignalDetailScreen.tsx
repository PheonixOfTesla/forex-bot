import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  SignalConfidenceBar,
  TradeDirectionPill,
  PrimaryButton,
  GhostButton,
} from '../components';
import { useSignal, useExecuteSignal, useSkipSignal } from '../hooks/useApi';

type SignalDetailParams = {
  SignalDetail: { signalId: string };
};

export const SignalDetailScreen: React.FC = () => {
  const navigation = useNavigation();
  const route = useRoute<RouteProp<SignalDetailParams, 'SignalDetail'>>();
  const signalId = route.params?.signalId || '1';

  const { data: signal } = useSignal(signalId);
  const { execute, loading: executing } = useExecuteSignal();
  const { skip, loading: skipping } = useSkipSignal();

  // Transform API data to UI format
  const s = signal as any;
  const displaySignal = {
    id: s?.id ?? '1',
    asset: s?.pair ?? 'Loading...',
    direction: (s?.direction === 'buy' ? 'LONG' : s?.direction === 'sell' ? 'SHORT' : 'LONG') as 'LONG' | 'SHORT',
    confidence: s?.confidence ?? 0,
    strategy: s?.strategy?.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) ?? 'ML Signal',
    session: s?.status ?? 'Active',
    atr: 0,
    volume: 0,
    entry: s?.entry_price ?? 0,
    stopLoss: s?.stop_loss ?? 0,
    takeProfit: s?.take_profit ?? 0,
    riskReward: s?.risk_reward_ratio ?? (s?.entry_price && s?.stop_loss && s?.take_profit
      ? Math.abs(s.take_profit - s.entry_price) / Math.abs(s.stop_loss - s.entry_price)
      : 2.0),
    createdAt: s?.created_at ?? s?.timestamp ?? new Date().toISOString(),
  };

  const handleExecute = async () => {
    Alert.alert(
      'Execute Trade',
      `Are you sure you want to execute this ${displaySignal.direction} trade on ${displaySignal.asset}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Execute',
          onPress: async () => {
            const result = await execute(displaySignal.id);
            if (result) {
              Alert.alert('Success', 'Trade executed successfully');
              navigation.goBack();
            }
          },
        },
      ]
    );
  };

  const handleSkip = async () => {
    const result = await skip(displaySignal.id);
    if (result) {
      navigation.goBack();
    }
  };

  const stopLossPips = Math.abs(
    (displaySignal.entry - displaySignal.stopLoss) * 10000
  ).toFixed(1);
  const takeProfitPips = Math.abs(
    (displaySignal.takeProfit - displaySignal.entry) * 10000
  ).toFixed(1);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.assetRow}>
            <Text style={styles.asset}>{displaySignal.asset}</Text>
            <TradeDirectionPill direction={displaySignal.direction} size="lg" />
          </View>
        </View>

        {/* Confidence Hero */}
        <View style={styles.confidenceSection}>
          <Text style={styles.confidenceValue}>{displaySignal.confidence}%</Text>
          <Text style={styles.confidenceLabel}>ML CONFIDENCE</Text>
          <View style={styles.confidenceBarContainer}>
            <SignalConfidenceBar
              confidence={displaySignal.confidence}
              height={12}
            />
          </View>
        </View>

        {/* Signal Info Grid */}
        <View style={styles.infoGrid}>
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>STRATEGY</Text>
            <Text style={styles.infoValue}>{displaySignal.strategy}</Text>
          </View>
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>SESSION</Text>
            <Text style={styles.infoValue}>{displaySignal.session}</Text>
          </View>
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>ATR</Text>
            <Text style={styles.infoValue}>
              {(displaySignal.atr * 10000).toFixed(1)} pips
            </Text>
          </View>
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>VOLUME</Text>
            <Text style={styles.infoValue}>
              {(displaySignal.volume / 1000).toFixed(0)}K
            </Text>
          </View>
        </View>

        {/* Entry/Stop/Target Table */}
        <View style={styles.priceTable}>
          <Text style={styles.sectionTitle}>PRICE LEVELS</Text>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>Entry</Text>
            <Text style={styles.priceValue}>
              {displaySignal.entry.toFixed(5)}
            </Text>
          </View>
          <View style={[styles.priceRow, styles.stopRow]}>
            <View>
              <Text style={styles.priceLabel}>Stop Loss</Text>
              <Text style={styles.pricePips}>{stopLossPips} pips</Text>
            </View>
            <Text style={[styles.priceValue, { color: colors.lpRed }]}>
              {displaySignal.stopLoss.toFixed(5)}
            </Text>
          </View>
          <View style={[styles.priceRow, styles.targetRow]}>
            <View>
              <Text style={styles.priceLabel}>Take Profit</Text>
              <Text style={styles.pricePips}>{takeProfitPips} pips</Text>
            </View>
            <Text style={[styles.priceValue, { color: colors.lpGreen }]}>
              {displaySignal.takeProfit.toFixed(5)}
            </Text>
          </View>
        </View>

        {/* Risk/Reward */}
        <View style={styles.rrSection}>
          <View style={styles.rrCard}>
            <Text style={styles.rrLabel}>RISK / REWARD</Text>
            <Text style={styles.rrValue}>
              1 : {displaySignal.riskReward.toFixed(1)}
            </Text>
          </View>
        </View>
      </ScrollView>

      {/* Action Buttons */}
      <View style={styles.actions}>
        <GhostButton
          title="SKIP"
          onPress={handleSkip}
          loading={skipping}
          style={styles.skipButton}
          size="lg"
        />
        <PrimaryButton
          title="EXECUTE TRADE"
          onPress={handleExecute}
          loading={executing}
          color={colors.lpCyan}
          style={styles.executeButton}
          size="lg"
        />
      </View>
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
    paddingBottom: 120,
  },
  header: {
    marginBottom: spacing.xl,
  },
  assetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  asset: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  confidenceSection: {
    alignItems: 'center',
    marginBottom: spacing.xxl,
  },
  confidenceValue: {
    ...typography.heroXL,
    color: colors.lpCyan,
  },
  confidenceLabel: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  confidenceBarContainer: {
    width: '100%',
    marginTop: spacing.lg,
  },
  infoGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginBottom: spacing.xxl,
  },
  infoItem: {
    flex: 1,
    minWidth: '45%',
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  infoLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  infoValue: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  priceTable: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  stopRow: {
    borderLeftWidth: 3,
    borderLeftColor: colors.lpRed,
    paddingLeft: spacing.md,
    marginLeft: -spacing.lg,
    marginRight: -spacing.lg,
    paddingRight: spacing.lg,
  },
  targetRow: {
    borderLeftWidth: 3,
    borderLeftColor: colors.lpGreen,
    paddingLeft: spacing.md,
    marginLeft: -spacing.lg,
    marginRight: -spacing.lg,
    paddingRight: spacing.lg,
    borderBottomWidth: 0,
  },
  priceLabel: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  pricePips: {
    ...typography.bodySM,
    color: colors.textMuted,
    marginTop: 2,
  },
  priceValue: {
    ...typography.h4,
    color: colors.textPrimary,
    fontFamily: 'monospace',
  },
  rrSection: {
    marginBottom: spacing.xl,
  },
  rrCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    borderLeftWidth: 3,
    borderLeftColor: colors.lpPurple,
    padding: spacing.lg,
    alignItems: 'center',
  },
  rrLabel: {
    ...typography.labelSM,
    color: colors.textSecondary,
  },
  rrValue: {
    ...typography.heroMD,
    color: colors.lpPurple,
    marginTop: spacing.xs,
  },
  actions: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    gap: spacing.md,
    padding: spacing.xl,
    backgroundColor: colors.lpBlack,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
  },
  skipButton: {
    flex: 1,
  },
  executeButton: {
    flex: 2,
  },
});
