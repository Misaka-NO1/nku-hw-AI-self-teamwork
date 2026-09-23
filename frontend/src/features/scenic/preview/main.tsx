import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import ScenicPage from "../ScenicPage";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <ScenicPage enableAuthoring />
  </StrictMode>,
);
