"use client";

import { useAuth } from "@/components/auth-provider";
import Spinner from "@/components/ui/spinner";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

function safeNext(pathname: string): string {
  if (!pathname.startsWith("/") || pathname.startsWith("//")) return "/";
  return pathname;
}

/**
 * Client-side guard for authenticated pages.
 * While the session check runs, show a loading state (no content flash).
 * When unauthenticated, replace to /login?next=<internal-path>.
 */
export default function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(safeNext(pathname))}`);
    }
  }, [status, router, pathname]);

  if (status === "loading") {
    return (
      <div
        className="flex flex-1 items-center justify-center px-4 py-20"
        aria-busy="true"
        aria-live="polite"
      >
        <div className="flex flex-col items-center gap-3 text-zinc-500 dark:text-zinc-400">
          <Spinner size={32} className="text-blue-600" />
          <p className="text-sm">Checking your session…</p>
        </div>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return null;
  }

  return <>{children}</>;
}
