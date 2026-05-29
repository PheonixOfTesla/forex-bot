import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Pressable,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path, Circle, G } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import { usePredictions, usePredictionAccuracy } from '../hooks/useApi';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Types
interface Prediction {
  pair: string;
  timeframe: string;
  direction: 'UP' | 'DOWN';
  confidence: number;
  current_price: number;
  predicted_low: number;
  predicted_high: number;
  key_factors: string[];
  generated_at: string;
  valid_until: string;
}

interface AccuracyData {
  overall_accuracy: {
    '1h': number;
    '4h': number;
    '24h': number;
  };
  by_pair: Record<string, {
    '1h': { accuracy: number; total_predictions: number };
    '4h': { accuracy: number; total_predictions: number };
    '24h': { accuracy: number; total_predictions: number };
  }>;
}

// Icons
const TrendUpIcon = ({ size = 24, color = colors.lpGreen }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M23 6l-9.5 9.5-5-5L1 18"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M17 6h6v6"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const TrendDownIcon = ({ size = 24, color = colors.lpRed }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M23 18l-9.5-9.5-5 5L1 6"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M17 18h6v-6"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const ChartIcon = ({ size = 24, color = colors.lpCyan }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M3 3v18h18"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Path
      d="M18 9l-5 5-4-4-3 3"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

const TargetIcon = ({ size = 16, color = colors.textMuted }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={2} />
    <Circle cx="12" cy="12" r="6" stroke={color} strokeWidth={2} />
    <Circle cx="12" cy="12" r="2" fill={color} />
  </Svg>
);

// Filter Pills
const TIMEFRAMES = ['All', '1h', '4h', '24h'] as const;
const PAIRS = ['All', 'EUR/USD', 'GBP/USD', 'USD/JPY', 'BTC/USD', 'ETH/USD'] as const;

type TimeframeFilter = typeof TIMEFRAMES[number];
type PairFilter = typeof PAIRS[number];

export const PredictionsScreen: React.FC = () => {
  const [selectedTimeframe, setSelectedTimeframe] = useState<TimeframeFilter>('All');
  const [selectedPair, setSelectedPair] = useState<PairFilter>('All');

  const { data: predictionsData, loading, refetch } = usePredictions(
    selectedPair === 'All' ? undefined : selectedPair,
    selectedTimeframe === 'All' ? undefined : selectedTimeframe
  );
  const { data: accuracyData } = usePredictionAccuracy();

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const predictions: Prediction[] = predictionsData?.predictions ?? [];
  const accuracy: AccuracyData | null = accuracyData ?? null;

  const formatPrice = (price: number, pair: string): string => {
    if (pair.includes('JPY')) {
      return price.toFixed(2);
    }
    if (pair.includes('BTC') || pair.includes('ETH')) {
      return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return price.toFixed(5);
  };

  const getTimeRemaining = (validUntil: string): string => {
    const now = new Date();
    const expiry = new Date(validUntil);
    const diffMs = expiry.getTime() - now.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 0) return 'Expired';
    if (diffMins < 60) return `${diffMins}m`;
    return `${Math.floor(diffMins / 60)}h ${diffMins % 60}m`;
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={onRefresh}
            tintColor={colors.lpCyan}
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <ChartIcon size={28} color={colors.lpCyan} />
            <Text style={styles.title}>ML Predictions</Text>
          </View>
        </View>

        {/* Accuracy Stats */}
        {accuracy && (
          <View style={styles.accuracySection}>
            <Text style={styles.sectionTitle}>PREDICTION ACCURACY</Text>
            <View style={styles.accuracyCards}>
              <View style={styles.accuracyCard}>
                <Text style={styles.accuracyValue}>{accuracy.overall_accuracy['1h']}%</Text>
                <Text style={styles.accuracyLabel}>1H</Text>
              </View>
              <View style={styles.accuracyCard}>
                <Text style={styles.accuracyValue}>{accuracy.overall_accuracy['4h']}%</Text>
                <Text style={styles.accuracyLabel}>4H</Text>
              </View>
              <View style={styles.accuracyCard}>
                <Text style={styles.accuracyValue}>{accuracy.overall_accuracy['24h']}%</Text>
                <Text style={styles.accuracyLabel}>24H</Text>
              </View>
            </View>
          </View>
        )}

        {/* Filters */}
        <View style={styles.filtersSection}>
          <Text style={styles.filterLabel}>Timeframe</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.filterScroll}
            contentContainerStyle={styles.filterRow}
          >
            {TIMEFRAMES.map((tf) => (
              <Pressable
                key={tf}
                style={[
                  styles.filterPill,
                  selectedTimeframe === tf && styles.filterPillActive,
                ]}
                onPress={() => setSelectedTimeframe(tf)}
              >
                <Text
                  style={[
                    styles.filterPillText,
                    selectedTimeframe === tf && styles.filterPillTextActive,
                  ]}
                >
                  {tf}
                </Text>
              </Pressable>
            ))}
          </ScrollView>

          <Text style={[styles.filterLabel, { marginTop: spacing.md }]}>Pair</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.filterScroll}
            contentContainerStyle={styles.filterRow}
          >
            {PAIRS.map((pair) => (
              <Pressable
                key={pair}
                style={[
                  styles.filterPill,
                  selectedPair === pair && styles.filterPillActive,
                ]}
                onPress={() => setSelectedPair(pair)}
              >
                <Text
                  style={[
                    styles.filterPillText,
                    selectedPair === pair && styles.filterPillTextActive,
                  ]}
                >
                  {pair}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>

        {/* Predictions List */}
        <View style={styles.predictionsSection}>
          <Text style={styles.sectionTitle}>
            PREDICTIONS ({predictions.length})
          </Text>

          {predictions.length === 0 ? (
            <View style={styles.emptyState}>
              <TargetIcon size={48} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>No Predictions</Text>
              <Text style={styles.emptyText}>
                Adjust filters or pull to refresh
              </Text>
            </View>
          ) : (
            <View style={styles.predictionsList}>
              {predictions.map((prediction, index) => (
                <View key={`${prediction.pair}-${prediction.timeframe}-${index}`} style={styles.predictionCard}>
                  {/* Card Header */}
                  <View style={styles.cardHeader}>
                    <View style={styles.pairRow}>
                      <Text style={styles.pairText}>{prediction.pair}</Text>
                      <View style={styles.timeframeBadge}>
                        <Text style={styles.timeframeText}>{prediction.timeframe}</Text>
                      </View>
                    </View>
                    <View
                      style={[
                        styles.directionBadge,
                        {
                          backgroundColor:
                            prediction.direction === 'UP'
                              ? colors.lpGreen + '20'
                              : colors.lpRed + '20',
                        },
                      ]}
                    >
                      {prediction.direction === 'UP' ? (
                        <TrendUpIcon size={16} />
                      ) : (
                        <TrendDownIcon size={16} />
                      )}
                      <Text
                        style={[
                          styles.directionText,
                          {
                            color:
                              prediction.direction === 'UP'
                                ? colors.lpGreen
                                : colors.lpRed,
                          },
                        ]}
                      >
                        {prediction.direction}
                      </Text>
                    </View>
                  </View>

                  {/* Confidence Bar */}
                  <View style={styles.confidenceSection}>
                    <View style={styles.confidenceHeader}>
                      <Text style={styles.confidenceLabel}>Confidence</Text>
                      <Text style={styles.confidenceValue}>{prediction.confidence}%</Text>
                    </View>
                    <View style={styles.confidenceBarBg}>
                      <View
                        style={[
                          styles.confidenceBarFill,
                          {
                            width: `${prediction.confidence}%`,
                            backgroundColor:
                              prediction.confidence >= 80
                                ? colors.lpGreen
                                : prediction.confidence >= 65
                                ? colors.lpAmber
                                : colors.lpRed,
                          },
                        ]}
                      />
                    </View>
                  </View>

                  {/* Price Range */}
                  <View style={styles.priceRangeSection}>
                    <Text style={styles.priceRangeTitle}>Predicted Range</Text>
                    <View style={styles.priceRangeRow}>
                      <View style={styles.priceItem}>
                        <Text style={styles.priceLabel}>Low</Text>
                        <Text style={styles.priceValue}>
                          {formatPrice(prediction.predicted_low, prediction.pair)}
                        </Text>
                      </View>
                      <View style={styles.priceArrow}>
                        <Text style={styles.priceArrowText}>-</Text>
                      </View>
                      <View style={styles.priceItem}>
                        <Text style={styles.priceLabel}>High</Text>
                        <Text style={styles.priceValue}>
                          {formatPrice(prediction.predicted_high, prediction.pair)}
                        </Text>
                      </View>
                    </View>
                    <Text style={styles.currentPrice}>
                      Current: {formatPrice(prediction.current_price, prediction.pair)}
                    </Text>
                  </View>

                  {/* Key Factors */}
                  <View style={styles.factorsSection}>
                    <Text style={styles.factorsTitle}>Key Factors</Text>
                    {prediction.key_factors.map((factor, idx) => (
                      <View key={idx} style={styles.factorRow}>
                        <View style={styles.factorBullet} />
                        <Text style={styles.factorText}>{factor}</Text>
                      </View>
                    ))}
                  </View>

                  {/* Footer */}
                  <View style={styles.cardFooter}>
                    <Text style={styles.validUntil}>
                      Valid for {getTimeRemaining(prediction.valid_until)}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.lpBlack,
  },
  scrollView: {
    flex: 1,
  },
  content: {
    padding: spacing.xl,
    paddingBottom: 100,
  },
  header: {
    marginBottom: spacing.xl,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },

  // Accuracy Section
  accuracySection: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  accuracyCards: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  accuracyCard: {
    flex: 1,
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
  },
  accuracyValue: {
    ...typography.heroMD,
    color: colors.lpCyan,
    fontWeight: '700',
  },
  accuracyLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },

  // Filters
  filtersSection: {
    marginBottom: spacing.xl,
  },
  filterLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  filterScroll: {
    marginHorizontal: -spacing.xl,
    paddingHorizontal: spacing.xl,
  },
  filterRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  filterPill: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    backgroundColor: colors.lpSurface,
    borderWidth: 1,
    borderColor: colors.borderDark,
  },
  filterPillActive: {
    backgroundColor: colors.lpCyan + '20',
    borderColor: colors.lpCyan,
  },
  filterPillText: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  filterPillTextActive: {
    color: colors.lpCyan,
    fontWeight: '600',
  },

  // Predictions
  predictionsSection: {
    marginBottom: spacing.xl,
  },
  predictionsList: {
    gap: spacing.md,
  },
  predictionCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    padding: spacing.lg,
    borderLeftWidth: 3,
    borderLeftColor: colors.lpCyan,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  pairRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  pairText: {
    ...typography.h3,
    color: colors.textPrimary,
  },
  timeframeBadge: {
    backgroundColor: colors.borderDark,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  timeframeText: {
    ...typography.labelSM,
    color: colors.textSecondary,
  },
  directionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
  },
  directionText: {
    ...typography.labelMD,
    fontWeight: '700',
  },

  // Confidence
  confidenceSection: {
    marginBottom: spacing.lg,
  },
  confidenceHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  confidenceLabel: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  confidenceValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  confidenceBarBg: {
    height: 6,
    backgroundColor: colors.borderDark,
    borderRadius: 3,
    overflow: 'hidden',
  },
  confidenceBarFill: {
    height: '100%',
    borderRadius: 3,
  },

  // Price Range
  priceRangeSection: {
    backgroundColor: colors.lpBlack,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  priceRangeTitle: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  priceRangeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.lg,
  },
  priceItem: {
    alignItems: 'center',
  },
  priceLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
  },
  priceValue: {
    ...typography.h4,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  priceArrow: {
    paddingHorizontal: spacing.md,
  },
  priceArrowText: {
    ...typography.h3,
    color: colors.textMuted,
  },
  currentPrice: {
    ...typography.bodySM,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },

  // Factors
  factorsSection: {
    marginBottom: spacing.md,
  },
  factorsTitle: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: spacing.sm,
  },
  factorRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  factorBullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.lpCyan,
    marginTop: 6,
  },
  factorText: {
    ...typography.bodySM,
    color: colors.textSecondary,
    flex: 1,
  },

  // Footer
  cardFooter: {
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    paddingTop: spacing.sm,
  },
  validUntil: {
    ...typography.bodySM,
    color: colors.textMuted,
    textAlign: 'center',
  },

  // Empty State
  emptyState: {
    alignItems: 'center',
    paddingVertical: spacing.xxxl,
  },
  emptyTitle: {
    ...typography.h3,
    color: colors.textPrimary,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  emptyText: {
    ...typography.bodyMD,
    color: colors.textMuted,
    textAlign: 'center',
  },
});
