import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TextInput,
  TouchableOpacity,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';

interface Signal {
  id: string;
  pair: string;
  direction: 'LONG' | 'SHORT';
  confidence: number;
  entry: number;
  stopLoss: number;
  takeProfit: number;
}

interface TradeExecutionModalProps {
  visible: boolean;
  signal: Signal | null;
  balance: number;
  onClose: () => void;
  onExecute: (signalId: string, lotSize: number) => Promise<void>;
  loading?: boolean;
}

const CloseIcon = ({ size = 24, color = colors.textMuted }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth={2} strokeLinecap="round" />
  </Svg>
);

const LOT_PRESETS = [0.01, 0.05, 0.1, 0.5, 1.0];

export const TradeExecutionModal: React.FC<TradeExecutionModalProps> = ({
  visible,
  signal,
  balance,
  onClose,
  onExecute,
  loading = false,
}) => {
  const [lotSize, setLotSize] = useState('0.1');
  const [inputFocused, setInputFocused] = useState(false);

  // Reset lot size when modal opens
  useEffect(() => {
    if (visible) {
      setLotSize('0.1');
    }
  }, [visible]);

  if (!signal) return null;

  const lot = parseFloat(lotSize) || 0;

  // Standard lot = 100,000 units
  const units = lot * 100000;
  const positionValue = units * signal.entry;

  // Calculate risk (distance to stop loss)
  const pipValue = signal.pair.includes('JPY') ? 0.01 : 0.0001;
  const stopPips = Math.abs(signal.entry - signal.stopLoss) / pipValue;
  const profitPips = Math.abs(signal.takeProfit - signal.entry) / pipValue;

  // Risk in dollars (rough estimate - $10 per pip per standard lot for most pairs)
  const pipValueUSD = lot * 10; // ~$10 per pip per lot
  const riskAmount = stopPips * pipValueUSD;
  const potentialProfit = profitPips * pipValueUSD;
  const riskPercent = (riskAmount / balance) * 100;

  const handleExecute = async () => {
    if (lot <= 0) return;
    await onExecute(signal.id, lot);
  };

  const formatPrice = (price: number) => {
    if (signal.pair.includes('JPY')) return price.toFixed(3);
    return price.toFixed(5);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <Pressable style={styles.overlay} onPress={onClose}>
        <Pressable style={styles.modal} onPress={(e) => e.stopPropagation()}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Execute Trade</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
              <CloseIcon />
            </TouchableOpacity>
          </View>

          {/* Signal Info */}
          <View style={styles.signalInfo}>
            <View style={styles.signalRow}>
              <Text style={styles.pair}>{signal.pair}</Text>
              <View style={[
                styles.directionBadge,
                { backgroundColor: signal.direction === 'LONG' ? colors.lpGreen + '20' : colors.lpRed + '20' }
              ]}>
                <Text style={[
                  styles.directionText,
                  { color: signal.direction === 'LONG' ? colors.lpGreen : colors.lpRed }
                ]}>
                  {signal.direction}
                </Text>
              </View>
            </View>
            <Text style={styles.confidence}>{signal.confidence}% confidence</Text>
          </View>

          {/* Price Levels */}
          <View style={styles.priceSection}>
            <View style={styles.priceRow}>
              <Text style={styles.priceLabel}>Entry</Text>
              <Text style={styles.priceValue}>{formatPrice(signal.entry)}</Text>
            </View>
            <View style={styles.priceRow}>
              <Text style={styles.priceLabel}>Stop Loss</Text>
              <Text style={[styles.priceValue, { color: colors.lpRed }]}>{formatPrice(signal.stopLoss)}</Text>
            </View>
            <View style={styles.priceRow}>
              <Text style={styles.priceLabel}>Take Profit</Text>
              <Text style={[styles.priceValue, { color: colors.lpGreen }]}>{formatPrice(signal.takeProfit)}</Text>
            </View>
          </View>

          {/* Lot Size Input */}
          <View style={styles.lotSection}>
            <Text style={styles.sectionLabel}>LOT SIZE</Text>
            <View style={styles.lotInputRow}>
              <TextInput
                style={[styles.lotInput, inputFocused && styles.lotInputFocused]}
                value={lotSize}
                onChangeText={setLotSize}
                keyboardType="decimal-pad"
                placeholder="0.1"
                placeholderTextColor={colors.textMuted}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
              />
              <Text style={styles.lotUnit}>lots</Text>
            </View>

            {/* Quick Select Buttons */}
            <View style={styles.presetRow}>
              {LOT_PRESETS.map((preset) => (
                <TouchableOpacity
                  key={preset}
                  style={[
                    styles.presetButton,
                    parseFloat(lotSize) === preset && styles.presetButtonActive
                  ]}
                  onPress={() => setLotSize(preset.toString())}
                >
                  <Text style={[
                    styles.presetText,
                    parseFloat(lotSize) === preset && styles.presetTextActive
                  ]}>
                    {preset}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Position Summary */}
          <View style={styles.summarySection}>
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Position Value</Text>
              <Text style={styles.summaryValue}>${positionValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</Text>
            </View>
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Units</Text>
              <Text style={styles.summaryValue}>{units.toLocaleString()}</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Risk Amount</Text>
              <Text style={[styles.summaryValue, { color: colors.lpRed }]}>
                -${riskAmount.toFixed(2)} ({riskPercent.toFixed(1)}%)
              </Text>
            </View>
            <View style={styles.summaryRow}>
              <Text style={styles.summaryLabel}>Potential Profit</Text>
              <Text style={[styles.summaryValue, { color: colors.lpGreen }]}>
                +${potentialProfit.toFixed(2)}
              </Text>
            </View>
          </View>

          {/* Warning if risk > 5% */}
          {riskPercent > 5 && (
            <View style={styles.warning}>
              <Text style={styles.warningText}>
                Risk exceeds 5% of balance. Consider reducing lot size.
              </Text>
            </View>
          )}

          {/* Action Buttons */}
          <View style={styles.actions}>
            <TouchableOpacity style={styles.cancelButton} onPress={onClose}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.executeButton, lot <= 0 && styles.executeButtonDisabled]}
              onPress={handleExecute}
              disabled={lot <= 0 || loading}
            >
              {loading ? (
                <ActivityIndicator color={colors.lpBlack} />
              ) : (
                <Text style={styles.executeText}>
                  Execute {signal.direction}
                </Text>
              )}
            </TouchableOpacity>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.8)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  modal: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    width: '100%',
    maxWidth: 400,
    padding: spacing.xl,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  title: {
    ...typography.h2,
    color: colors.textPrimary,
  },
  closeButton: {
    padding: spacing.xs,
  },
  signalInfo: {
    marginBottom: spacing.lg,
  },
  signalRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  pair: {
    ...typography.h3,
    color: colors.textPrimary,
  },
  directionBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  directionText: {
    ...typography.labelSM,
    fontWeight: '700',
  },
  confidence: {
    ...typography.bodySM,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  priceSection: {
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  priceLabel: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  priceValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontFamily: 'monospace',
  },
  lotSection: {
    marginBottom: spacing.lg,
  },
  sectionLabel: {
    ...typography.labelSM,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  lotInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  lotInput: {
    flex: 1,
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.borderDark,
    padding: spacing.md,
    ...typography.h3,
    color: colors.textPrimary,
  },
  lotInputFocused: {
    borderColor: colors.lpCyan,
  },
  lotUnit: {
    ...typography.bodyMD,
    color: colors.textMuted,
  },
  presetRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  presetButton: {
    flex: 1,
    backgroundColor: colors.lpBlack,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.borderDark,
  },
  presetButtonActive: {
    backgroundColor: colors.lpCyan + '20',
    borderColor: colors.lpCyan,
  },
  presetText: {
    ...typography.labelMD,
    color: colors.textSecondary,
  },
  presetTextActive: {
    color: colors.lpCyan,
  },
  summarySection: {
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs,
  },
  summaryLabel: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  summaryValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    backgroundColor: colors.borderDark,
    marginVertical: spacing.sm,
  },
  warning: {
    backgroundColor: colors.lpAmber + '20',
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  warningText: {
    ...typography.bodySM,
    color: colors.lpAmber,
    textAlign: 'center',
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
    alignItems: 'center',
  },
  cancelText: {
    ...typography.labelMD,
    color: colors.textSecondary,
  },
  executeButton: {
    flex: 2,
    backgroundColor: colors.lpCyan,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  executeButtonDisabled: {
    opacity: 0.5,
  },
  executeText: {
    ...typography.labelMD,
    color: colors.lpBlack,
    fontWeight: '700',
  },
});
