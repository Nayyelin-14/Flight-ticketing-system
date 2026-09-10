import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Bookings - Fast",
};

export default function BookingsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold">My Bookings</h1>
      <p className="text-zinc-500 dark:text-zinc-400">
        Your upcoming and past bookings will appear here.
      </p>
    </div>
  );
}
