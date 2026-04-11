/**
 * Trinity Chimera - Design System Color Tokens
 * Centralized color palette for the application
 */

export const colors = {
  // Brand Colors
  brand: {
    primary: "#bd93f9",    // Cyber Purple (Main Accent)
    secondary: "#ff79c6",  // Cyber Pink
    indigo: "#6075ffff",   // Professional Indigo
    teal: "#8be9fd",      // Cyber Teal
  },

  // Trading/Status Colors
  status: {
    up: "#6075ffff",       // For positive movements (matches brand.indigo)
    down: "#ffa2f1ff",     // For negative movements (matches a lighter secondary)
    success: "#4ade80",    // Emerald Green
    danger: "#fb7185",     // Rose Red
    warning: "#ffb86c",    // Pastel Orange
    info: "#8be9fd",       // Matches brand.teal
  },

  // Core System Colors
  slate: {
    50: "#f8fafc",
    100: "#f1f5f9",
    200: "#e2e8f0",
    300: "#cbd5e1",
    400: "#94a3b8",
    500: "#64748b",
    600: "#475569",
    700: "#334155",
    800: "#1e293b",
    900: "#0f172a",
    950: "#020617",
  },

  // Surface/Background Colors
  bg: {
    main: "#0b0b1a",       // Deep Space
    panel: "#060912",      // Dark Panel
    card: "rgba(6, 9, 18, 0.4)",
    hover: "rgba(255, 255, 255, 0.04)",
  },

  // Border & Grid Colors
  border: {
    base: "rgba(255, 255, 255, 0.06)",
    light: "rgba(255, 255, 255, 0.03)",
    accent: "rgba(189, 147, 249, 0.2)",
    focus: "rgba(189, 147, 249, 0.4)",
  },

  // Graphical Elements
  grid: "rgba(189, 147, 249, 0.03)",
  glow: {
    purple: "rgba(189, 147, 249, 0.15)",
    indigo: "rgba(96, 117, 255, 0.1)",
  }
};

export type Colors = typeof colors;
