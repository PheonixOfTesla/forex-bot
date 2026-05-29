import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, spacing, borderRadius } from '../theme';
import { useTradingMode } from '../context/TradingModeContext';

interface TradingModeIndicatorProps {
  compact?: boolean;
}

export const TradingModeIndicator: React.FC<TradingModeIndicatorProps> = ({
  compact = false,
}) => {
  const { mode, isLoading } = useTradingMode();

  if (isLoading) {
    return null;
  }

  const isPaper = mode === 'paper';
  const indicatorColor = isPaper ? colors.lpGreen : colors.lpRed;

  if (compact) {
    return (
      <View style={[styles.compactContainer, { backgroundColor: indicatorColor + '30' }]}>
        <View style={[styles.dot, { backgroundColor: indicatorColor }]} />
        <Text style={[styles.compactText, { color: indicatorColor }]}>
          {isPaper ? 'PAPER' : 'LIVE'}
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { borderColor: indicatorColor }]}>
      <View style={[styles.pulsingDot, { backgroundColor: indicatorColor }]} />
      <Text style={[styles.text, { color: indicatorColor }]}>
        {isPaper ? 'PAPER MODE' : 'LIVE TRADING'}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.lpSurface,
    borderWidth: 1,
    borderRadius: borderRadius.full,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    gap: spacing.sm,
  },
  pulsingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  text: {
    ...typography.labelSM,
  },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: borderRadius.sm,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  compactText: {
    ...typography.labelSM,
    fontSize: 9,
  },
});

export default TradingModeIndicator;
