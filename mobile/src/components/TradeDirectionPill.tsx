import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors, typography, borderRadius } from '../theme';

type Direction = 'LONG' | 'SHORT' | 'BUY' | 'SELL';

interface TradeDirectionPillProps {
  direction: Direction;
  size?: 'sm' | 'md' | 'lg';
}

const directionConfig: Record<Direction, { color: string; bg: string }> = {
  LONG: { color: colors.lpGreen, bg: `${colors.lpGreen}20` },
  BUY: { color: colors.lpGreen, bg: `${colors.lpGreen}20` },
  SHORT: { color: colors.lpRed, bg: `${colors.lpRed}20` },
  SELL: { color: colors.lpRed, bg: `${colors.lpRed}20` },
};

const sizeStyles = {
  sm: { paddingHorizontal: 8, paddingVertical: 2 },
  md: { paddingHorizontal: 12, paddingVertical: 4 },
  lg: { paddingHorizontal: 16, paddingVertical: 6 },
};

export const TradeDirectionPill: React.FC<TradeDirectionPillProps> = ({
  direction,
  size = 'md',
}) => {
  const config = directionConfig[direction];
  const sizeStyle = sizeStyles[size];

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: config.bg },
        sizeStyle,
      ]}
    >
      <Text style={[styles.text, { color: config.color }]}>
        {direction}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    borderRadius: borderRadius.sm,
    alignSelf: 'flex-start',
  },
  text: {
    ...typography.labelSM,
    fontWeight: '700',
  },
});
