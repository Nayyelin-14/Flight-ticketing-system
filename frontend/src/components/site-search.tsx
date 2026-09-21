"use client";

import Modal from "@/components/ui/modal";
import Icon from "@/components/ui/icon";
import Spinner from "@/components/ui/spinner";
import { AIRPORTS } from "@/lib/airports";
import { SEARCHABLE_PAGES } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { useRouter } from "next/navigation";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

interface SearchItem {
  key: string;
  type: "action" | "page" | "airport";
  title: string;
  subtitle?: string;
  href: string;
}

export interface SiteSearchHandle {
  open: () => void;
}

const SiteSearch = forwardRef<SiteSearchHandle>(function SiteSearch(
  _,
  ref
) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [navigating, setNavigating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const openSearch = useCallback(() => {
    setQuery("");
    setSelectedIndex(0);
    setOpen(true);
  }, []);

  useImperativeHandle(ref, () => ({ open: openSearch }));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openSearch();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openSearch]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  const results = useCallback((): SearchItem[] => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const pages: SearchItem[] = SEARCHABLE_PAGES.filter((p) =>
      p.label.toLowerCase().includes(q)
    ).map((p) => ({
      key: `page-${p.href}`,
      type: "page",
      title: p.label,
      subtitle: "Page",
      href: p.href,
    }));
    const airports: SearchItem[] = AIRPORTS.filter(
      (a) =>
        a.name.toLowerCase().includes(q) || a.code.toLowerCase().includes(q)
    ).map((a) => ({
      key: `airport-${a.code}`,
      type: "airport",
      title: `${a.name} (${a.code})`,
      subtitle: "Airport",
      href: `/flights?origin=${a.code}`,
    }));
    return [...airports, ...pages];
  }, [query]);

  const flightSuggestions = useCallback((): SearchItem[] => {
    const q = query.trim();
    if (!q) return [];
    return [
      {
        key: "search-all",
        type: "action",
        title: `Search flights${q ? ` from "${q}"` : ""}`,
        subtitle: "View all available routes",
        href: `/flights?origin=${encodeURIComponent(q.split("/")[0].split(" ")[0])}`,
      },
    ];
  }, [query]);

  const allResults = [...flightSuggestions(), ...results()];

  const go = (href: string) => {
    setNavigating(true);
    setOpen(false);
    router.push(href);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, allResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = allResults[selectedIndex];
      if (item) go(item.href);
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => setOpen(false)}
      title="Search Fast"
      className="sm:max-w-lg"
    >
      <div className="relative mb-4">
        <Icon
          name="search"
          size={18}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelectedIndex(0);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search pages, airports or flights…"
          className="w-full rounded-lg border border-zinc-300 bg-white py-3 pl-10 pr-4 text-sm text-zinc-900 placeholder:text-zinc-400 transition-colors hover:border-zinc-400 focus:outline-2 focus:outline-blue-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-50 dark:placeholder:text-zinc-500 dark:hover:border-zinc-600"
          role="combobox"
          aria-expanded="true"
          aria-controls="search-results"
        />
      </div>

      <div
        id="search-results"
        role="listbox"
        className="max-h-72 overflow-y-auto"
      >
        {navigating ? (
          <div className="flex items-center justify-center gap-2 py-10 text-zinc-500">
            <Spinner size={18} /> Loading…
          </div>
        ) : allResults.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-500">
            No results for &quot;{query}&quot;
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {allResults.map((item, index) => (
              <li key={item.key}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === selectedIndex}
                  onClick={() => go(item.href)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors",
                    index === selectedIndex
                      ? "bg-zinc-100 dark:bg-zinc-800"
                      : "hover:bg-zinc-50 dark:hover:bg-zinc-800/60"
                  )}
                >
                  <Icon
                    name={item.type === "airport" ? "compass" : "arrow-right"}
                    size={16}
                    className="shrink-0 text-zinc-400"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
                      {item.title}
                    </span>
                    {item.subtitle ? (
                      <span className="block text-xs text-zinc-500">
                        {item.subtitle}
                      </span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="mt-4 border-t border-zinc-200 pt-3 text-xs text-zinc-400 dark:border-zinc-800">
        Use <kbd className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">↑</kbd>{" "}
        <kbd className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">↓</kbd> to
        navigate · <kbd className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">Enter</kbd> to
        select · <kbd className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">Ctrl K</kbd> to
        open
      </p>
    </Modal>
  );
});

export default SiteSearch;