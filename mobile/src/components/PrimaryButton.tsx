import React from 'react';
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ViewStyle,
  TextStyle,
  ActivityIndicator,
} from 'react-native';
import { colors, typography, spacing, borderRadius } from '../theme';

interface PrimaryButtonProps {
  title: string;
  onPress: () => void;
  color?: string;
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  size?: 'sm' | 'md' | 'lg';
}

const sizeStyles = {
  sm: { paddingVertical: spacing.sm, paddingHorizontal: spacing.md },
  md: { paddingVertical: spacing.md, paddingHorizontal: spacing.xl },
  lg: { paddingVertical: spacing.lg, paddingHorizontal: spacing.xxl },
};

export const PrimaryButton: React.FC<PrimaryButtonProps> = ({
  title,
  onPress,
  color = colors.lpCyan,
  disabled = false,
  loading = false,
  style,
  textStyle,
  size = 'md',
}) => {
  return (
    <TouchableOpacity
      style={[
        styles.button,
        { backgroundColor: color },
        sizeStyles[size],
        disabled && styles.disabled,
        style,
      ]}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator color={colors.lpBlack} size="small" />
      ) : (
        <Text style={[styles.text, textStyle]}>{title}</Text>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    ...typography.labelLG,
    color: colors.lpBlack,
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.5,
  },
});
