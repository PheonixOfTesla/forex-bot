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
import { useRouter } from 'expo-router';
import Svg, { Path, Rect } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import { PrimaryButton, GhostButton } from '../components';
import { useDeposit, useWallet } from '../hooks/useApi';

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

const CardIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Rect
      x="2"
      y="5"
      width="20"
      height="14"
      rx="2"
      stroke={color}
      strokeWidth={2}
    />
    <Path d="M2 10h20" stroke={color} strokeWidth={2} />
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

type PaymentMethod = 'bank' | 'card' | 'crypto';

const PRESET_AMOUNTS = [100, 500, 1000, 5000];

export const DepositScreen: React.FC = () => {
  const router = useRouter();
  const { data: wallet, refetch: refetchWallet } = useWallet();
  const { deposit, loading } = useDeposit();

  const [amount, setAmount] = useState('');
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [depositResult, setDepositResult] = useState<{
    amount: number;
    newBalance: number;
    status: string;
  } | null>(null);

  const isPaperMode = wallet?.mode === 'paper';

  const paymentMethods = [
    { id: 'bank' as const, name: 'Bank Transfer', icon: BankIcon, fee: '0%', time: '1-3 days' },
    { id: 'card' as const, name: 'Credit/Debit Card', icon: CardIcon, fee: '2.5%', time: 'Instant' },
    { id: 'crypto' as const, name: 'Cryptocurrency', icon: CryptoIcon, fee: '1%', time: '10-30 min' },
  ];

  const calculateFee = (amt: number, method: PaymentMethod | null) => {
    if (!method) return 0;
    switch (method) {
      case 'card':
        return amt * 0.025;
      case 'crypto':
        return amt * 0.01;
      default:
        return 0;
    }
  };

  const handleConfirmDeposit = () => {
    if (!amount || parseFloat(amount) <= 0) {
      Alert.alert('Invalid Amount', 'Please enter a valid deposit amount.');
      return;
    }
    if (!selectedMethod && !isPaperMode) {
      Alert.alert('Select Method', 'Please select a payment method.');
      return;
    }
    setShowConfirmModal(true);
  };

  const handleDeposit = async () => {
    setShowConfirmModal(false);

    const result = await deposit(parseFloat(amount), selectedMethod ?? undefined);

    if (result) {
      if (result.broker_redirect_url) {
        // Live mode - redirect to broker
        Alert.alert(
          'Redirecting to Broker',
          'You will be redirected to your broker to complete the deposit.',
          [
            {
              text: 'Continue',
              onPress: () => Linking.openURL(result.broker_redirect_url!),
            },
            { text: 'Cancel', style: 'cancel' },
          ]
        );
      } else {
        // Paper mode or instant deposit - show success
        setDepositResult({
          amount: result.amount,
          newBalance: result.new_balance,
          status: result.status,
        });
        setShowSuccessModal(true);
        refetchWallet();
      }
    } else {
      Alert.alert('Deposit Failed', 'There was an error processing your deposit. Please try again.');
    }
  };

  const handleSuccessClose = () => {
    setShowSuccessModal(false);
    router.back();
  };

  const parsedAmount = parseFloat(amount) || 0;
  const fee = calculateFee(parsedAmount, selectedMethod);
  const total = parsedAmount + fee;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity
            style={styles.backButton}
            onPress={() => router.back()}
          >
            <BackIcon color={colors.textPrimary} size={24} />
          </TouchableOpacity>
          <Text style={styles.title}>Deposit Funds</Text>
          <View style={styles.headerSpacer} />
        </View>

        {/* Mode Badge */}
        <View style={[styles.modeBanner, isPaperMode ? styles.paperBanner : styles.liveBanner]}>
          <Text style={styles.modeBannerText}>
            {isPaperMode ? 'PAPER MODE - Funds are simulated' : 'LIVE MODE - Real funds'}
          </Text>
        </View>

        {/* Amount Input */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>AMOUNT</Text>
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
          </View>

          {/* Preset Amounts */}
          <View style={styles.presetAmounts}>
            {PRESET_AMOUNTS.map((preset) => (
              <TouchableOpacity
                key={preset}
                style={[
                  styles.presetButton,
                  amount === String(preset) && styles.presetButtonActive,
                ]}
                onPress={() => setAmount(String(preset))}
              >
                <Text
                  style={[
                    styles.presetText,
                    amount === String(preset) && styles.presetTextActive,
                  ]}
                >
                  ${preset}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Payment Methods - Only show for live mode */}
        {!isPaperMode && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>PAYMENT METHOD</Text>
            <View style={styles.methodsList}>
              {paymentMethods.map((method) => {
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
                        Fee: {method.fee} | {method.time}
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
            <Text style={styles.paperInfoTitle}>Instant Paper Deposit</Text>
            <Text style={styles.paperInfoText}>
              Paper deposits are added to your account immediately with no fees.
              These are simulated funds for practice trading.
            </Text>
          </View>
        )}

        {/* Fee Summary */}
        {parsedAmount > 0 && (
          <View style={styles.summaryCard}>
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Deposit Amount</Text>
              <Text style={styles.summaryValue}>${parsedAmount.toFixed(2)}</Text>
            </View>
            {!isPaperMode && (
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Fee</Text>
                <Text style={styles.summaryValue}>${fee.toFixed(2)}</Text>
              </View>
            )}
            <View style={[styles.summaryRow, styles.summaryTotal]}>
              <Text style={styles.summaryTotalLabel}>
                {isPaperMode ? 'Amount to Add' : 'Total'}
              </Text>
              <Text style={styles.summaryTotalValue}>
                ${(isPaperMode ? parsedAmount : total).toFixed(2)}
              </Text>
            </View>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <PrimaryButton
            title={isPaperMode ? 'ADD FUNDS' : 'DEPOSIT NOW'}
            onPress={handleConfirmDeposit}
            loading={loading}
            disabled={!amount || parseFloat(amount) <= 0 || (!isPaperMode && !selectedMethod)}
            size="lg"
            color={colors.lpGreen}
          />
          <GhostButton
            title="CANCEL"
            onPress={() => router.back()}
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
            <Text style={styles.modalTitle}>Confirm Deposit</Text>
            <Text style={styles.modalText}>
              Are you sure you want to deposit ${parsedAmount.toFixed(2)}
              {isPaperMode ? ' to your paper account' : ` via ${selectedMethod}`}?
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
                onPress={handleDeposit}
                loading={loading}
                size="md"
                color={colors.lpGreen}
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
              <CheckIcon color={colors.lpGreen} size={48} />
            </View>
            <Text style={styles.modalTitle}>Deposit Successful!</Text>
            <Text style={styles.modalText}>
              ${depositResult?.amount.toFixed(2)} has been added to your {isPaperMode ? 'paper' : ''} account.
            </Text>
            <View style={styles.newBalanceCard}>
              <Text style={styles.newBalanceLabel}>New Balance</Text>
              <Text style={styles.newBalanceValue}>
                ${depositResult?.newBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
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
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  amountCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    marginBottom: spacing.md,
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
  presetAmounts: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  presetButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.lpSurface,
    alignItems: 'center',
  },
  presetButtonActive: {
    backgroundColor: `${colors.lpCyan}20`,
    borderWidth: 1,
    borderColor: colors.lpCyan,
  },
  presetText: {
    ...typography.labelMD,
    color: colors.textSecondary,
  },
  presetTextActive: {
    color: colors.lpCyan,
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
    color: colors.lpGold,
    fontWeight: '700',
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

export default DepositScreen;
