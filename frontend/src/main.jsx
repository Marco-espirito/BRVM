import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App.jsx";
const ListePage = lazy(() => import("./pages/ListePage.jsx"));
const DetailPage = lazy(() => import("./pages/DetailPage.jsx"));
const SimulateurPage = lazy(() => import("./pages/SimulateurPage.jsx"));
const PortefeuillePage = lazy(() => import("./pages/PortefeuillePage.jsx"));
const AlertesPage = lazy(() => import("./pages/AlertesPage.jsx"));
const ComparateurPage = lazy(() => import("./pages/ComparateurPage.jsx"));
const ScreenerPage = lazy(() => import("./pages/ScreenerPage.jsx"));
const CalendrierPage = lazy(() => import("./pages/CalendrierPage.jsx"));
const ObjectifPage = lazy(() => import("./pages/ObjectifPage.jsx"));
const BacktestPage = lazy(() => import("./pages/BacktestPage.jsx"));
const TableauBordPage = lazy(() => import("./pages/TableauBordPage.jsx"));
const ParametresPage = lazy(() => import("./pages/ParametresPage.jsx"));
const AnalysePage = lazy(() => import("./pages/AnalysePage.jsx"));
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Suspense fallback={<p className="info">Chargement de la page…</p>}><Routes>
        <Route path="/" element={<App />}>
          <Route index element={<ListePage />} />
          <Route path="tableau-de-bord" element={<TableauBordPage />} />
          <Route path="parametres" element={<ParametresPage />} />
          <Route path="analyse" element={<AnalysePage />} />
          <Route path="action/:symbole" element={<DetailPage />} />
          <Route path="simulateur" element={<SimulateurPage />} />
          <Route path="portefeuille" element={<PortefeuillePage />} />
          <Route path="alertes" element={<AlertesPage />} />
          <Route path="comparateur" element={<ComparateurPage />} />
          <Route path="screener" element={<ScreenerPage />} />
          <Route path="calendrier" element={<CalendrierPage />} />
          <Route path="objectif" element={<ObjectifPage />} />
          <Route path="backtest" element={<BacktestPage />} />
        </Route>
      </Routes></Suspense>
    </BrowserRouter>
  </React.StrictMode>
);
