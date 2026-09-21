import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  lines?: number;
}

export default function Skeleton({ className, lines }: SkeletonProps) {
  if (lines) {
    return (
      <div aria-hidden="true" className="space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-4 animate-pulse rounded-md bg-zinc-200 dark:bg-zinc-800",
              i === lines - 1 ? "w-2/3" : "w-full",
              className
            )}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-md bg-zinc-200 dark:bg-zinc-800",
        className
      )}
    />
  );
}