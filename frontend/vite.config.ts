import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // 开发模式允许读取仓库根的 fixtures/ 与 knowledge/（带标签的虚构数据）
      allow: [".."],
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    globals: true,
  },
});
