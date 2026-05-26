/**
 * Lightning Pass Typography
 * Rajdhani font family - bold, technical feel
 */

import { TextStyle } from 'react-native';

export const fontFamily = {
  regular: 'Rajdhani_400Regular',
  medium: 'Rajdhani_500Medium',
  semiBold: 'Rajdhani_600SemiBold',
  bold: 'Rajdhani_700Bold',
} as const;

export const typography: Record<string, TextStyle> = {
  // Hero numbers
  heroXL: {
    fontFamily: fontFamily.bold,
    fontSize: 64,
    lineHeight: 72,
    letterSpacing: -1,
  },
  heroLG: {
    fontFamily: fontFamily.bold,
    fontSize: 40,
    lineHeight: 48,
    letterSpacing: -0.5,
  },
  heroMD: {
    fontFamily: fontFamily.bold,
    fontSize: 32,
    lineHeight: 40,
    letterSpacing: -0.5,
  },

  // Headings
  h1: {
    fontFamily: fontFamily.bold,
    fontSize: 28,
    lineHeight: 36,
  },
  h2: {
    fontFamily: fontFamily.semiBold,
    fontSize: 24,
    lineHeight: 32,
  },
  h3: {
    fontFamily: fontFamily.semiBold,
    fontSize: 20,
    lineHeight: 28,
  },
  h4: {
    fontFamily: fontFamily.medium,
    fontSize: 18,
    lineHeight: 24,
  },

  // Body text
  bodyLG: {
    fontFamily: fontFamily.regular,
    fontSize: 16,
    lineHeight: 24,
  },
  bodyMD: {
    fontFamily: fontFamily.regular,
    fontSize: 14,
    lineHeight: 20,
  },
  bodySM: {
    fontFamily: fontFamily.regular,
    fontSize: 12,
    lineHeight: 16,
  },

  // Labels
  labelLG: {
    fontFamily: fontFamily.semiBold,
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  labelMD: {
    fontFamily: fontFamily.semiBold,
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  labelSM: {
    fontFamily: fontFamily.medium,
    fontSize: 10,
    lineHeight: 14,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },

  // Mono (for numbers, code)
  mono: {
    fontFamily: fontFamily.medium,
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 1,
  },
} as const;

export type TypographyKey = keyof typeof typography;
