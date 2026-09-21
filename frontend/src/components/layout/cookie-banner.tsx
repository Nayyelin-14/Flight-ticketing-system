"use client";

import Button from "@/components/ui/button";
import { useEffect, useState } from "react";

const CONSENT_KEY = "fast-cookie-consent";

export default function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!window.localStorage.getItem(CONSENT_KEY)) {
      const t = setTimeout(() => setVisible(true), 1200);
      return () => clearTimeout(t);
    }
  }, []);

  const choose = (value: "accepted" | "declined") => {
    window.localStorage.setItem(CONSENT_KEY, value);
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="region"
      aria-label="Cookie consent"
      className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-md animate-slide-up rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xl sm:left-4 sm:right-auto sm:inset-x-auto dark:border-zinc-800 dark:bg-zinc-900"
    >
      <p className="mb-4 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
        We use cookies to improve your experience and remember your
        preferences. By continuing, you accept our cookie usage.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button size="sm" variant="primary" onClick={() => choose("accepted")}>
          Accept all
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => choose("declined")}
        >
          Decline
        </Button>
      </div>
    </div>
  );
}