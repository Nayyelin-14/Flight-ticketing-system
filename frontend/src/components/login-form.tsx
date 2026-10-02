"use client";

import { useAuth } from "@/components/auth-provider";
import Button from "@/components/ui/button";
import { Input, PasswordInput } from "@/components/ui/input";
import Spinner from "@/components/ui/spinner";
import { normalizeEmail } from "@/lib/auth";
import { ApiError, messageForCode } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, Suspense } from "react";

function safeNext(raw: string | null): string {
  // Only internal relative paths — never absolute or protocol-relative URLs.
  if (!raw) return "/";
  if (!raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

function LoginFormInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<{ email?: string; password?: string }>(
    {},
  );
  const [loading, setLoading] = useState(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  // Already signed in (e.g. navigated back to /login) → leave without history entry.
  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/");
    }
  }, [status, router]);

  // Never show the form while the startup session check runs, and do not
  // leave it mounted once authenticated (redirect is in flight).
  if (status === "loading" || status === "authenticated") {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 py-10 text-zinc-500 dark:text-zinc-400"
        aria-busy="true"
        aria-live="polite"
      >
        <Spinner size={28} />
        <p className="text-sm">
          {status === "loading" ? "Checking your session…" : "Redirecting…"}
        </p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setError("");
    setFieldError({});

    const trimmed = normalizeEmail(email);
    const nextField: { email?: string; password?: string } = {};
    if (!trimmed) nextField.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed))
      nextField.email = "Enter a valid email address.";
    if (!password) nextField.password = "Password is required.";

    if (nextField.email || nextField.password) {
      setFieldError(nextField);
      (nextField.email ? emailRef : passwordRef).current?.focus();
      return;
    }

    setLoading(true);
    try {
      await login(trimmed, password);
      router.replace(safeNext(searchParams.get("next")));
    } catch (err) {
      if (err instanceof ApiError && err.code === "INVALID_CREDENTIALS") {
        setPassword("");
        passwordRef.current?.focus();
        setError(err.message || messageForCode("INVALID_CREDENTIALS"));
      } else if (err instanceof ApiError && err.isNetwork) {
        setError(messageForCode("NETWORK_ERROR"));
      } else if (err instanceof ApiError) {
        setError(err.message || messageForCode(err.code));
      } else {
        setError(messageForCode("INTERNAL_ERROR"));
      }
      // Focus the live error region after a failed submission.
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <Input
        ref={emailRef}
        type="email"
        label="Email"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        disabled={loading}
        autoComplete="email"
        required
        aria-invalid={Boolean(fieldError.email)}
        aria-describedby={fieldError.email ? "login-email-error" : undefined}
      />
      {fieldError.email ? (
        <p
          id="login-email-error"
          className="text-sm text-red-600 dark:text-red-400"
        >
          {fieldError.email}
        </p>
      ) : null}
      <PasswordInput
        ref={passwordRef}
        placeholder="••••••••"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        disabled={loading}
        autoComplete="current-password"
        required
        aria-invalid={Boolean(fieldError.password)}
        aria-describedby={fieldError.password ? "login-password-error" : undefined}
      />
      {fieldError.password ? (
        <p
          id="login-password-error"
          className="text-sm text-red-600 dark:text-red-400"
        >
          {fieldError.password}
        </p>
      ) : null}
      {error ? (
        <p
          ref={errorRef}
          role="alert"
          tabIndex={-1}
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 focus:outline-2 focus:outline-red-600 dark:border-red-900 dark:bg-red-950/50 dark:text-red-400"
        >
          {error}
        </p>
      ) : null}
      <Button type="submit" loading={loading} fullWidth disabled={loading}>
        {loading ? "Signing in…" : "Sign In"}
      </Button>
      {error.includes("verify your email") ? (
        <p className="text-center text-sm text-zinc-500 dark:text-zinc-400">
          Check your inbox for the verification link, then try again.
        </p>
      ) : null}
    </form>
  );
}

export default function LoginForm() {
  return (
    <Suspense fallback={null}>
      <LoginFormInner />
    </Suspense>
  );
}
