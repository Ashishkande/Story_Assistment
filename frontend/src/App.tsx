import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ToastProvider } from "./hooks/useToast";
import { AppShell } from "./layouts/AppShell";
import { DashboardPage } from "./pages/Dashboard";
import { DemoPage } from "./pages/Demo";
import { EpisodesPage } from "./pages/Episodes";
import { FeedbackPage } from "./pages/Feedback";
import { LogsPage } from "./pages/Logs";
import { MemoryPage } from "./pages/Memory";
import { OverviewPage } from "./pages/Overview";
import { PlanPage } from "./pages/Plan";
import { StoriesPage } from "./pages/Stories";
import { StoryLayout } from "./pages/StoryLayout";

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="stories" element={<StoriesPage />} />
            <Route path="stories/:storyId" element={<StoryLayout />}>
              <Route index element={<OverviewPage />} />
              <Route path="plan" element={<PlanPage />} />
              <Route path="episodes" element={<EpisodesPage />} />
              <Route path="memory" element={<MemoryPage />} />
              <Route path="feedback" element={<FeedbackPage />} />
              <Route path="logs" element={<LogsPage />} />
            </Route>
            <Route path="demo" element={<DemoPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
