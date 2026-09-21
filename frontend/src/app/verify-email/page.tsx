"use client";

import Button from "@/components/ui/button";
import Spinner from "@/components/ui/spinner";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type VerifyState = "loading" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<VerifyState>(() =>
    token ? "loading" : "error",
  );

  useEffect(() => {
    if (!token) return;

    let cancelled = false;

    async function verify() {
      try {
        const res = await fetch(`${API_BASE}/auth/verify-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });

        if (!cancelled && !res.ok) setState("error");
        if (cancelled) return;
        if (res.ok) setState("success");
      } catch {
        if (!cancelled) setState("error");
      }
    }

    verify();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="flex flex-1 items-center justify-center px-4 py-20">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
        {state === "loading" && (
          <div className="flex flex-col items-center gap-4 text-center">
            <Spinner size={40} className="text-blue-600" />
            <h1 className="text-2xl font-bold">Verifying your email…</h1>
            <p className="text-zinc-500 dark:text-zinc-400">
              Please wait while we verify your email address.
            </p>
          </div>
        )}

        {state === "success" && (
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
              <svg
                className="h-8 w-8 text-green-600 dark:text-green-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4.5 12.75l6 6 9-13.5"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold">Email Verified!</h1>
            <p className="text-zinc-500 dark:text-zinc-400">
              Your email address has been successfully verified.
            </p>
            <p className="text-zinc-500 dark:text-zinc-400">
              You can now log in to your account.
            </p>
            <Button href="/login" className="mt-2">
              Go to Login
            </Button>
          </div>
        )}

        {state === "error" && (
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
              <svg
                className="h-8 w-8 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold">Verification Failed</h1>
            <p className="text-zinc-500 dark:text-zinc-400">
              We couldn&apos;t verify your email address.
            </p>
            <p className="text-zinc-500 dark:text-zinc-400">
              The verification link may be invalid or no longer valid.
            </p>
            <Button href="/register" variant="outline" className="mt-2">
              Back to Registration
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-1 items-center justify-center px-4 py-20">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex flex-col items-center gap-4 text-center">
              <Spinner size={40} className="text-blue-600" />
              <h1 className="text-2xl font-bold">Loading…</h1>
            </div>
          </div>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
