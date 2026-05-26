import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Easing } from 'react-native';
import { colors, typography } from '../theme';

type Status = 'LIVE' | 'PAUSED' | 'STOPPED';

interface StatusBadgeProps {
  status: Status;
}

const statusConfig: Record<Status, { color: string; label: string }> = {
  LIVE: { color: colors.lpCyan, label: 'LIVE' },
  PAUSED: { color: colors.lpAmber, label: 'PAUSED' },
  STOPPED: { color: colors.lpRed, label: 'STOPPED' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const config = statusConfig[status];

  useEffect(() => {
    if (status === 'LIVE') {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 0.4,
            duration: 800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    }
  }, [status, pulseAnim]);

  return (
    <View style={[styles.container, { borderColor: config.color }]}>
      <Animated.View
        style={[
          styles.dot,
          { backgroundColor: config.color, opacity: pulseAnim },
        ]}
      />
      <Text style={[styles.label, { color: config.color }]}>
        {config.label}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  label: {
    ...typography.labelMD,
  },
});
