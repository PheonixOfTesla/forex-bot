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
import Svg, { Path, Circle, G, Rect, Line } from 'react-native-svg';
import { colors, typography, spacing, borderRadius } from '../theme';
import {
  useMarketSentiment,
  useTechnicalIndicators,
  useAIInsights,
  useDetectedPatterns,
} from '../hooks/useApi';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Types
interface SentimentData {
  fear_greed_index: number;
  fear_greed_label: string;
  pair_sentiments: Record<string, {
    bullish: number;
    bearish: number;
    neutral: number;
    overall: string;
  }>;
}

interface Indicator {
  pair: string;
  rsi: { value: number; signal: string };
  macd: { value: number; histogram: number; trend: string };
  moving_averages: { trend: string };
  bollinger_bands: { position: number; squeeze: boolean };
  adx: { value: number; trend_strength: string };
  overall_bias: string;
}

interface Insight {
  id: string;
  title: string;
  content: string;
  category: string;
  priority: string;
  pairs_affected: string[];
  generated_at: string;
}

interface Pattern {
  id: string;
  pair: string;
  pattern_name: string;
  pattern_type: string;
  direction: string;
  timeframe: string;
  completion_percentage: number;
  reliability_score: number;
  notes: string;
}

// Icons
const BrainIcon = ({ size = 24, color = colors.lpPurple }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M12 4.5C7.5 4.5 4.5 7.5 4.5 12s3 7.5 7.5 7.5 7.5-3 7.5-7.5S16.5 4.5 12 4.5z"
      stroke={color}
      strokeWidth={2}
    />
    <Path
      d="M12 4.5V12M12 12l5.25 3.03M12 12l-5.25 3.03"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
    />
  </Svg>
);

const GaugeIcon = ({ size = 24, color = colors.lpAmber }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"
      stroke={color}
      strokeWidth={2}
    />
    <Path
      d="M12 6v6l4 2"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
    />
  </Svg>
);

const ChartBarIcon = ({ size = 24, color = colors.lpCyan }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Rect x="3" y="12" width="4" height="9" rx="1" stroke={color} strokeWidth={2} />
    <Rect x="10" y="8" width="4" height="13" rx="1" stroke={color} strokeWidth={2} />
    <Rect x="17" y="4" width="4" height="17" rx="1" stroke={color} strokeWidth={2} />
  </Svg>
);

const PatternIcon = ({ size = 24, color = colors.lpGold }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M2 12l5-5 4 4 5-5 6 6"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <Circle cx="7" cy="7" r="2" stroke={color} strokeWidth={2} />
    <Circle cx="17" cy="6" r="2" stroke={color} strokeWidth={2} />
  </Svg>
);

