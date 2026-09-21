"use client";

import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { useState } from "react";

export default function Newsletter() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "done">("idle");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setError("");
    setStatus("submitting");
    setTimeout(() => setStatus("done"), 900);
  };

  if (status === "done") {
    return (
      <div className="animate-slide-up flex flex-col items-center gap-3 rounded-2xl border border-green-200 bg-green-50 p-8 text-center dark:border-green-900 dark:bg-green-950/40">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-green-600 text-white">
          <Icon name="check" size={22} />
        </span>
        <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-50">
          You&apos;re on the list!
        </h3>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Deals and route updates are heading to{" "}
          <span className="font-medium">{email}</span> soon.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 sm:flex-row sm:items-start"
      noValidate
    >
      <div className="flex-1">
        <Input
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-label="Email address"
          hint={error}
        />
      </div>
      <Button type="submit" loading={status === "submitting"}>
        Subscribe
      </Button>
    </form>
  );
}