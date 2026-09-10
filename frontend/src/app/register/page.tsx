import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Register - Fast",
};

export default function RegisterPage() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-20">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
        <h1 className="mb-6 text-2xl font-bold">Create Account</h1>
        <form className="flex flex-col gap-4">
          <input type="text" placeholder="Full name" required className="rounded-lg border border-zinc-300 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-800" />
          <input type="email" placeholder="Email" required className="rounded-lg border border-zinc-300 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-800" />
          <input type="tel" placeholder="Phone" required className="rounded-lg border border-zinc-300 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-800" />
          <input type="password" placeholder="Password" required className="rounded-lg border border-zinc-300 px-4 py-2.5 text-sm dark:border-zinc-700 dark:bg-zinc-800" />
          <button type="submit" className="rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">
            Create Account
          </button>
        </form>
      </div>
    </div>
  );
}
