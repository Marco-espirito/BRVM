import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
import ListePage from "./pages/ListePage.jsx";
import DetailPage from "./pages/DetailPage.jsx";
import SimulateurPage from "./pages/SimulateurPage.jsx";
import PortefeuillePage from "./pages/PortefeuillePage.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<ListePage />} />
          <Route path="action/:symbole" element={<DetailPage />} />
          <Route path="simulateur" element={<SimulateurPage />} />
          <Route path="portefeuille" element={<PortefeuillePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
