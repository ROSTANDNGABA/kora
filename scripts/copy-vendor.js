// Copie les bibliothèques front depuis node_modules vers static/vendor (servies localement par WhiteNoise).
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const nm = (p) => path.join(root, "node_modules", p);
const out = (p) => path.join(root, "static", p);

const files = [
  [nm("htmx.org/dist/htmx.min.js"), out("vendor/htmx.min.js")],
  [nm("alpinejs/dist/cdn.min.js"), out("vendor/alpine.min.js")],
  [nm("chart.js/dist/chart.umd.js"), out("vendor/chart.umd.js")],
  [nm("chart.js/dist/chart.umd.js.map"), out("vendor/chart.umd.js.map")],
  [nm("lucide/dist/umd/lucide.min.js"), out("vendor/lucide.min.js")],
  [nm("lucide/dist/umd/lucide.min.js.map"), out("vendor/lucide.min.js.map")],
];
for (const w of [400, 500, 600, 700, 800]) {
  files.push([
    nm(`@fontsource/poppins/files/poppins-latin-${w}-normal.woff2`),
    out(`fonts/poppins-latin-${w}.woff2`),
  ]);
  files.push([
    nm(`@fontsource/poppins/files/poppins-latin-ext-${w}-normal.woff2`),
    out(`fonts/poppins-latin-ext-${w}.woff2`),
  ]);
}

for (const [src, dest] of files) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  console.log("copié", path.relative(root, dest));
}
