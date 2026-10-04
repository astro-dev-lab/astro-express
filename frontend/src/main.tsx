import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Corporate from "./Corporate";
import "./styles.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {window.location.pathname === "/corporate" ? <Corporate /> : <App />}
  </React.StrictMode>,
);
