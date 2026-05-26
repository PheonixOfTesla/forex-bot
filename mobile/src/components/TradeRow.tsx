import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { colors, typography, spacing, borderRadius } from '../theme';
import { TradeDirectionPill } from './TradeDirectionPill';

interface TradeRowProps {
  asset: string;
  direction: 'LONG' | 'SHORT';
  pnl: number;
  date: string;
  confidence: number;
  onPress?: () => void;
}

export const TradeRow: React.FC<TradeRowProps> = ({
  asset,
  direction,
  pnl,
  date,
  confidence,
  onPress,
}) => {
  const isWin = pnl >= 0;
  const borderColor = isWin ? colors.lpGreen : colors.lpRed;
  const pnlColor = isWin ? colors.lpGreen : colors.lpRed;
  const pnlPrefix = isWin ? '+' : '';

  return (
    <TouchableOpacity
      style={[styles.container, { borderLeftColor: borderColor }]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.leftSection}>
        <View style={styles.topRow}>
          <Text style={styles.asset}>{asset}</Text>
          <TradeDirectionPill direction={direction} size="sm" />
        </View>
        <Text style={styles.date}>{date}</Text>
      </View>

      <View style={styles.rightSection}>
        <Text style={[styles.pnl, { color: pnlColor }]}>
          {pnlPrefix}${Math.abs(pnl).toFixed(2)}
        </Text>
        <Text style={styles.confidence}>{confidence}% conf</Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    borderLeftWidth: 3,
    padding: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  leftSection: {
    flex: 1,
    gap: spacing.xs,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  asset: {
    ...typography.h4,
    color: colors.textPrimary,
  },
  date: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  rightSection: {
    alignItems: 'flex-end',
    gap: spacing.xs,
  },
  pnl: {
    ...typography.h3,
    fontWeight: '700',
  },
  confidence: {
    ...typography.bodySM,
    color: colors.textSecondary,
  },
});
