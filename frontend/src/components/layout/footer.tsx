import Icon from "@/components/ui/icon";
import Newsletter from "@/components/layout/newsletter";
import { PUBLIC_LINKS } from "@/lib/nav";
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-black">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-10 md:grid-cols-3">
          <div className="flex flex-col gap-3">
            <Link
              href="/"
              className="flex items-center gap-2 text-xl font-bold tracking-tight transition-opacity hover:opacity-80"
            >
              <Icon name="plane" size={24} className="text-blue-600 dark:text-blue-500" />
              Fast
            </Link>
            <p className="max-w-xs text-sm text-zinc-500 dark:text-zinc-400">
              Search hundreds of routes, book in minutes and fly anywhere —
              all from one place.
            </p>
          </div>

          <nav aria-label="Footer" className="flex flex-col gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Explore
            </h3>
            {PUBLIC_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-zinc-600 transition-colors hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="flex flex-col gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Travel deals
            </h3>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Get the best fares and new route alerts straight to your inbox.
            </p>
            <Newsletter />
          </div>
        </div>

        <div className="mt-10 border-t border-zinc-200 pt-6 text-xs text-zinc-400 dark:border-zinc-800">
          © {new Date().getFullYear()} Fast. All rights reserved.
        </div>
      </div>
    </footer>
  );
}