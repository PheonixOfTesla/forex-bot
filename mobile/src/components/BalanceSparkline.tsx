import React from 'react';
import { View, StyleSheet } from 'react-native';
import Svg, { Path, Defs, LinearGradient, Stop } from 'react-native-svg';
import { colors } from '../theme';

interface BalanceSparklineProps {
  data: number[];
  width: number;
  height: number;
  color?: string;
}

export const BalanceSparkline: React.FC<BalanceSparklineProps> = ({
  data,
  width,
  height,
  color = colors.lpCyan,
}) => {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height * 0.8 - height * 0.1;
    return { x, y };
  });

  const pathData = points
    .map((point, index) => {
      if (index === 0) return `M ${point.x} ${point.y}`;
      const prev = points[index - 1];
      const cp1x = prev.x + (point.x - prev.x) / 2;
      const cp1y = prev.y;
      const cp2x = prev.x + (point.x - prev.x) / 2;
      const cp2y = point.y;
      return `C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${point.x} ${point.y}`;
    })
    .join(' ');

  const areaData = `${pathData} L ${width} ${height} L 0 ${height} Z`;

  return (
    <View style={[styles.container, { width, height }]}>
      <Svg width={width} height={height}>
        <Defs>
          <LinearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <Stop offset="100%" stopColor={color} stopOpacity={0} />
          </LinearGradient>
        </Defs>
        <Path d={areaData} fill="url(#areaGradient)" />
        <Path
          d={pathData}
          stroke={color}
          strokeWidth={2}
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </Svg>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    overflow: 'hidden',
  },
});
