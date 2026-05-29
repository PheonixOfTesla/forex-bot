import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Alert,
  Modal,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import Svg, { Path } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import { PrimaryButton, GhostButton } from '../components';
import { useWithdraw, useWallet } from '../hooks/useApi';

// Icons
const BackIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M19 12H5M12 19l-7-7 7-7"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const BankIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 14v3M12 14v3M16 14v3"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const CryptoIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M9 8h6M9 12h6M9 16h6M12 3v3M12 18v3"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M17.5 6.5L12 3 6.5 6.5v11L12 21l5.5-3.5v-11z"
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

const ClockIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"
      stroke={color}
      strokeWidth={2}
    />
    <Path
      d="M12 6v6l4 2"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

type WithdrawMethod = 'bank' | 'crypto';

export const WithdrawScreen: React.FC = () => {
  const navigation = useNavigation<any>();
  const { data: wallet, refetch: refetchWallet } = useWallet();
  const { withdraw, loading } = useWithdraw();

  const [amount, setAmount] = useState('');
  const [selectedMethod, setSelectedMethod] = useState<WithdrawMethod | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [withdrawResult, setWithdrawResult] = useState<{
    amount: number;
    newBalance: number;
    estimatedCompletion?: string;
  } | null>(null);

  const isPaperMode = wallet?.mode === 'paper';
  const availableBalance = wallet?.available_balance ?? 0;

  const withdrawMethods = [
    { id: 'bank' as const, name: 'Bank Transfer', icon: BankIcon, fee: '$5.00', feeAmount: 5, time: '2-5 days', minAmount: 50 },
    { id: 'crypto' as const, name: 'Cryptocurrency', icon: CryptoIcon, fee: '0.5%', feePercent: 0.005, time: '10-30 min', minAmount: 20 },
  ];

  const getFee = () => {
    if (!amount || !selectedMethod) return 0;
    const amountNum = parseFloat(amount);
    const method = withdrawMethods.find(m => m.id === selectedMethod);
    if (!method) return 0;
    if (method.feeAmount) return method.feeAmount;
    if (method.feePercent) return amountNum * method.feePercent;
    return 0;
  };

  const getNetAmount = () => {
    if (!amount) return 0;
    return Math.max(0, parseFloat(amount) - getFee());
  };

  const handleConfirmWithdraw = () => {
    const amountNum = parseFloat(amount);

    if (!amount || amountNum <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid withdrawal amount.');
      return;
    }
    if (!selectedMethod && !isPaperMode) {
      Alert.alert('Select Method', 'Please select a withdrawal method.');
      return;
    }
    if (amountNum > availableBalance) {
      Alert.alert('Insufficient Balance', `You cannot withdraw more than your available balance of $${availableBalance.toFixed(2)}.`);
      return;
    }

    if (!isPaperMode) {
      const method = withdrawMethods.find(m => m.id === selectedMethod);
      if (method && amountNum < method.minAmount) {
        Alert.alert('Minimum Amount', `Minimum withdrawal for ${method.name} is $${method.minAmount}.`);
        return;
      }
    }

    setShowConfirmModal(true);
  };

  const handleWithdraw = async () => {
    setShowConfirmModal(false);

    const result = await withdraw(parseFloat(amount), selectedMethod ?? undefined);

    if (result) {
      if (result.broker_redirect_url) {
        // Live mode - redirect to broker
        Alert.alert(
          'Redirecting to Broker',
          'You will be redirected to your broker to complete the withdrawal.',
          [
            {
              text: 'Continue',
              onPress: () => Linking.openURL(result.broker_redirect_url!),
            },
            { text: 'Cancel', style: 'cancel' },
          ]
        );
      } else {
        // Paper mode or instant withdrawal - show success
        setWithdrawResult({
          amount: result.amount,
          newBalance: result.new_balance,
          estimatedCompletion: result.estimated_completion,
        });
        setShowSuccessModal(true);
        refetchWallet();
      }
    } else {
      Alert.alert('Withdrawal Failed', 'There was an error processing your withdrawal. Please try again.');
    }
  };

  const handleSuccessClose = () => {
    setShowSuccessModal(false);
    navigation.goBack();
  };

  const handleMaxAmount = () => {
    setAmount(String(availableBalance));
  };

  const parsedAmount = parseFloat(amount) || 0;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => navigation.goBack()}
          >
            <BackIcon color={colors.textPrimary} size={24} />
          </TouchableOpacity>
          <Text style={styles.title}>Withdraw Funds</Text>
          <View style={styles.headerSpacer} />
        </View>

        {/* Mode Badge */}
        <View style={[styles.modeBanner, isPaperMode ? styles.paperBanner : styles.liveBanner]}>
          <Text style={styles.modeBannerText}>
            {isPaperMode ? 'PAPER MODE - Funds are simulated' : 'LIVE MODE - Real funds'}
          </Text>
        </View>

        {/* Available Balance */}
        <View style={styles.balanceCard}>
          <Text style={styles.balanceLabel}>Available Balance</Text>
          <Text style={styles.balanceValue}>
            ${availableBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </Text>
        </View>

        {/* Amount Input */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>AMOUNT</Text>
            <TouchableOpacity onPress={handleMaxAmount}>
              <Text style={styles.maxButton}>MAX</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.amountCard}>
            <View style={styles.amountInputWrapper}>
              <Text style={styles.currencySymbol}>$</Text>
              <TextInput
                style={styles.amountInput}
                value={amount}
                onChangeText={setAmount}
                placeholder="0.00"
                placeholderTextColor={colors.textMuted}
                keyboardType="decimal-pad"
              />
            </View>
            {parsedAmount > availableBalance && (
              <Text style={styles.errorText}>
                Amount exceeds available balance
              </Text>
            )}
          </View>
        </View>

        {/* Withdrawal Methods - Only show for live mode */}
        {!isPaperMode && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>WITHDRAWAL METHOD</Text>
            <View style={styles.methodsList}>
              {withdrawMethods.map((method) => {
                const Icon = method.icon;
                const isSelected = selectedMethod === method.id;
                return (
                  <TouchableOpacity
                    key={method.id}
                    style={[styles.methodCard, isSelected && styles.methodCardSelected]}
                    onPress={() => setSelectedMethod(method.id)}
                  >
                    <View style={styles.methodIcon}>
                      <Icon color={isSelected ? colors.lpCyan : colors.textSecondary} size={24} />
                    </View>
                    <View style={styles.methodInfo}>
                      <Text style={[styles.methodName, isSelected && styles.methodNameSelected]}>
                        {method.name}
                      </Text>
                      <Text style={styles.methodDetails}>
                        Fee: {method.fee} | {method.time} | Min: ${method.minAmount}
                      </Text>
                    </View>
                    <View style={[styles.radioOuter, isSelected && styles.radioOuterSelected]}>
                      {isSelected && <View style={styles.radioInner} />}
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        )}

        {/* Paper Mode Info */}
        {isPaperMode && (
          <View style={styles.paperInfoCard}>
            <Text style={styles.paperInfoTitle}>Instant Paper Withdrawal</Text>
            <Text style={styles.paperInfoText}>
              Paper withdrawals are deducted from your account immediately with no fees.
              These are simulated funds for practice trading.
            </Text>
          </View>
        )}

        {/* Summary */}
        {parsedAmount > 0 && (
          <View style={styles.summaryCard}>
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Withdrawal Amount</Text>
              <Text style={styles.summaryValue}>${parsedAmount.toFixed(2)}</Text>
            </View>
            {!isPaperMode && selectedMethod && (
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Fee</Text>
                <Text style={[styles.summaryValue, { color: colors.lpRed }]}>
                  -${getFee().toFixed(2)}
                </Text>
              </View>
            )}
            <View style={[styles.summaryRow, styles.summaryTotal]}>
              <Text style={styles.summaryTotalLabel}>
                {isPaperMode ? 'Amount to Remove' : "You'll Receive"}
              </Text>
              <Text style={styles.summaryTotalValue}>
                ${(isPaperMode ? parsedAmount : getNetAmount()).toFixed(2)}
              </Text>
            </View>
          </View>
        )}

        {/* Warning */}
        {!isPaperMode && (
          <View style={styles.warningCard}>
            <Text style={styles.warningTitle}>Important</Text>
            <Text style={styles.warningText}>
              Withdrawals are processed during business hours (Mon-Fri, 9AM-5PM EST).
              Please ensure your withdrawal details are correct as transactions cannot be reversed.
            </Text>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <PrimaryButton
            title={isPaperMode ? 'REMOVE FUNDS' : 'REQUEST WITHDRAWAL'}
            onPress={handleConfirmWithdraw}
            loading={loading}
            disabled={
              !amount ||
              parseFloat(amount) <= 0 ||
              parseFloat(amount) > availableBalance ||
              (!isPaperMode && !selectedMethod)
            }
            size="lg"
            color={colors.lpRed}
          />
          <GhostButton
            title="CANCEL"
            onPress={() => navigation.goBack()}
            size="lg"
            style={styles.cancelButton}
          />
        </View>
      </ScrollView>

      {/* Confirmation Modal */}
      <Modal
        visible={showConfirmModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowConfirmModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Confirm Withdrawal</Text>
            <Text style={styles.modalText}>
              Are you sure you want to withdraw ${parsedAmount.toFixed(2)}
              {isPaperMode ? ' from your paper account' : ` via ${selectedMethod}`}?
              {!isPaperMode && `\n\nYou will receive $${getNetAmount().toFixed(2)} after fees.`}
            </Text>
            <View style={styles.modalButtons}>
              <GhostButton
                title="Cancel"
                onPress={() => setShowConfirmModal(false)}
                size="md"
                style={styles.modalButton}
              />
              <PrimaryButton
                title="Confirm"
                onPress={handleWithdraw}
                loading={loading}
                size="md"
                color={colors.lpRed}
                style={styles.modalButton}
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Success Modal */}
      <Modal
        visible={showSuccessModal}
        transparent
        animationType="fade"
        onRequestClose={handleSuccessClose}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.successIcon}>
              {isPaperMode ? (
                <CheckIcon color={colors.lpGreen} size={48} />
              ) : (
                <ClockIcon color={colors.lpAmber} size={48} />
              )}
            </View>
            <Text style={styles.modalTitle}>
              {isPaperMode ? 'Withdrawal Complete!' : 'Withdrawal Requested'}
            </Text>
            <Text style={styles.modalText}>
              {isPaperMode
                ? `$${withdrawResult?.amount.toFixed(2)} has been removed from your paper account.`
                : `Your withdrawal of $${withdrawResult?.amount.toFixed(2)} has been submitted.`}
            </Text>
            {withdrawResult?.estimatedCompletion && !isPaperMode && (
              <View style={styles.estimateCard}>
                <Text style={styles.estimateLabel}>Estimated Completion</Text>
                <Text style={styles.estimateValue}>{withdrawResult.estimatedCompletion}</Text>
              </View>
            )}
            <View style={styles.newBalanceCard}>
              <Text style={styles.newBalanceLabel}>New Balance</Text>
              <Text style={styles.newBalanceValue}>
                ${withdrawResult?.newBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </Text>
            </View>
            <PrimaryButton
              title="Done"
              onPress={handleSuccessClose}
              size="lg"
              style={styles.doneButton}
            />
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.lg,
  },
  backButton: {
    padding: spacing.sm,
    marginLeft: -spacing.sm,
  },
  title: {
    ...typography.h2,
    color: colors.textPrimary,
  },
  headerSpacer: {
    width: 40,
  },
  modeBanner: {
    padding: spacing.md,
    borderRadius: borderRadius.md,
    marginBottom: spacing.xl,
    alignItems: 'center',
  },
  paperBanner: {
    backgroundColor: `${colors.lpAmber}20`,
  },
  liveBanner: {
    backgroundColor: `${colors.lpGreen}20`,
  },
  modeBannerText: {
    ...typography.labelSM,
    color: colors.textPrimary,
  },
  balanceCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    alignItems: 'center',
  },
  balanceLabel: {
    ...typography.labelSM,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  balanceValue: {
    ...typography.heroMD,
    color: colors.lpGold,
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
  maxButton: {
    ...typography.labelMD,
    color: colors.lpCyan,
  },
  amountCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
  },
  amountInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  currencySymbol: {
    ...typography.heroLG,
    color: colors.textMuted,
    marginRight: spacing.sm,
  },
  amountInput: {
    ...typography.heroLG,
    color: colors.lpGold,
    minWidth: 100,
    textAlign: 'center',
  },
  errorText: {
    ...typography.bodySM,
    color: colors.lpRed,
    textAlign: 'center',
    marginTop: spacing.md,
  },
  methodsList: {
    gap: spacing.md,
  },
  methodCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'transparent',
  },
  methodCardSelected: {
    borderColor: colors.lpCyan,
    backgroundColor: `${colors.lpCyan}10`,
  },
  methodIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.lpBlack,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  methodInfo: {
    flex: 1,
  },
  methodName: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  methodNameSelected: {
    color: colors.lpCyan,
  },
  methodDetails: {
    ...typography.bodySM,
    color: colors.textMuted,
    marginTop: 2,
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.textMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterSelected: {
    borderColor: colors.lpCyan,
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.lpCyan,
  },
  paperInfoCard: {
    backgroundColor: `${colors.lpAmber}15`,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    borderWidth: 1,
    borderColor: `${colors.lpAmber}30`,
  },
  paperInfoTitle: {
    ...typography.bodyLG,
    color: colors.lpAmber,
    fontWeight: '600',
    marginBottom: spacing.sm,
  },
  paperInfoText: {
    ...typography.bodySM,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  summaryCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
  },
  summaryLabel: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  summaryValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '500',
  },
  summaryTotal: {
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    marginTop: spacing.sm,
    paddingTop: spacing.md,
  },
  summaryTotalLabel: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  summaryTotalValue: {
    ...typography.h3,
    color: colors.lpGreen,
    fontWeight: '700',
  },
  warningCard: {
    backgroundColor: `${colors.lpAmber}15`,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    borderLeftWidth: 3,
    borderLeftColor: colors.lpAmber,
  },
  warningTitle: {
    ...typography.labelMD,
    color: colors.lpAmber,
    marginBottom: spacing.xs,
  },
  warningText: {
    ...typography.bodySM,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  actionButtons: {
    gap: spacing.md,
  },
  cancelButton: {
    marginTop: spacing.sm,
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
    maxWidth: 400,
    alignItems: 'center',
  },
  modalTitle: {
    ...typography.h3,
    color: colors.textPrimary,
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  modalText: {
    ...typography.bodyMD,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: spacing.md,
    width: '100%',
  },
  modalButton: {
    flex: 1,
  },
  successIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: `${colors.lpGreen}20`,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  estimateCard: {
    backgroundColor: `${colors.lpAmber}15`,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    width: '100%',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  estimateLabel: {
    ...typography.labelSM,
    color: colors.lpAmber,
    marginBottom: spacing.xs,
  },
  estimateValue: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  newBalanceCard: {
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    width: '100%',
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  newBalanceLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  newBalanceValue: {
    ...typography.heroMD,
    color: colors.lpGold,
  },
  doneButton: {
    width: '100%',
  },
});

export default WithdrawScreen;
