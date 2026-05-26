import React from 'react';
import { View, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { colors, borderRadius } from '../theme';

interface SignalConfidenceBarProps {
  confidence: number; // 0-100
  height?: number;
  showBackground?: boolean;
}

export const SignalConfidenceBar: React.FC<SignalConfidenceBarProps> = ({
  confidence,
  height = 8,
  showBackground = true,
}) => {
  const clampedConfidence = Math.min(100, Math.max(0, confidence));

  return (
    <View
      style={[
        styles.container,
        { height },
        showBackground && styles.withBackground,
      ]}
    >
      <LinearGradient
        colors={[colors.lpCyan, colors.lpPurple]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 0 }}
        style={[
          styles.fill,
          {
            width: `${clampedConfidence}%`,
            height,
          },
        ]}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
    borderRadius: borderRadius.full,
    overflow: 'hidden',
  },
  withBackground: {
    backgroundColor: colors.borderDark,
  },
  fill: {
    borderRadius: borderRadius.full,
  },
});
