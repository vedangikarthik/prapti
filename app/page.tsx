"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import LanguageSelector from "@/components/LanguageSelector";
import { getStoredLanguage } from "@/lib/language-storage";
import { DEFAULT_LANGUAGE, LanguageCode } from "@/lib/languages";

export default function WelcomePage() {
  const [language, setLanguage] = useState<LanguageCode>(DEFAULT_LANGUAGE);

  useEffect(() => {
    setLanguage(getStoredLanguage());
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-[360px] flex-col gap-8 px-4 py-10" data-nexen-id="nx-6f76c4f4-0">
      <header className="flex flex-col gap-2" data-nexen-id="nx-6f76c4f4-1">
        <h1 className="text-3xl font-bold text-amber-800" data-nexen-id="nx-6f76c4f4-2">HaqPath</h1>
        <p className="text-base text-stone-700" data-nexen-id="nx-6f76c4f4-3">Know what support you can claim.</p>
      </header>

      <LanguageSelector value={language} onChange={setLanguage} />

      <section aria-labelledby="trust-heading" className="flex flex-col gap-2" data-nexen-id="nx-6f76c4f4-4">
        <h2 id="trust-heading" className="text-lg font-semibold" data-nexen-id="nx-6f76c4f4-5">
          How HaqPath works
        </h2>
        <p className="text-base text-stone-700" data-nexen-id="nx-6f76c4f4-6">
          HaqPath provides guidance based on published rules. Final eligibility is decided by the
          relevant authority.
        </p>
      </section>

      <Link
        href="/intake"
        className="flex min-h-[56px] items-center justify-center rounded-xl bg-amber-600 px-6 py-3 text-lg font-semibold text-white"
       data-nexen-id="nx-6f76c4f4-7">
        Continue
      </Link>
    </main>
  );
}
