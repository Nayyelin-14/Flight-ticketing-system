import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { resetAuthClientForTests } from "@/lib/api";

afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  resetAuthClientForTests();
});
