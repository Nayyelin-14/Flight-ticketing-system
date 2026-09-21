import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Page not found - Fast",
};

export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <span className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600 dark:text-blue-500">
        <Icon name="compass" size={32} />
      </span>
      <p className="mb-2 text-5xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-6xl">
        404
      </p>
      <h1 className="mb-3 text-2xl font-bold tracking-tight">
        This route has been grounded
      </h1>
      <p className="mb-8 max-w-md text-zinc-500 dark:text-zinc-400">
        The page you&apos;re looking for doesn&apos;t exist or has moved. Let&apos;s
        get you back to your destination.
      </p>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Button href="/" size="lg">
          Back to home
          <Icon name="arrow-right" size={16} />
        </Button>
        <Button href="/flights" size="lg" variant="outline">
          Search flights
        </Button>
      </div>
    </div>
  );
}