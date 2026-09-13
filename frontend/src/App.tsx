import { Navigate, Route, Routes } from "react-router-dom";

import { PublicLayout, StudioLayout } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { AlbumPage } from "./pages/AlbumPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { ReleaseEditorPage } from "./pages/ReleaseEditorPage";
import { StudioPage } from "./pages/StudioPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";

export function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="records/:slug" element={<AlbumPage />} />
        <Route path="about" element={<AboutPage />} />
      </Route>
      <Route path="studio/login" element={<LoginPage />} />
      <Route path="studio" element={<StudioLayout />}>
        <Route index element={<StudioPage />} />
        <Route path="releases/:id" element={<ReleaseEditorPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
