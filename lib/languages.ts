/**
 * Languages offered on the welcome screen.
 *
 * NOTE: The "regional" entry is a PLACEHOLDER. Replace its code and label
 * with the real regional language for the target state (PRD: [REGIONAL LANGUAGE]).
 */
export const LANGUAGES = [
  { code: "en", label: "English" },
  // TODO: replace with the real regional language before launch.
  { code: "regional", label: "[REGIONAL LANGUAGE]" },
] as const;

export type LanguageCode = (typeof LANGUAGES)[number]["code"];

export const DEFAULT_LANGUAGE: LanguageCode = "en";

export function isSupportedLanguage(code: string): code is LanguageCode {
  return LANGUAGES.some((language) => language.code === code);
}
