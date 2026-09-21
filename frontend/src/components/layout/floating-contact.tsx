"use client";

import Icon from "@/components/ui/icon";

interface FloatingContactProps {
  href: string;
  label?: string;
}

export default function FloatingContact({
  href,
  label = "Contact us",
}: FloatingContactProps) {
  return (
    <a
      href={href}
      className="group fixed bottom-6 right-4 z-40 flex h-12 items-center gap-2 rounded-full bg-blue-600 px-3 text-sm font-semibold text-white shadow-lg transition-all hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-xl sm:right-6"
      aria-label={label}
    >
      <Icon name="chat" size={20} />
      <span className="hidden sm:inline">{label}</span>
    </a>
  );
}