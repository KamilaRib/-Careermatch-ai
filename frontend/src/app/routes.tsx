import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import HomePage from "@/pages/HomePage";
import NotFoundPage from "@/pages/NotFoundPage";
import PrivacyPage from "@/pages/PrivacyPage";
import { AssistantPage, JobPage, MatchPage, OptimizePage, ResumePage } from "@/pages/ModulePages";

export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "curriculo", element: <ResumePage /> },
      { path: "vaga", element: <JobPage /> },
      { path: "compatibilidade", element: <MatchPage /> },
      { path: "curriculo-ats", element: <OptimizePage /> },
      { path: "assistente", element: <AssistantPage /> },
      { path: "privacidade", element: <PrivacyPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export const createAppRouter = () => createBrowserRouter(routes);
