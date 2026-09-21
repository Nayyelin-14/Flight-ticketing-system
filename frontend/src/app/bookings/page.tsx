import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Bookings - Fast",
};

export default function BookingsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold">My Bookings</h1>
      <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-zinc-300 bg-white px-6 py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-400 dark:bg-zinc-800">
          <Icon name="plane" size={28} />
        </span>
        <p className="max-w-sm text-zinc-500 dark:text-zinc-400">
          No bookings yet. Your upcoming and past trips will show up here.
        </p>
        <Button href="/flights" size="sm">
          Search flights
        </Button>
      </div>
    </div>
  );
}