import { useEffect, useState } from "react";
import { api, getToken, type User } from "./api/client";
import { Layout } from "./components/Layout";
import { ChatPage } from "./pages/ChatPage";
import { AlertEventsPage } from "./pages/AlertEventsPage";
import { AssistantsPage } from "./pages/AssistantsPage";
import { AuditLogsPage } from "./pages/AuditLogsPage";
import { BackupsPage } from "./pages/BackupsPage";
import { AnnotationListPage } from "./pages/AnnotationListPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { EvaluationDashboardPage } from "./pages/EvaluationDashboardPage";
import { EvaluationFailureTriagePage } from "./pages/EvaluationFailureTriagePage";
import { ImprovementItemDetailPage } from "./pages/ImprovementItemDetailPage";
import { IndexJobDetailPage } from "./pages/IndexJobDetailPage";
import { IndexJobsPage } from "./pages/IndexJobsPage";
import { KnowledgeBasePage } from "./pages/KnowledgeBasePage";
import { LoginPage } from "./pages/LoginPage";
import { MetadataDictionaryPage } from "./pages/MetadataDictionaryPage";
import { MetadataPrecheckPage } from "./pages/MetadataPrecheckPage";
import { SearchPage } from "./pages/SearchPage";
import { SystemStatus } from "./pages/SystemStatus";
import { UsersPage } from "./pages/UsersPage";
import {
  buildMetadataPrecheckReturnUrl,
  parseMetadataReviewFocus,
  type MetadataReviewFocus,
} from "./utils/metadataPrecheckNavigation";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [active, setActive] = useState("kb");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedImprovementId, setSelectedImprovementId] = useState<string | null>(null);
  const [annotationSearch, setAnnotationSearch] = useState("");
  const [improvementBackSearch, setImprovementBackSearch] = useState("");
  const [metadataReviewFocus, setMetadataReviewFocus] = useState<MetadataReviewFocus | null>(null);
  const [loading, setLoading] = useState(true);

  function applyCurrentRoute() {
    const metadataFocus = parseMetadataReviewFocus(window.location.pathname, window.location.search);
    if (metadataFocus) {
      setMetadataReviewFocus(metadataFocus);
      setActive("kb");
      return;
    }
    if (window.location.pathname === "/metadata/precheck") {
      setActive("metadataPrecheck");
      return;
    }
    if (window.location.pathname === "/evaluation/annotations") {
      setAnnotationSearch(window.location.search);
      setActive("annotations");
      return;
    }
    if (window.location.pathname.startsWith("/evaluation/improvements/")) {
      setSelectedImprovementId(window.location.pathname.split("/").pop() || null);
      setImprovementBackSearch(window.location.search);
      setActive("improvementDetail");
    }
  }

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((me) => {
        setUser(me);
        applyCurrentRoute();
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const handlePopState = () => applyCurrentRoute();
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  if (loading) return <div className="boot">CoreKB</div>;
  if (!user) return <LoginPage onLogin={setUser} />;

  return (
    <Layout user={user} active={active} onNavigate={setActive} onLogout={() => setUser(null)}>
      {active === "kb" && (
        <KnowledgeBasePage
          metadataReviewFocus={metadataReviewFocus}
          onMetadataReviewHandled={() => setMetadataReviewFocus(null)}
          onBackToMetadataPrecheck={(search) => {
            const url = buildMetadataPrecheckReturnUrl(search);
            window.history.pushState(null, "", url);
            setMetadataReviewFocus(null);
            setActive("metadataPrecheck");
          }}
          onOpenJob={(jobId) => {
            setSelectedJobId(jobId);
            setActive("indexJobDetail");
          }}
        />
      )}
      {active === "search" && <SearchPage />}
      {active === "chat" && <ChatPage />}
      {active === "assistants" && <AssistantsPage />}
      {active === "evaluationDashboard" && <EvaluationDashboardPage onOpenEvaluation={() => setActive("evaluation")} />}
      {active === "evaluationFailureTriage" && (
        <EvaluationFailureTriagePage
          onOpenEvaluation={() => setActive("evaluation")}
          onOpenAnnotations={(search) => {
            setAnnotationSearch(search);
            window.history.pushState(null, "", `/evaluation/annotations${search}`);
            setActive("annotations");
          }}
        />
      )}
      {active === "evaluation" && (
        <EvaluationPage
          onOpenAnnotations={(search) => {
            setAnnotationSearch(search);
            window.history.pushState(null, "", `/evaluation/annotations${search}`);
            setActive("annotations");
          }}
        />
      )}
      {active === "annotations" && (
        <AnnotationListPage
          initialSearch={annotationSearch}
          onBackToEvaluation={() => {
            window.history.pushState(null, "", "/");
            setActive("evaluation");
          }}
          onOpenImprovementItem={(itemId, fromSearch) => {
            setSelectedImprovementId(itemId);
            setImprovementBackSearch(fromSearch);
            window.history.pushState(null, "", `/evaluation/improvements/${itemId}`);
            setActive("improvementDetail");
          }}
        />
      )}
      {active === "improvementDetail" && (
        <ImprovementItemDetailPage
          itemId={selectedImprovementId}
          fromAnnotationSearch={improvementBackSearch}
          onBackToAnnotations={(search) => {
            setAnnotationSearch(search);
            window.history.pushState(null, "", `/evaluation/annotations${search || ""}`);
            setActive("annotations");
          }}
        />
      )}
      {active === "alerts" && <AlertEventsPage />}
      {active === "auditLogs" && <AuditLogsPage />}
      {active === "backups" && <BackupsPage />}
      {active === "indexJobs" && (
        <IndexJobsPage
          onOpenJob={(jobId) => {
            setSelectedJobId(jobId);
            setActive("indexJobDetail");
          }}
        />
      )}
      {active === "indexJobDetail" && (
        <IndexJobDetailPage
          jobId={selectedJobId}
          onBack={() => setActive("indexJobs")}
          onOpenJob={(jobId) => {
            setSelectedJobId(jobId);
            setActive("indexJobDetail");
          }}
        />
      )}
      {active === "users" && <UsersPage />}
      {active === "metadataDictionary" && <MetadataDictionaryPage />}
      {active === "metadataPrecheck" && (
        <MetadataPrecheckPage
          onOpenKnowledgeBases={() => setActive("kb")}
          onOpenDictionary={() => setActive("metadataDictionary")}
          onReviewDocument={(focus, url) => {
            setMetadataReviewFocus(focus);
            window.history.pushState(null, "", url);
            setActive("kb");
          }}
        />
      )}
      {active === "system" && <SystemStatus />}
    </Layout>
  );
}
