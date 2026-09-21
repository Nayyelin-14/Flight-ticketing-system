"use client";

import Icon from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import { useState } from "react";

export interface AccordionItemData {
  id: string;
  question: string;
  answer: string;
}

interface AccordionProps {
  items: AccordionItemData[];
  defaultOpen?: string;
  multiple?: boolean;
}

export default function Accordion({
  items,
  defaultOpen,
  multiple = false,
}: AccordionProps) {
  const [openItems, setOpenItems] = useState<string[]>(
    defaultOpen ? [defaultOpen] : []
  );

  const toggle = (id: string) =>
    setOpenItems((prev) =>
      multiple
        ? prev.includes(id)
          ? prev.filter((x) => x !== id)
          : [...prev, id]
        : prev.includes(id)
          ? []
          : [id]
    );

  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => {
        const open = openItems.includes(item.id);
        return (
          <div
            key={item.id}
            className={cn(
              "overflow-hidden rounded-xl border transition-colors",
              open
                ? "border-blue-600 dark:border-blue-500"
                : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700"
            )}
          >
            <button
              type="button"
              onClick={() => toggle(item.id)}
              aria-expanded={open}
              aria-controls={`faq-panel-${item.id}`}
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
            >
              <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                {item.question}
              </span>
              <Icon
                name="chevron-down"
                size={18}
                className={cn(
                  "shrink-0 text-zinc-400 transition-transform duration-200",
                  open && "rotate-180"
                )}
              />
            </button>
            <div
              id={`faq-panel-${item.id}`}
              role="region"
              className={cn(
                "grid transition-all duration-200",
                open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
              )}
            >
              <div className="overflow-hidden">
                <p className="px-5 pb-4 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
                  {item.answer}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}