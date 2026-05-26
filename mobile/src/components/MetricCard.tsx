import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { colors, typography, spacing, borderRadius } from '../theme';

interface MetricCardProps {
  value: string | number;
  label: string;
  valueColor?: string;
  valueSize?: 'sm' | 'md' | 'lg' | 'xl';
  style?: ViewStyle;
  showBorder?: boolean;
  borderColor?: string;
}

const valueSizes = {
  sm: typography.h3,
  md: typography.heroMD,
  lg: typography.heroLG,
  xl: typography.heroXL,
};

export const MetricCard: React.FC<MetricCardProps> = ({
  value,
  label,
  valueColor = colors.textPrimary,
  valueSize = 'md',
  style,
  showBorder = false,
  borderColor = colors.lpCyan,
}) => {
  return (
    <View
      style={[
        styles.container,
        showBorder && { borderLeftWidth: 3, borderLeftColor: borderColor },
        style,
      ]}
    >
      <Text style={[valueSizes[valueSize], { color: valueColor }]}>
        {value}
      </Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.lpSurface,
    padding: spacing.lg,
    borderRadius: borderRadius.lg,
  },
  label: {
    ...typography.labelSM,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
});
