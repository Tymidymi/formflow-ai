import { build } from "esbuild";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const result = await build({
  absWorkingDir: here,
  entryPoints: ["preview.jsx"],
  outfile: resolve(here, "../api/app/static/preview.bundle.js"),
  bundle: true,
  platform: "browser",
  format: "iife",
  target: ["es2020"],
  jsx: "automatic",
  minify: true,
  sourcemap: false,
  legalComments: "none",
  metafile: true,
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "info",
});
const output = Object.entries(result.metafile.outputs)
  .map(([file, meta]) => file + " " + (meta.bytes / 1024).toFixed(1) + " KiB");
console.log("FormFlow v0.8 bundle: " + output.join(", "));
