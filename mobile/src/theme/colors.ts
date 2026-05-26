/**
 * Lightning Pass Color Tokens
 * Dark theme with cyan/gold/purple accents
 */

export const colors = {
  // Core backgrounds
  lpBlack: '#000000',
  lpSurface: '#0d0f1a',

  // Primary accents
  lpCyan: '#00d4ff',
  lpGold: '#f7c524',
  lpPurple: '#a78bfa',

  // Semantic colors
  lpGreen: '#22c55e',
  lpRed: '#ef4444',
  lpAmber: '#f59e0b',

  // Text hierarchy
  textPrimary: '#ffffff',
  textSecondary: '#a0a0a0',
  textMuted: '#666666',

  // Borders
  borderDark: '#1a1a2e',
  borderLight: '#2a2a3e',

  // Gradients (for reference)
  gradientCyanPurple: ['#00d4ff', '#a78bfa'],
  gradientGoldPurple: ['#f7c524', '#a78bfa'],
} as const;

export type ColorKey = keyof typeof colors;
