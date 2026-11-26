/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./*/templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1B2A4A", 50: "#EEF1F7", 100: "#D9DFEB", 300: "#8E9BB8", 500: "#4A5B80", 700: "#26365A", 900: "#121D35" },
        marigold: { DEFAULT: "#F2A51A", 50: "#FEF6E6", 100: "#FCE7BC", 600: "#D68C07", 700: "#A86C04" },
        jade: { DEFAULT: "#1F7A6B", 50: "#E8F4F1", 600: "#18665A" },
        rose: { DEFAULT: "#C8364E", 50: "#FBEBEE" },
        paper: "#F4F6F9",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "system-ui", "sans-serif"],
        sans: ['"Public Sans"', "system-ui", "sans-serif"],
      },
      borderRadius: { arch: "999px 999px 14px 14px" },
    },
  },
  plugins: [],
};
