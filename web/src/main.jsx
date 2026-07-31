import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./index.css";
// Token sheet last: it is authoritative for color, type, radius and shadow.
import "./premium.css";

createRoot(document.getElementById("root")).render(<App />);
