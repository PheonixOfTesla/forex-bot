import React from 'react';
import Svg, { Path, Defs, LinearGradient, Stop } from 'react-native-svg';

interface LightningIconProps {
  size?: number;
  color?: string;
  gradient?: boolean;
}

export const LightningIcon: React.FC<LightningIconProps> = ({
  size = 24,
  color = '#00d4ff',
  gradient = true,
}) => {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {gradient && (
        <Defs>
          <LinearGradient id="lightningGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%" stopColor="#00d4ff" />
            <Stop offset="100%" stopColor="#ffd700" />
          </LinearGradient>
        </Defs>
      )}
      <Path
        d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"
        fill={gradient ? "url(#lightningGrad)" : color}
        stroke={gradient ? "url(#lightningGrad)" : color}
        strokeWidth={1}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
};
