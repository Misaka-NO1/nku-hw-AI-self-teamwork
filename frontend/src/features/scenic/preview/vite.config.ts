import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const require = createRequire(import.meta.url);

// The preview's dependencies live below ScenicPage, not beside it. Resolve React
// explicitly so the standalone preview does not alter C's shared frontend setup.
export default defineConfig({
  resolve: {
    alias: [
      { find: /^react$/, replacement: require.resolve("react") },
      { find: /^react\/jsx-runtime$/, replacement: require.resolve("react/jsx-runtime") },
      { find: /^react\/jsx-dev-runtime$/, replacement: require.resolve("react/jsx-dev-runtime") },
      { find: /^react-dom\/client$/, replacement: require.resolve("react-dom/client") },
    ],
  },
  server: {
    fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
  },
  build: {
    rolldownOptions: {
      input: {
        preview: fileURLToPath(new URL("./index.html", import.meta.url)),
        review: fileURLToPath(new URL("./review.html", import.meta.url)),
      },
    },
  },
});
