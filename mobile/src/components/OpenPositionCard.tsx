import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  Pressable,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';

interface Position {
  id: string;
  pair: string;
  direction: 'long' | 'short';
  entry_price: number;
  current_price: number;
  size: number;
  pnl: number;
  stop_loss?: number;
  take_profit?: number;
  opened_at: string;
}

interface OpenPositionCardProps {
  position: Position;
  onClose: (positionId: string, exitPrice: number) => Promise<void>;
}

const CloseIcon = ({ size = 20, color = colors.textMuted }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth={2} strokeLinecap="round" />
  </Svg>
);

const TrendUpIcon = ({ size = 16, color = colors.lpGreen }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path d="M23 6l-9.5 9.5-5-5L1 18" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);

const TrendDownIcon = ({ size = 16, color = colors.lpRed }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path d="M23 18l-9.5-9.5-5 5L1 6" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);

export const OpenPositionCard: React.FC<OpenPositionCardProps> = ({ position, onClose }) => {
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [exitPrice, setExitPrice] = useState(position.current_price.toString());
  const [closing, setClosing] = useState(false);

  const isProfit = position.pnl >= 0;
  const pnlColor = isProfit ? colors.lpGreen : colors.lpRed;
  const directionColor = position.direction === 'long' ? colors.lpGreen : colors.lpRed;

  const formatPrice = (price: number) => {
    if (position.pair.includes('JPY')) return price.toFixed(3);
    if (position.pair.includes('BTC') || position.pair.includes('ETH')) return price.toFixed(2);
    return price.toFixed(5);
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  const handleClose = async () => {
    const price = parseFloat(exitPrice);
    if (isNaN(price) || price <= 0) return;

    setClosing(true);
    try {
      await onClose(position.id, price);
      setShowCloseModal(false);
    } finally {
      setClosing(false);
    }
  };

  // Calculate distance to SL/TP in pips
  const pipValue = position.pair.includes('JPY') ? 0.01 : 0.0001;
  const slDistance = position.stop_loss
    ? Math.abs(position.current_price - position.stop_loss) / pipValue
    : null;
  const tpDistance = position.take_profit
    ? Math.abs(position.take_profit - position.current_price) / pipValue
    : null;

  return (
    <>
      <View style={[styles.card, { borderLeftColor: pnlColor }]}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.pairRow}>
            <Text style={styles.pair}>{position.pair}</Text>
            <View style={[styles.directionBadge, { backgroundColor: directionColor + '20' }]}>
              <Text style={[styles.directionText, { color: directionColor }]}>
                {position.direction.toUpperCase()}
              </Text>
            </View>
          </View>
          <Text style={styles.time}>{formatTime(position.opened_at)}</Text>
        </View>

        {/* P&L Display */}
        <View style={styles.pnlSection}>
          <View style={styles.pnlRow}>
            {isProfit ? <TrendUpIcon /> : <TrendDownIcon color={colors.lpRed} />}
            <Text style={[styles.pnlValue, { color: pnlColor }]}>
              {isProfit ? '+' : ''}{position.pnl.toFixed(2)} USD
            </Text>
          </View>
        </View>

        {/* Trade Details */}
        <View style={styles.detailsGrid}>
          <View style={styles.detailItem}>
            <Text style={styles.detailLabel}>Entry</Text>
            <Text style={styles.detailValue}>{formatPrice(position.entry_price)}</Text>
          </View>
          <View style={styles.detailItem}>
            <Text style={styles.detailLabel}>Current</Text>
            <Text style={[styles.detailValue, { color: pnlColor }]}>
              {formatPrice(position.current_price)}
            </Text>
          </View>
          <View style={styles.detailItem}>
            <Text style={styles.detailLabel}>Size</Text>
            <Text style={styles.detailValue}>{position.size.toFixed(2)}</Text>
          </View>
        </View>

        {/* SL/TP Row */}
        {(position.stop_loss || position.take_profit) && (
          <View style={styles.slTpRow}>
            {position.stop_loss && (
              <View style={styles.slTpItem}>
                <Text style={[styles.slTpLabel, { color: colors.lpRed }]}>SL</Text>
                <Text style={styles.slTpValue}>{formatPrice(position.stop_loss)}</Text>
                {slDistance && <Text style={styles.slTpPips}>{slDistance.toFixed(0)} pips</Text>}
              </View>
            )}
            {position.take_profit && (
              <View style={styles.slTpItem}>
                <Text style={[styles.slTpLabel, { color: colors.lpGreen }]}>TP</Text>
                <Text style={styles.slTpValue}>{formatPrice(position.take_profit)}</Text>
                {tpDistance && <Text style={styles.slTpPips}>{tpDistance.toFixed(0)} pips</Text>}
              </View>
            )}
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.closeButton}
            onPress={() => {
              setExitPrice(position.current_price.toString());
              setShowCloseModal(true);
            }}
          >
            <Text style={styles.closeButtonText}>Close Position</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Close Position Modal */}
      <Modal visible={showCloseModal} transparent animationType="fade">
        <Pressable style={styles.overlay} onPress={() => setShowCloseModal(false)}>
          <Pressable style={styles.modal} onPress={(e) => e.stopPropagation()}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Close Position</Text>
              <TouchableOpacity onPress={() => setShowCloseModal(false)}>
                <CloseIcon />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalPair}>{position.pair} {position.direction.toUpperCase()}</Text>

            <View style={styles.modalDetail}>
              <Text style={styles.modalLabel}>Exit Price</Text>
              <TextInput
                style={styles.priceInput}
                value={exitPrice}
                onChangeText={setExitPrice}
                keyboardType="decimal-pad"
                placeholder={formatPrice(position.current_price)}
                placeholderTextColor={colors.textMuted}
              />
            </View>

            <View style={styles.modalDetail}>
              <Text style={styles.modalLabel}>Estimated P&L</Text>
              <Text style={[styles.modalValue, { color: pnlColor }]}>
                {isProfit ? '+' : ''}{position.pnl.toFixed(2)} USD
              </Text>
            </View>

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.cancelButton}
                onPress={() => setShowCloseModal(false)}
              >
                <Text style={styles.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.confirmButton, closing && styles.confirmButtonDisabled]}
                onPress={handleClose}
                disabled={closing}
              >
                {closing ? (
                  <ActivityIndicator color={colors.lpBlack} />
                ) : (
                  <Text style={styles.confirmText}>Close Trade</Text>
                )}
              </TouchableOpacity>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderLeftWidth: 3,
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  pairRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  pair: {
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
    fontWeight: '700',
  },
  time: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  pnlSection: {
    marginBottom: spacing.md,
  },
  pnlRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  pnlValue: {
    ...typography.h3,
    fontWeight: '700',
  },
  detailsGrid: {
    flexDirection: 'row',
    marginBottom: spacing.md,
  },
  detailItem: {
    flex: 1,
  },
  detailLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: 2,
  },
  detailValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontFamily: 'monospace',
  },
  slTpRow: {
    flexDirection: 'row',
    gap: spacing.lg,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    marginBottom: spacing.md,
  },
  slTpItem: {
    flex: 1,
  },
  slTpLabel: {
    ...typography.labelSM,
    fontWeight: '600',
  },
  slTpValue: {
    ...typography.bodySM,
    color: colors.textSecondary,
    fontFamily: 'monospace',
  },
  slTpPips: {
    ...typography.labelSM,
    color: colors.textMuted,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  closeButton: {
    flex: 1,
    backgroundColor: colors.lpRed + '20',
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.lpRed,
  },
  closeButtonText: {
    ...typography.labelMD,
    color: colors.lpRed,
    fontWeight: '600',
  },
  // Modal styles
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
    padding: spacing.xl,
    width: '100%',
    maxWidth: 360,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  modalTitle: {
    ...typography.h3,
    color: colors.textPrimary,
  },
  modalPair: {
    ...typography.h4,
    color: colors.lpCyan,
    marginBottom: spacing.lg,
  },
  modalDetail: {
    marginBottom: spacing.md,
  },
  modalLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.xs,
  },
  modalValue: {
    ...typography.h4,
    color: colors.textPrimary,
  },
  priceInput: {
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    ...typography.bodyMD,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: colors.borderDark,
  },
  modalActions: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.lg,
  },
  cancelButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  cancelText: {
    ...typography.labelMD,
    color: colors.textSecondary,
  },
  confirmButton: {
    flex: 1,
    backgroundColor: colors.lpRed,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: 'center',
  },
  confirmButtonDisabled: {
    opacity: 0.5,
  },
  confirmText: {
    ...typography.labelMD,
    color: colors.textPrimary,
    fontWeight: '700',
  },
});
