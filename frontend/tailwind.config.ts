import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0f7ff",
          500: "#2563eb",
          700: "#1d4ed8",
          900: "#0f172a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