const LightbulbIcon = ({ size = 20, color = colors.lpGold }: { size?: number; color?: string }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <Path
      d="M9 21h6M12 3a6 6 0 016 6c0 2.22-1.21 4.16-3 5.2V17a1 1 0 01-1 1h-4a1 1 0 01-1-1v-2.8C7.21 13.16 6 11.22 6 9a6 6 0 016-6z"
      stroke={color}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

// Fear & Greed Gauge Component
const FearGreedGauge: React.FC<{ value: number; label: string }> = ({ value, label }) => {
  const getColor = () => {
    if (value < 25) return colors.lpRed;
    if (value < 45) return '#f97316'; // Orange
    if (value < 55) return colors.lpAmber;
    if (value < 75) return '#84cc16'; // Lime
    return colors.lpGreen;
  };

  return (
    <View style={styles.gaugeContainer}>
      <View style={styles.gaugeCircle}>
        <Text style={[styles.gaugeValue, { color: getColor() }]}>{Math.round(value)}</Text>
        <Text style={styles.gaugeLabel}>{label}</Text>
      </View>
      <View style={styles.gaugeLegend}>
        <View style={styles.gaugeLegendItem}>
          <View style={[styles.gaugeLegendDot, { backgroundColor: colors.lpRed }]} />
          <Text style={styles.gaugeLegendText}>Fear</Text>
        </View>
        <View style={styles.gaugeLegendItem}>
          <View style={[styles.gaugeLegendDot, { backgroundColor: colors.lpAmber }]} />
          <Text style={styles.gaugeLegendText}>Neutral</Text>
        </View>
        <View style={styles.gaugeLegendItem}>
          <View style={[styles.gaugeLegendDot, { backgroundColor: colors.lpGreen }]} />
          <Text style={styles.gaugeLegendText}>Greed</Text>
        </View>
      </View>
    </View>
  );
};

// Indicator Bar Component
const IndicatorBar: React.FC<{
  label: string;
  value: number;
  maxValue?: number;
  signal?: string;
  color?: string;
}> = ({ label, value, maxValue = 100, signal, color = colors.lpCyan }) => {
  const percentage = Math.min((value / maxValue) * 100, 100);

  return (
    <View style={styles.indicatorBarContainer}>
      <View style={styles.indicatorBarHeader}>
        <Text style={styles.indicatorBarLabel}>{label}</Text>
        <Text style={styles.indicatorBarValue}>{value.toFixed(1)}</Text>
      </View>
      <View style={styles.indicatorBarBg}>
        <View
          style={[
            styles.indicatorBarFill,
            { width: `${percentage}%`, backgroundColor: color },
          ]}
        />
      </View>
      {signal && (
        <Text
          style={[
            styles.indicatorBarSignal,
            {
              color:
                signal === 'oversold' || signal === 'bullish'
                  ? colors.lpGreen
                  : signal === 'overbought' || signal === 'bearish'
                  ? colors.lpRed
                  : colors.textMuted,
            },
          ]}
        >
          {signal.toUpperCase()}
        </Text>
      )}
    </View>
  );
};

export const IntelligenceScreen: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'sentiment' | 'indicators' | 'insights' | 'patterns'>('sentiment');

  const { data: sentimentData, loading: sentimentLoading, refetch: refetchSentiment } = useMarketSentiment();
  const { data: indicatorsData, loading: indicatorsLoading, refetch: refetchIndicators } = useTechnicalIndicators();
  const { data: insightsData, loading: insightsLoading, refetch: refetchInsights } = useAIInsights();
  const { data: patternsData, loading: patternsLoading, refetch: refetchPatterns } = useDetectedPatterns();

  const loading = sentimentLoading || indicatorsLoading || insightsLoading || patternsLoading;

  const onRefresh = useCallback(() => {
    refetchSentiment();
    refetchIndicators();
    refetchInsights();
    refetchPatterns();
  }, [refetchSentiment, refetchIndicators, refetchInsights, refetchPatterns]);

  const sentiment: SentimentData | null = sentimentData ?? null;
  const indicators: Indicator[] = indicatorsData?.indicators ?? [];
  const insights: Insight[] = insightsData?.insights ?? [];
  const patterns: Pattern[] = patternsData?.patterns ?? [];

  const TABS = [
    { key: 'sentiment', label: 'Sentiment', icon: GaugeIcon },
    { key: 'indicators', label: 'Indicators', icon: ChartBarIcon },
    { key: 'insights', label: 'AI Insights', icon: BrainIcon },
    { key: 'patterns', label: 'Patterns', icon: PatternIcon },
  ] as const;

  const renderSentimentTab = () => (
    <View style={styles.tabContent}>
      {sentiment && (
        <>
          {/* Fear & Greed Gauge */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Fear & Greed Index</Text>
            <FearGreedGauge
              value={sentiment.fear_greed_index}
              label={sentiment.fear_greed_label}
            />
          </View>

          {/* Pair Sentiments */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Pair Sentiment</Text>
            <View style={styles.pairSentimentList}>
              {Object.entries(sentiment.pair_sentiments).map(([pair, data]) => (
                <View key={pair} style={styles.pairSentimentItem}>
                  <Text style={styles.pairSentimentPair}>{pair}</Text>
                  <View style={styles.sentimentBar}>
                    <View
                      style={[
                        styles.sentimentBarSection,
                        { width: `${data.bullish}%`, backgroundColor: colors.lpGreen },
                      ]}
                    />
                    <View
                      style={[
                        styles.sentimentBarSection,
                        { width: `${data.neutral}%`, backgroundColor: colors.textMuted },
                      ]}
                    />
                    <View
                      style={[
                        styles.sentimentBarSection,
                        { width: `${data.bearish}%`, backgroundColor: colors.lpRed },
                      ]}
                    />
                  </View>
                  <Text
                    style={[
                      styles.pairSentimentOverall,
                      {
                        color:
                          data.overall === 'bullish'
                            ? colors.lpGreen
                            : data.overall === 'bearish'
                            ? colors.lpRed
                            : colors.textMuted,
                      },
                    ]}
                  >
                    {data.overall.toUpperCase()}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        </>
      )}
    </View>
  );

  const renderIndicatorsTab = () => (
    <View style={styles.tabContent}>
      {indicators.map((indicator) => (
        <View key={indicator.pair} style={styles.card}>
          <View style={styles.indicatorHeader}>
            <Text style={styles.cardTitle}>{indicator.pair}</Text>
            <View
              style={[
                styles.biasBadge,
                {
                  backgroundColor:
                    indicator.overall_bias === 'bullish'
                      ? colors.lpGreen + '20'
                      : indicator.overall_bias === 'bearish'
                      ? colors.lpRed + '20'
                      : colors.textMuted + '20',
                },
              ]}
            >
              <Text
                style={[
                  styles.biasText,
                  {
                    color:
                      indicator.overall_bias === 'bullish'
                        ? colors.lpGreen
                        : indicator.overall_bias === 'bearish'
                        ? colors.lpRed
                        : colors.textMuted,
                  },
                ]}
              >
                {indicator.overall_bias.toUpperCase()}
              </Text>
            </View>
          </View>

          <View style={styles.indicatorsGrid}>
            <IndicatorBar
              label="RSI"
              value={indicator.rsi.value}
              signal={indicator.rsi.signal}
              color={
                indicator.rsi.signal === 'oversold'
                  ? colors.lpGreen
                  : indicator.rsi.signal === 'overbought'
                  ? colors.lpRed
                  : colors.lpCyan
              }
            />
            <IndicatorBar
              label="ADX"
              value={indicator.adx.value}
              signal={indicator.adx.trend_strength}
              color={colors.lpPurple}
            />
          </View>

          <View style={styles.indicatorDetails}>
            <View style={styles.indicatorDetailItem}>
              <Text style={styles.indicatorDetailLabel}>MACD</Text>
              <Text
                style={[
                  styles.indicatorDetailValue,
                  {
                    color:
                      indicator.macd.trend === 'bullish'
                        ? colors.lpGreen
                        : colors.lpRed,
                  },
                ]}
              >
                {indicator.macd.trend.toUpperCase()}
              </Text>
            </View>
            <View style={styles.indicatorDetailItem}>
              <Text style={styles.indicatorDetailLabel}>MA Trend</Text>
              <Text
                style={[
                  styles.indicatorDetailValue,
                  {
                    color:
                      indicator.moving_averages.trend === 'bullish'
                        ? colors.lpGreen
                        : colors.lpRed,
                  },
                ]}
              >
                {indicator.moving_averages.trend.toUpperCase()}
              </Text>
            </View>
            <View style={styles.indicatorDetailItem}>
              <Text style={styles.indicatorDetailLabel}>BB Squeeze</Text>
              <Text
                style={[
                  styles.indicatorDetailValue,
                  {
                    color: indicator.bollinger_bands.squeeze
                      ? colors.lpAmber
                      : colors.textMuted,
                  },
                ]}
              >
                {indicator.bollinger_bands.squeeze ? 'YES' : 'NO'}
              </Text>
            </View>
          </View>
        </View>
      ))}
    </View>
  );

  const renderInsightsTab = () => (
    <View style={styles.tabContent}>
      <View style={styles.insightsHeader}>
        <LightbulbIcon size={24} />
        <Text style={styles.insightsHeaderText}>AI-Generated Market Analysis</Text>
      </View>

      {insights.map((insight) => (
        <View key={insight.id} style={styles.insightCard}>
          <View style={styles.insightHeader}>
            <View
              style={[
                styles.priorityBadge,
                {
                  backgroundColor:
                    insight.priority === 'high'
                      ? colors.lpRed + '20'
                      : insight.priority === 'medium'
                      ? colors.lpAmber + '20'
                      : colors.textMuted + '20',
                },
              ]}
            >
              <Text
                style={[
                  styles.priorityText,
                  {
                    color:
                      insight.priority === 'high'
                        ? colors.lpRed
                        : insight.priority === 'medium'
                        ? colors.lpAmber
                        : colors.textMuted,
                  },
                ]}
              >
                {insight.priority.toUpperCase()}
              </Text>
            </View>
            <Text style={styles.insightCategory}>{insight.category}</Text>
          </View>
          <Text style={styles.insightTitle}>{insight.title}</Text>
          <Text style={styles.insightContent}>{insight.content}</Text>
          <View style={styles.insightFooter}>
            <View style={styles.affectedPairs}>
              {insight.pairs_affected.map((pair) => (
                <View key={pair} style={styles.affectedPairBadge}>
                  <Text style={styles.affectedPairText}>{pair}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
      ))}
    </View>
  );

  const renderPatternsTab = () => (
    <View style={styles.tabContent}>
      {patterns.length === 0 ? (
        <View style={styles.emptyState}>
          <PatternIcon size={48} color={colors.textMuted} />
          <Text style={styles.emptyTitle}>No Patterns Detected</Text>
          <Text style={styles.emptyText}>Pull to refresh or check back later</Text>
        </View>
      ) : (
        patterns.map((pattern) => (
          <View key={pattern.id} style={styles.patternCard}>
            <View style={styles.patternHeader}>
              <Text style={styles.patternPair}>{pattern.pair}</Text>
              <View style={styles.patternTimeframe}>
                <Text style={styles.patternTimeframeText}>{pattern.timeframe}</Text>
              </View>
            </View>

            <View style={styles.patternMain}>
              <Text style={styles.patternName}>{pattern.pattern_name}</Text>
              <View
                style={[
                  styles.patternDirection,
                  {
                    backgroundColor:
                      pattern.direction === 'bullish'
                        ? colors.lpGreen + '20'
                        : colors.lpRed + '20',
                  },
                ]}
              >
                <Text
                  style={[
                    styles.patternDirectionText,
                    {
                      color:
                        pattern.direction === 'bullish'
                          ? colors.lpGreen
                          : colors.lpRed,
                    },
                  ]}
                >
                  {pattern.direction.toUpperCase()}
                </Text>
              </View>
            </View>

            <View style={styles.patternStats}>
              <View style={styles.patternStat}>
                <Text style={styles.patternStatLabel}>Completion</Text>
                <Text style={styles.patternStatValue}>{pattern.completion_percentage}%</Text>
                <View style={styles.completionBar}>
                  <View
                    style={[
                      styles.completionBarFill,
                      { width: `${pattern.completion_percentage}%` },
                    ]}
                  />
                </View>
              </View>
              <View style={styles.patternStat}>
                <Text style={styles.patternStatLabel}>Reliability</Text>
                <Text style={styles.patternStatValue}>{pattern.reliability_score}%</Text>
              </View>
              <View style={styles.patternStat}>
                <Text style={styles.patternStatLabel}>Type</Text>
                <Text style={styles.patternStatValue}>{pattern.pattern_type}</Text>
              </View>
            </View>

            <Text style={styles.patternNotes}>{pattern.notes}</Text>
          </View>
        ))
      )}
    </View>
  );

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
            <BrainIcon size={28} color={colors.lpPurple} />
            <Text style={styles.title}>Market Intelligence</Text>
          </View>
        </View>

        {/* Tabs */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.tabsScroll}
          contentContainerStyle={styles.tabsContainer}
        >
          {TABS.map((tab) => {
            const IconComponent = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <Pressable
                key={tab.key}
                style={[styles.tab, isActive && styles.tabActive]}
                onPress={() => setActiveTab(tab.key as typeof activeTab)}
              >
                <IconComponent
                  size={20}
                  color={isActive ? colors.lpCyan : colors.textMuted}
                />
                <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {/* Tab Content */}
        {activeTab === 'sentiment' && renderSentimentTab()}
        {activeTab === 'indicators' && renderIndicatorsTab()}
        {activeTab === 'insights' && renderInsightsTab()}
        {activeTab === 'patterns' && renderPatternsTab()}
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
    marginBottom: spacing.lg,
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

  // Tabs
  tabsScroll: {
    marginHorizontal: -spacing.xl,
    marginBottom: spacing.xl,
  },
  tabsContainer: {
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
    flexDirection: 'row',
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.lpSurface,
    borderWidth: 1,
    borderColor: colors.borderDark,
  },
  tabActive: {
    backgroundColor: colors.lpCyan + '15',
    borderColor: colors.lpCyan,
  },
  tabText: {
    ...typography.bodyMD,
    color: colors.textMuted,
  },
  tabTextActive: {
    color: colors.lpCyan,
    fontWeight: '600',
  },

  // Tab Content
  tabContent: {
    gap: spacing.md,
  },

  // Cards
  card: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.xl,
    padding: spacing.lg,
  },
  cardTitle: {
    ...typography.h4,
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },

  // Fear & Greed Gauge
  gaugeContainer: {
    alignItems: 'center',
    paddingVertical: spacing.lg,
  },
  gaugeCircle: {
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: colors.lpBlack,
    borderWidth: 4,
    borderColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gaugeValue: {
    ...typography.heroLG,
    fontWeight: '700',
  },
  gaugeLabel: {
    ...typography.bodySM,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  gaugeLegend: {
    flexDirection: 'row',
    gap: spacing.xl,
    marginTop: spacing.lg,
  },
  gaugeLegendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  gaugeLegendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  gaugeLegendText: {
    ...typography.bodySM,
    color: colors.textMuted,
  },

  // Pair Sentiments
  pairSentimentList: {
    gap: spacing.md,
  },
  pairSentimentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  pairSentimentPair: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    width: 70,
  },
  sentimentBar: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    flexDirection: 'row',
    overflow: 'hidden',
    backgroundColor: colors.borderDark,
  },
  sentimentBarSection: {
    height: '100%',
  },
  pairSentimentOverall: {
    ...typography.labelSM,
    width: 60,
    textAlign: 'right',
  },

  // Indicators
  indicatorHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  biasBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
  },
  biasText: {
    ...typography.labelSM,
    fontWeight: '600',
  },
  indicatorsGrid: {
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  indicatorBarContainer: {
    marginBottom: spacing.sm,
  },
  indicatorBarHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  indicatorBarLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
  },
  indicatorBarValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  indicatorBarBg: {
    height: 6,
    backgroundColor: colors.borderDark,
    borderRadius: 3,
    overflow: 'hidden',
  },
  indicatorBarFill: {
    height: '100%',
    borderRadius: 3,
  },
  indicatorBarSignal: {
    ...typography.labelSM,
    marginTop: 2,
  },
  indicatorDetails: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    paddingTop: spacing.md,
    gap: spacing.lg,
  },
  indicatorDetailItem: {
    flex: 1,
    alignItems: 'center',
  },
  indicatorDetailLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: 2,
  },
  indicatorDetailValue: {
    ...typography.bodyMD,
    fontWeight: '600',
  },

  // Insights
  insightsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderDark,
  },
  insightsHeaderText: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  insightCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    borderLeftWidth: 3,
    borderLeftColor: colors.lpPurple,
  },
  insightHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  priorityBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  priorityText: {
    ...typography.labelSM,
    fontWeight: '600',
  },
  insightCategory: {
    ...typography.labelSM,
    color: colors.textMuted,
    textTransform: 'capitalize',
  },
  insightTitle: {
    ...typography.h4,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  insightContent: {
    ...typography.bodyMD,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  insightFooter: {
    borderTopWidth: 1,
    borderTopColor: colors.borderDark,
    paddingTop: spacing.sm,
  },
  affectedPairs: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  affectedPairBadge: {
    backgroundColor: colors.borderDark,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  affectedPairText: {
    ...typography.labelSM,
    color: colors.textSecondary,
  },

  // Patterns
  patternCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
  },
  patternHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  patternPair: {
    ...typography.h4,
    color: colors.textPrimary,
  },
  patternTimeframe: {
    backgroundColor: colors.borderDark,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  patternTimeframeText: {
    ...typography.labelSM,
    color: colors.textSecondary,
  },
  patternMain: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  patternName: {
    ...typography.h3,
    color: colors.lpGold,
  },
  patternDirection: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.md,
  },
  patternDirectionText: {
    ...typography.labelSM,
    fontWeight: '600',
  },
  patternStats: {
    flexDirection: 'row',
    gap: spacing.lg,
    marginBottom: spacing.md,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.borderDark,
  },
  patternStat: {
    flex: 1,
  },
  patternStatLabel: {
    ...typography.labelSM,
    color: colors.textMuted,
    marginBottom: 2,
  },
  patternStatValue: {
    ...typography.bodyMD,
    color: colors.textPrimary,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  completionBar: {
    height: 4,
    backgroundColor: colors.borderDark,
    borderRadius: 2,
    marginTop: spacing.xs,
    overflow: 'hidden',
  },
  completionBarFill: {
    height: '100%',
    backgroundColor: colors.lpCyan,
    borderRadius: 2,
  },
  patternNotes: {
    ...typography.bodySM,
    color: colors.textMuted,
    fontStyle: 'italic',
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
