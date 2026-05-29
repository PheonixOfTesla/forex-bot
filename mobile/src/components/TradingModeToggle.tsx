import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  Alert,
} from 'react-native';
import { colors, typography, spacing, borderRadius } from '../theme';
import { useTradingMode, TradingMode } from '../context/TradingModeContext';

interface TradingModeToggleProps {
  onModeChange?: (mode: TradingMode) => void;
}

export const TradingModeToggle: React.FC<TradingModeToggleProps> = ({
  onModeChange,
}) => {
  const { mode, setMode, validateApiKeys } = useTradingMode();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingMode, setPendingMode] = useState<TradingMode | null>(null);

  const handleModePress = useCallback(
    (newMode: TradingMode) => {
      if (newMode === mode) return;

      if (newMode === 'live') {
        // Check if API keys are configured
        if (!validateApiKeys()) {
          Alert.alert(
            'API Keys Required',
            'Please configure your OANDA API keys below before switching to Live mode.',
            [{ text: 'OK' }]
          );
          return;
        }
        // Show confirmation modal for switching to live
        setPendingMode(newMode);
        setShowConfirmModal(true);
      } else {
        // Switching to paper mode doesn't need confirmation
        setMode(newMode);
        onModeChange?.(newMode);
      }
    },
    [mode, setMode, validateApiKeys, onModeChange]
  );

  const confirmModeSwitch = useCallback(async () => {
    if (pendingMode) {
      await setMode(pendingMode);
      onModeChange?.(pendingMode);
      setShowConfirmModal(false);
      setPendingMode(null);
    }
  }, [pendingMode, setMode, onModeChange]);

  const cancelModeSwitch = useCallback(() => {
    setShowConfirmModal(false);
    setPendingMode(null);
  }, []);

  return (
    <View style={styles.container}>
      {/* Paper Mode Banner */}
      {mode === 'paper' && (
        <View style={styles.paperBanner}>
          <Text style={styles.paperBannerText}>
            PAPER MODE - No real money at risk
          </Text>
        </View>
      )}

      {/* Live Mode Banner */}
      {mode === 'live' && (
        <View style={styles.liveBanner}>
          <Text style={styles.liveBannerText}>
            LIVE MODE - Real money trading active
          </Text>
        </View>
      )}

      {/* Segmented Control */}
      <View style={styles.segmentedControl}>
        <TouchableOpacity
          style={[
            styles.segment,
            mode === 'paper' && styles.segmentActivePaper,
          ]}
          onPress={() => handleModePress('paper')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.segmentText,
              mode === 'paper' && styles.segmentTextActivePaper,
            ]}
          >
            PAPER
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.segment,
            mode === 'live' && styles.segmentActiveLive,
          ]}
          onPress={() => handleModePress('live')}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.segmentText,
              mode === 'live' && styles.segmentTextActiveLive,
            ]}
          >
            LIVE
          </Text>
        </TouchableOpacity>
      </View>

      {/* Confirmation Modal for Live Mode */}
      <Modal
        visible={showConfirmModal}
        transparent
        animationType="fade"
        onRequestClose={cancelModeSwitch}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalIconContainer}>
              <Text style={styles.modalIcon}>!</Text>
            </View>
            <Text style={styles.modalTitle}>Switch to Live Trading?</Text>
            <Text style={styles.modalText}>
              You are about to enable live trading mode. This will execute real
              trades with real money using your connected OANDA account.
            </Text>
            <Text style={styles.modalWarning}>
              Please ensure you understand the risks involved.
            </Text>
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={styles.modalCancelButton}
                onPress={cancelModeSwitch}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalConfirmButton}
                onPress={confirmModeSwitch}
              >
                <Text style={styles.modalConfirmText}>ENABLE LIVE</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: spacing.lg,
  },
  paperBanner: {
    backgroundColor: colors.lpGreen + '20',
    borderWidth: 1,
    borderColor: colors.lpGreen,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  paperBannerText: {
    ...typography.labelMD,
    color: colors.lpGreen,
    textAlign: 'center',
  },
  liveBanner: {
    backgroundColor: colors.lpRed + '20',
    borderWidth: 1,
    borderColor: colors.lpRed,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  liveBannerText: {
    ...typography.labelMD,
    color: colors.lpRed,
    textAlign: 'center',
  },
  segmentedControl: {
    flexDirection: 'row',
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    padding: spacing.xs,
    gap: spacing.xs,
  },
  segment: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  segmentActivePaper: {
    backgroundColor: colors.lpGreen,
  },
  segmentActiveLive: {
    backgroundColor: colors.lpRed,
  },
  segmentText: {
    ...typography.labelLG,
    color: colors.textMuted,
  },
  segmentTextActivePaper: {
    color: colors.lpBlack,
  },
  segmentTextActiveLive: {
    color: colors.textPrimary,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.xl,
  },
  modalContent: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    width: '100%',
    borderWidth: 1,
    borderColor: colors.lpRed,
    alignItems: 'center',
  },
  modalIconContainer: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: colors.lpRed + '30',
    borderWidth: 2,
    borderColor: colors.lpRed,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  modalIcon: {
    ...typography.heroMD,
    color: colors.lpRed,
    fontWeight: 'bold',
  },
  modalTitle: {
    ...typography.h2,
    color: colors.lpRed,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  modalText: {
    ...typography.bodyLG,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  modalWarning: {
    ...typography.h4,
    color: colors.lpAmber,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: spacing.md,
    width: '100%',
  },
  modalCancelButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.textMuted,
    alignItems: 'center',
  },
  modalCancelText: {
    ...typography.labelLG,
    color: colors.textSecondary,
  },
  modalConfirmButton: {
    flex: 1,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.lpRed,
    alignItems: 'center',
  },
  modalConfirmText: {
    ...typography.labelLG,
    color: colors.textPrimary,
  },
});

export default TradingModeToggle;
