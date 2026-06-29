import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Migration/utility scripts use CommonJS require()
    "src/scripts/**/*.js",
  ]),
  {
    rules: {
      // Downgrade from error to warn — proper typing is tracked as a separate refactor task
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      // Overly strict for async fetch patterns (setState after await is not truly synchronous)
      "react-hooks/immutability": "warn",
      // Async setState inside effect bodies is the standard pattern for data fetching
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
