import { DEFAULT_LANGUAGE, LanguageCode, isSupportedLanguage } from "./languages";

const STORAGE_KEY = "haqpath.language";

/** Returns the saved language, or the default when nothing valid is stored. Safe during SSR. */
export function getStoredLanguage(): LanguageCode {
  if (typeof window === "undefined") {
    return DEFAULT_LANGUAGE;
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored !== null && isSupportedLanguage(stored) ? stored : DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE;
  }
}

/** Saves the chosen language. Does nothing during SSR. */
export function setStoredLanguage(code: LanguageCode): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // Storage may be unavailable (private mode, blocked cookies); ignore.
  }
}
