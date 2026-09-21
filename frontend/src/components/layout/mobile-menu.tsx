"use client";

import { useAuth } from "@/components/auth-provider";
import { AUTH_LINKS, PUBLIC_LINKS } from "@/lib/nav";
import Link from "next/link";
import { useEffect } from "react";
import { cn } from "@/lib/utils";

interface MobileMenuProps {
  open: boolean;
  onClose: () => void;
}

export default function MobileMenu({ open, onClose }: MobileMenuProps) {
  const { user, isAuthenticated, logout } = useAuth();

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div
        className="absolute inset-0 animate-fade-in bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={cn(
          "absolute inset-x-0 top-16 bottom-0 flex animate-slide-up flex-col overflow-y-auto border-t border-zinc-200 bg-white px-4 py-6 dark:border-zinc-800 dark:bg-zinc-950"
        )}
      >
        <nav aria-label="Mobile" className="flex flex-col gap-1">
          {[...PUBLIC_LINKS, ...(isAuthenticated ? AUTH_LINKS : [])].map(
            (link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={onClose}
                className="rounded-lg px-3 py-3 text-base font-medium text-zinc-700 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
              >
                {link.label}
              </Link>
            )
          )}
        </nav>

        <div className="mt-6 flex flex-col gap-3 border-t border-zinc-200 pt-6 dark:border-zinc-800">
          <p className="text-xs uppercase tracking-wider text-zinc-400">
            {isAuthenticated ? `Signed in as ${user?.name}` : "Account"}
          </p>
          {isAuthenticated ? (
            <button
              type="button"
              onClick={() => {
                onClose();
                logout();
              }}
              className="flex items-center justify-center gap-2 rounded-lg border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
            >
              Logout
            </button>
          ) : (
            <div className="flex flex-col gap-3">
              <Link
                href="/login"
                onClick={onClose}
                className="rounded-lg border border-zinc-300 px-4 py-2.5 text-center text-sm font-semibold text-zinc-700 transition-colors hover:border-zinc-400 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
              >
                Login
              </Link>
              <Link
                href="/register"
                onClick={onClose}
                className="rounded-lg bg-blue-600 px-4 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-blue-700"
              >
                Create Account
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}