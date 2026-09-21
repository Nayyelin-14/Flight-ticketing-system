"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/button";
import { AIRPORTS } from "@/lib/airports";

export default function SearchForm() {
  const router = useRouter();
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [date, setDate] = useState("");
  const [passengers, setPassengers] = useState(1);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams({
      origin,
      destination,
      date,
      passengers: String(passengers),
    });
    router.push(`/flights?${params.toString()}`);
  };

  const selectClasses =
    "rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-sm transition-colors hover:border-zinc-400 focus:border-blue-600 focus:outline-2 focus:outline-blue-600 dark:border-zinc-700 dark:bg-zinc-800 dark:hover:border-zinc-600";

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-4xl rounded-2xl border border-zinc-200 bg-white p-6 shadow-lg dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">From</label>
          <select
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
            required
            aria-label="Origin city"
            className={selectClasses}
          >
            <option value="">Select city</option>
            {AIRPORTS.map((a) => (
              <option key={a.code} value={a.code}>{a.name} ({a.code})</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">To</label>
          <select
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            required
            aria-label="Destination city"
            className={selectClasses}
          >
            <option value="">Select city</option>
            {AIRPORTS.map((a) => (
              <option key={a.code} value={a.code}>{a.name} ({a.code})</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">Date</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
            min={new Date().toISOString().split("T")[0]}
            className={selectClasses}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium uppercase tracking-wider text-zinc-500">Passengers</label>
          <input
            type="number"
            value={passengers}
            onChange={(e) => setPassengers(Number(e.target.value))}
            min={1}
            max={9}
            className={selectClasses}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="invisible text-xs">Search</label>
          <Button type="submit" size="md" fullWidth className="h-[42px]">
            Search Flights
          </Button>
        </div>
      </div>
    </form>
  );
}