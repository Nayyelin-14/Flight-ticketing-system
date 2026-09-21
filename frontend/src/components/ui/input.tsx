"use client";

import { forwardRef, useId, useState, type InputHTMLAttributes } from "react";
import Icon from "@/components/ui/icon";
import { cn } from "@/lib/utils";

const INPUT_CLASSES =
  "w-full rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 transition-colors hover:border-zinc-400 focus:border-blue-600 focus:outline-2 focus:outline-blue-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-50 dark:placeholder:text-zinc-500 dark:hover:border-zinc-600";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  function Input({ label, hint, className, id, ...props }, ref) {
    const generatedId = useId().replace(/:/g, "");
    const inputId = id ?? `input-${generatedId}`;
    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label
            htmlFor={inputId}
            className="text-xs font-medium uppercase tracking-wider text-zinc-500"
          >
            {label}
          </label>
        ) : null}
        <input ref={ref} id={inputId} className={cn(INPUT_CLASSES, className)} {...props} />
        {hint ? <p className="text-xs text-zinc-500">{hint}</p> : null}
      </div>
    );
  }
);

export function PasswordInput({
  label = "Password",
  hint,
  className,
  id,
  ...props
}: Omit<InputProps, "type">) {
  const [visible, setVisible] = useState(false);
  const generatedId = useId().replace(/:/g, "");
  const inputId = id ?? `password-${generatedId}`;

  return (
    <div className="flex flex-col gap-1.5">
      {label ? (
        <label
          htmlFor={inputId}
          className="text-xs font-medium uppercase tracking-wider text-zinc-500"
        >
          {label}
        </label>
      ) : null}
      <div className="relative">
        <input
          id={inputId}
          type={visible ? "text" : "password"}
          className={cn(INPUT_CLASSES, "pr-11", className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          title={visible ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-zinc-400 transition-colors hover:text-zinc-700 dark:hover:text-zinc-200"
        >
          <Icon name={visible ? "eye-off" : "eye"} size={18} />
        </button>
      </div>
      {hint ? <p className="text-xs text-zinc-500">{hint}</p> : null}
    </div>
  );
}

export default Input;