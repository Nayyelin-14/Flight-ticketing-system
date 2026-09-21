import RegisterForm from "@/components/register-form";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Register - Fast",
};

export default function RegisterPage() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-20">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-lg dark:border-zinc-800 dark:bg-zinc-900">
        <h1 className="mb-6 text-2xl font-bold">Create Account</h1>
        <RegisterForm />
      </div>
    </div>
  );
}