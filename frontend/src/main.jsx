import "@fontsource-variable/inter";
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/shell.css";
import "./styles/components.css";
import "./styles/tables.css";
import "./styles/print.css";

createRoot(document.getElementById("root")).render(<React.StrictMode><App /></React.StrictMode>);
