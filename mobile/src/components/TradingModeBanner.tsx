import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  Alert,
} from 'react-native';
import Svg, { Path, Circle, G } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import { PrimaryButton, GhostButton } from './index';

type TradingMode = 'paper' | 'live';

interface TradingModeBannerProps {
  mode: TradingMode;
  onModeChange?: (newMode: TradingMode) => void;
}

// Icons
const AlertIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M12 9v4M12 17h.01"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const TestTubeIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M9 3h6M12 3v12.5M12 15.5L7.5 20a2.12 2.12 0 103 3L16.5 17M12 8h2"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const BoltIcon = ({ color, size }: { color: string; size: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

export const TradingModeBanner: React.FC<TradingModeBannerProps> = ({
  mode,
  onModeChange,
}) => {
  const [showModal, setShowModal] = useState(false);
  const [pendingMode, setPendingMode] = useState<TradingMode | null>(null);

  const isPaper = mode === 'paper';

  const handlePress = () => {
    setShowModal(true);
  };

  const handleModeSelect = (selectedMode: TradingMode) => {
    if (selectedMode === mode) {
      setShowModal(false);
      return;
    }

    if (selectedMode === 'live') {
      setPendingMode('live');
    } else {
      // Switching to paper mode doesn't need confirmation
      onModeChange?.('paper');
      setShowModal(false);
    }
  };

  const confirmLiveMode = () => {
    onModeChange?.('live');
    setPendingMode(null);
    setShowModal(false);
  };

  const cancelLiveMode = () => {
    setPendingMode(null);
  };

  return (
    <>
      <TouchableOpacity
        style={[
          styles.banner,
          isPaper ? styles.paperBanner : styles.liveBanner,
        ]}
        onPress={handlePress}
        activeOpacity={0.8}
      >
        <View style={styles.bannerContent}>
          {isPaper ? (
            <TestTubeIcon color={colors.lpGreen} size={16} />
          ) : (
            <BoltIcon color={colors.lpRed} size={16} />
          )}
          <Text style={[styles.bannerText, isPaper ? styles.paperText : styles.liveText]}>
            {isPaper ? 'PAPER TRADING' : 'LIVE'}
          </Text>
        </View>
        <Text style={styles.tapHint}>Tap to change</Text>
      </TouchableOpacity>

      {/* Mode Switch Modal */}
      <Modal
        visible={showModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            {pendingMode === 'live' ? (
              // Live Mode Confirmation
              <>
                <View style={styles.warningIcon}>
                  <AlertIcon color={colors.lpRed} size={32} />
                </View>
                <Text style={styles.modalTitle}>Switch to Live Trading?</Text>
                <Text style={styles.modalText}>
                  You are about to enable live trading mode. Real money will be used for all trades.
                </Text>
                <View style={styles.warningBox}>
                  <Text style={styles.warningTitle}>Warning</Text>
                  <Text style={styles.warningText}>
                    Trading involves substantial risk of loss. Only trade with money you can afford to lose.
                  </Text>
                </View>
                <View style={styles.modalButtons}>
                  <GhostButton
                    title="CANCEL"
                    onPress={cancelLiveMode}
                    style={styles.modalButton}
                    size="lg"
                  />
                  <PrimaryButton
                    title="ENABLE LIVE"
                    onPress={confirmLiveMode}
                    color={colors.lpRed}
                    style={styles.modalButton}
                    size="lg"
                  />
                </View>
              </>
            ) : (
              // Mode Selection
              <>
                <Text style={styles.modalTitle}>Trading Mode</Text>
                <Text style={styles.modalSubtitle}>
                  Select your preferred trading mode
                </Text>

                <TouchableOpacity
                  style={[
                    styles.modeOption,
                    mode === 'paper' && styles.modeOptionActive,
                  ]}
                  onPress={() => handleModeSelect('paper')}
                >
                  <View style={[styles.modeIconContainer, { backgroundColor: colors.lpGreen + '20' }]}>
                    <TestTubeIcon color={colors.lpGreen} size={24} />
                  </View>
                  <View style={styles.modeInfo}>
                    <Text style={styles.modeName}>Paper Trading</Text>
                    <Text style={styles.modeDescription}>
                      Practice with virtual money. No real funds at risk.
                    </Text>
                  </View>
                  <View style={[styles.radioOuter, mode === 'paper' && styles.radioOuterActive]}>
                    {mode === 'paper' && <View style={styles.radioInner} />}
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[
                    styles.modeOption,
                    mode === 'live' && styles.modeOptionActive,
                  ]}
                  onPress={() => handleModeSelect('live')}
                >
                  <View style={[styles.modeIconContainer, { backgroundColor: colors.lpRed + '20' }]}>
                    <BoltIcon color={colors.lpRed} size={24} />
                  </View>
                  <View style={styles.modeInfo}>
                    <Text style={styles.modeName}>Live Trading</Text>
                    <Text style={styles.modeDescription}>
                      Trade with real money. Real profits and losses.
                    </Text>
                  </View>
                  <View style={[styles.radioOuter, mode === 'live' && styles.radioOuterLive]}>
                    {mode === 'live' && <View style={[styles.radioInner, { backgroundColor: colors.lpRed }]} />}
                  </View>
                </TouchableOpacity>

                <GhostButton
                  title="CLOSE"
                  onPress={() => setShowModal(false)}
                  style={styles.closeButton}
                  size="lg"
                />
              </>
            )}
          </View>
        </View>
      </Modal>
    </>
  );
};

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  paperBanner: {
    backgroundColor: colors.lpGreen + '15',
    borderBottomWidth: 1,
    borderBottomColor: colors.lpGreen + '30',
  },
  liveBanner: {
    backgroundColor: colors.lpRed + '10',
    borderBottomWidth: 1,
    borderBottomColor: colors.lpRed + '30',
  },
  bannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  bannerText: {
    ...typography.labelMD,
    fontWeight: '700',
    letterSpacing: 1,
  },
  paperText: {
    color: colors.lpGreen,
  },
  liveText: {
    color: colors.lpRed,
  },
  tapHint: {
    ...typography.bodySM,
    color: colors.textMuted,
    fontSize: 11,
  },

  // Modal
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
    maxWidth: 400,
  },
  modalTitle: {
    ...typography.h2,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.sm,
  },
  modalSubtitle: {
    ...typography.bodyMD,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.xl,
  },
  modalText: {
    ...typography.bodyMD,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },

  // Warning
  warningIcon: {
    alignItems: 'center',
    marginBottom: spacing.lg,
  },
  warningBox: {
    backgroundColor: colors.lpRed + '15',
    borderRadius: borderRadius.md,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    borderLeftWidth: 3,
    borderLeftColor: colors.lpRed,
  },
  warningTitle: {
    ...typography.labelMD,
    color: colors.lpRed,
    marginBottom: spacing.xs,
  },
  warningText: {
    ...typography.bodySM,
    color: colors.textSecondary,
    lineHeight: 18,
  },

  // Mode Options
  modeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  modeOptionActive: {
    borderColor: colors.lpCyan,
  },
  modeIconContainer: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  modeInfo: {
    flex: 1,
  },
  modeName: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  modeDescription: {
    ...typography.bodySM,
    color: colors.textMuted,
    marginTop: 2,
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: colors.textMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterActive: {
    borderColor: colors.lpCyan,
  },
  radioOuterLive: {
    borderColor: colors.lpRed,
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.lpCyan,
  },

  // Buttons
  modalButtons: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  modalButton: {
    flex: 1,
  },
  closeButton: {
    marginTop: spacing.md,
  },
});

export default TradingModeBanner;
