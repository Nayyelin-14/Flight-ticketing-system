import Skeleton from "@/components/ui/skeleton";
import { airportLabel } from "@/lib/airports";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Search Results - Fast",
};

interface Params {
  origin?: string;
  destination?: string;
  date?: string;
  passengers?: string;
}

function formatDate(date?: string): string {
  if (!date) return "";
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default async function FlightsPage({
  searchParams,
}: {
  searchParams: Promise<Params>;
}) {
  const { origin, destination, date, passengers } = await searchParams;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-2 text-2xl font-bold">Available Flights</h1>

      {origin && destination ? (
        <div className="mb-8 flex flex-wrap items-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
          <span className="font-semibold text-zinc-900 dark:text-zinc-50">
            {airportLabel(origin)}
          </span>
          <span aria-hidden="true">→</span>
          <span className="font-semibold text-zinc-900 dark:text-zinc-50">
            {airportLabel(destination)}
          </span>
          {formatDate(date) ? (
            <>
              <span className="text-zinc-400">·</span>
              <span>{formatDate(date)}</span>
            </>
          ) : null}
          {passengers ? (
            <>
              <span className="text-zinc-400">·</span>
              <span>
                {passengers} {passengers === "1" ? "passenger" : "passengers"}
              </span>
            </>
          ) : null}
        </div>
      ) : null}

      <p className="mb-6 text-zinc-500 dark:text-zinc-400">
        Flight results will load here based on your search.
      </p>

      <div aria-hidden="true" className="flex flex-col gap-4">
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="h-24 rounded-2xl" />
      </div>
    </div>
  );
}