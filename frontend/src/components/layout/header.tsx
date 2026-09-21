"use client";

import { useAuth } from "@/components/auth-provider";
import SiteSearch, { type SiteSearchHandle } from "@/components/site-search";
import Icon from "@/components/ui/icon";
import ConfirmDialog from "@/components/ui/confirm-dialog";
import MobileMenu from "@/components/layout/mobile-menu";
import ThemeToggle from "@/components/layout/theme-toggle";
import { AUTH_LINKS, PUBLIC_LINKS } from "@/lib/nav";
import Link from "next/link";
import { useRef, useState } from "react";

export default function Header() {
  const { user, isAuthenticated, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const searchRef = useRef<SiteSearchHandle>(null);

  const handleLogout = () => {
    setLoggingOut(true);
    logout();
    setConfirmLogout(false);
    setLoggingOut(false);
  };

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 backdrop-blur-lg dark:border-zinc-800 dark:bg-black/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2 text-xl font-bold tracking-tight transition-opacity hover:opacity-80"
          >
            <Icon name="plane" size={24} className="text-blue-600 dark:text-blue-500" />
            Fast
          </Link>

          <nav
            aria-label="Primary"
            className="hidden items-center gap-1 lg:flex"
          >
            {[...PUBLIC_LINKS, ...(isAuthenticated ? AUTH_LINKS : [])].map(
              (link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-lg px-3 py-2 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
                >
                  {link.label}
                </Link>
              )
            )}
          </nav>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => searchRef.current?.open()}
              aria-label="Open search"
              title="Search (Ctrl+K)"
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition-colors hover:border-zinc-300 hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
            >
              <Icon name="search" size={18} />
            </button>

            <ThemeToggle />

            {isAuthenticated ? (
              <span className="hidden text-sm text-zinc-500 lg:inline">
                {user?.name}
              </span>
            ) : null}

            {isAuthenticated ? (
              <button
                type="button"
                onClick={() => setConfirmLogout(true)}
                className="hidden h-10 items-center rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300 lg:flex"
              >
                Logout
              </button>
            ) : (
              <Link
                href="/register"
                className="hidden h-10 items-center rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-blue-700 lg:flex"
              >
                Register
              </Link>
            )}

            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
              aria-expanded={menuOpen}
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-600 transition-colors hover:border-zinc-300 hover:bg-zinc-100 hover:text-zinc-900 lg:hidden dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-50"
            >
              <Icon name="menu" size={20} />
            </button>
          </div>
        </div>
      </header>

      <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} />
      <SiteSearch ref={searchRef} />
      <ConfirmDialog
        open={confirmLogout}
        title="Log out?"
        description="You'll need to sign in again to manage your bookings."
        confirmLabel="Log out"
        onCancel={() => setConfirmLogout(false)}
        onConfirm={handleLogout}
        loading={loggingOut}
      />
    </>
  );
}