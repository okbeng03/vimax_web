module.exports = {
  root: true,
  env: { browser: true, es2024: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
    "prettier",
  ],
  ignorePatterns: ["dist", "node_modules", "*.cjs"],
  parser: "@typescript-eslint/parser",
  plugins: ["react-hooks", "@typescript-eslint"],
  rules: {
    "no-console": "warn",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
  },
};
