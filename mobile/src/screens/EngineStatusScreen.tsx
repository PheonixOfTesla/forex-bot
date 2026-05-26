import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, typography, spacing, borderRadius } from '../theme';
import { StatusBadge } from '../components';
import { useEngineStatus } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';

type ComponentStatus = 'active' | 'down' | 'degraded';

const statusColors: Record<ComponentStatus, string> = {
  active: colors.lpCyan,
  down: colors.lpRed,
  degraded: colors.lpAmber,
};

const statusLabels: Record<ComponentStatus, string> = {
  active: 'Active',
  down: 'Down',
  degraded: 'Degraded',
};

export const EngineStatusScreen: React.FC = () => {
  const { data, loading, refetch } = useEngineStatus();
  const { isConnected } = useWebSocket({
    onEngineStatus: () => refetch(),
  });

  const onRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  // Mock data for development
  const engineStatus = data || {
    status: 'LIVE' as const,
    uptime: 86400 * 7 + 3600 * 5 + 60 * 23, // 7d 5h 23m
    tradeCount: 234,
    components: [
      { name: 'WebSocket Server', status: 'active' as const, lastHeartbeat: new Date().toISOString() },
      { name: 'Feature Engine', status: 'active' as const, lastHeartbeat: new Date().toISOString() },
      { name: 'ML Classifier', status: 'active' as const, lastHeartbeat: new Date().toISOString() },
      { name: 'Risk Manager', status: 'active' as const, lastHeartbeat: new Date().toISOString() },
      { name: 'Order Executor', status: 'degraded' as const, lastHeartbeat: new Date().toISOString(), details: 'High latency detected' },
      { name: 'Logger', status: 'active' as const, lastHeartbeat: new Date().toISOString() },
    ],
  };

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    const parts: string[] = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);

    return parts.join(' ') || '0m';
  };

  const formatLastHeartbeat = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);

    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    return `${Math.floor(diffSec / 3600)}h ago`;
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
          <Text style={styles.title}>Engine Status</Text>
          <StatusBadge status={engineStatus.status} />
        </View>

        {/* Connection Status */}
        <View style={styles.connectionCard}>
          <View style={styles.connectionRow}>
            <View
              style={[
                styles.connectionDot,
                { backgroundColor: isConnected ? colors.lpCyan : colors.lpRed },
              ]}
            />
            <Text style={styles.connectionText}>
              {isConnected ? 'Real-time connected' : 'Disconnected'}
            </Text>
          </View>
        </View>

        {/* Components List */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>SYSTEM COMPONENTS</Text>
          <View style={styles.componentsList}>
            {engineStatus.components.map((component, index) => {
              const statusColor = statusColors[component.status];
              return (
                <View
                  key={index}
                  style={[
                    styles.componentRow,
                    { borderLeftColor: statusColor },
                  ]}
                >
                  <View style={styles.componentInfo}>
                    <Text style={styles.componentName}>{component.name}</Text>
                    {component.details && (
                      <Text style={styles.componentDetails}>
                        {component.details}
                      </Text>
                    )}
                    <Text style={styles.componentHeartbeat}>
                      Last heartbeat: {formatLastHeartbeat(component.lastHeartbeat)}
                    </Text>
                  </View>
                  <View style={styles.statusBadge}>
                    <View
                      style={[styles.statusDot, { backgroundColor: statusColor }]}
                    />
                    <Text style={[styles.statusText, { color: statusColor }]}>
                      {statusLabels[component.status]}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>
        </View>

        {/* Stats */}
        <View style={styles.statsRow}>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{formatUptime(engineStatus.uptime)}</Text>
            <Text style={styles.statLabel}>UPTIME</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{engineStatus.tradeCount}</Text>
            <Text style={styles.statLabel}>TOTAL TRADES</Text>
          </View>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xl,
  },
  title: {
    ...typography.h1,
    color: colors.textPrimary,
  },
  connectionCard: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.xl,
  },
  connectionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  connectionText: {
    ...typography.bodyMD,
    color: colors.textSecondary,
  },
  section: {
    marginBottom: spacing.xl,
  },
  sectionTitle: {
    ...typography.labelMD,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  componentsList: {
    gap: spacing.sm,
  },
  componentRow: {
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.md,
    borderLeftWidth: 3,
    padding: spacing.lg,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  componentInfo: {
    flex: 1,
    gap: 2,
  },
  componentName: {
    ...typography.bodyLG,
    color: colors.textPrimary,
    fontWeight: '600',
  },
  componentDetails: {
    ...typography.bodySM,
    color: colors.lpAmber,
  },
  componentHeartbeat: {
    ...typography.bodySM,
    color: colors.textMuted,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    ...typography.labelSM,
  },
  statsRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.lpSurface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
  },
  statValue: {
    ...typography.heroMD,
    color: colors.lpCyan,
  },
  statLabel: {
    ...typography.labelSM,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
});
