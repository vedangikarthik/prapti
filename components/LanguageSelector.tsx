"use client";

import { LANGUAGES, LanguageCode } from "@/lib/languages";
import { setStoredLanguage } from "@/lib/language-storage";

type LanguageSelectorProps = {
  value: LanguageCode;
  onChange?: (code: LanguageCode) => void;
};

export default function LanguageSelector({ value, onChange }: LanguageSelectorProps) {
  function handleChange(code: LanguageCode) {
    setStoredLanguage(code);
    onChange?.(code);
  }

  return (
    <fieldset className="w-full max-w-[360px]" data-nexen-id="nx-6e19eb63-0">
      <legend className="mb-3 text-lg font-semibold" data-nexen-id="nx-6e19eb63-1">Choose your language</legend>
      <div className="flex flex-col gap-3">
        {LANGUAGES.map((language) => {
          const inputId = `language-${language.code}`;
          const checked = value === language.code;
          return (
            <label
              key={language.code}
              htmlFor={inputId}
              className={`flex min-h-[56px] cursor-pointer items-center gap-3 rounded-xl border-2 px-4 py-3 text-base ${
                checked ? "border-amber-600 bg-white" : "border-stone-300 bg-white"
              }`}
             data-nexen-id="nx-6e19eb63-2">
              <input
                id={inputId}
                type="radio"
                name="language"
                value={language.code}
                checked={checked}
                onChange={() => handleChange(language.code)}
                className="h-5 w-5 accent-amber-600"
               data-nexen-id="nx-6e19eb63-3"/>
              <span data-nexen-id="nx-6e19eb63-4">{language.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
