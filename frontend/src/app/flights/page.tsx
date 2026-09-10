import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Search Results - Fast",
};

export default function FlightsPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold">Available Flights</h1>
      <p className="text-zinc-500 dark:text-zinc-400">
        Flight results will load here based on your search.
      </p>
    </div>
  );
}
