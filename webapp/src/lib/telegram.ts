export interface HapticFeedback {
  impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
  notificationOccurred(type: "error" | "success" | "warning"): void;
}

export interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  close(): void;
  HapticFeedback?: HapticFeedback;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function haptic(style: "light" | "medium" = "light"): void {
  getWebApp()?.HapticFeedback?.impactOccurred(style);
}

export function hapticSuccess(): void {
  getWebApp()?.HapticFeedback?.notificationOccurred("success");
}
