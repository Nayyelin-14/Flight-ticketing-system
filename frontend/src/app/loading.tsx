import Skeleton from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div
      aria-label="Loading page content"
      aria-live="polite"
      className="mx-auto max-w-6xl px-4 py-10"
    >
      <Skeleton className="mb-8 h-9 w-56" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Skeleton className="mb-4 h-40 w-full rounded-2xl" />
          <Skeleton lines={4} />
        </div>
        <div className="hidden flex-col gap-4 lg:flex">
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton lines={3} />
        </div>
      </div>
      <p className="sr-only">Loading…</p>
    </div>
  );
}