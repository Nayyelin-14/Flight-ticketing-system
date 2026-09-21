import SearchForm from "@/components/search-form";
import FaqSection from "@/components/faq-section";

export default function Home() {
  return (
    <>
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-20">
        <div className="mb-12 text-center">
          <h1 className="mb-3 text-4xl font-bold tracking-tight sm:text-5xl">
            Find your next flight
          </h1>
          <p className="text-lg text-zinc-500 dark:text-zinc-400">
            Search hundreds of routes at the best prices
          </p>
        </div>
        <SearchForm />
      </div>
      <FaqSection />
    </>
  );
}