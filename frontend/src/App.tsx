
import { Routes, Route, HashRouter } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { Shell } from './layout/Shell';
import { ErrorBoundary } from './components/ErrorBoundary';

const PromotionDashboard = lazy(() => import('./features/promotion/PromotionDashboard').then(m => ({ default: m.PromotionDashboard })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Models = lazy(() => import('./pages/Models').then(m => ({ default: m.Models })));

const SavedQueriesPage = lazy(() => import('./pages/SavedQueriesPage').then(m => ({ default: m.SavedQueriesPage })));
const QueryRunner = lazy(() => import('./pages/QueryRunner').then(m => ({ default: m.QueryRunner })));
const DocsPage = lazy(() => import('./pages/DocsPage').then(m => ({ default: m.DocsPage })));
const DimensionsListPage = lazy(() => import('./features/dimensions/DimensionsListPage').then(m => ({ default: m.DimensionsListPage })));
const DimensionDetailPage = lazy(() => import('./features/dimensions/DimensionDetailPage').then(m => ({ default: m.DimensionDetailPage })));
const MetricsListPage = lazy(() => import('./features/metrics/MetricsListPage').then(m => ({ default: m.MetricsListPage })));
const MetricDetailPage = lazy(() => import('./features/metrics/MetricDetailPage').then(m => ({ default: m.MetricDetailPage })));
const SemanticQueryPage = lazy(() => import('./features/query/SemanticQueryPage').then(m => ({ default: m.SemanticQueryPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));
const GraphExplore = lazy(() => import('./pages/GraphExplore').then(m => ({ default: m.GraphExplore })));
const GraphExplorer = lazy(() => import('./pages/GraphExplorer').then(m => ({ default: m.GraphExplorer })));
const MetricCompare = lazy(() => import('./pages/MetricCompare').then(m => ({ default: m.MetricCompare })));
const GlossaryHome = lazy(() => import('./pages/glossary/GlossaryHome').then(m => ({ default: m.GlossaryHome })));
const GlossaryEntityList = lazy(() => import('./pages/glossary/EntityList').then(m => ({ default: m.EntityList })));
const GlossaryEntityDetail = lazy(() => import('./pages/glossary/EntityDetail').then(m => ({ default: m.EntityDetail })));
const GlossaryMetricView = lazy(() => import('./pages/glossary/MetricView').then(m => ({ default: m.MetricView })));
const GlossaryDimensionView = lazy(() => import('./pages/glossary/DimensionView').then(m => ({ default: m.DimensionView })));
const GlossaryTermView = lazy(() => import('./pages/glossary/GlossaryTermView').then(m => ({ default: m.GlossaryTermView })));
const RoiPage = lazy(() => import('./pages/RoiPage').then(m => ({ default: m.RoiPage })));

// Use HashRouter for simpler local file execution if needed, but BrowserRouter is fine for Vite
// Using HashRouter ensures reloading works easily without server config for SPA
export default function App() {
  return (
    <ErrorBoundary>
      <HashRouter>
        <Suspense fallback={<div className="p-8 text-slate-300">Loading...</div>}>
          <Routes>
            <Route element={<Shell />}>
              <Route path="/" element={<PromotionDashboard />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/models" element={<Models />} />
              <Route path="/metrics" element={<MetricsListPage />} />
              <Route path="/metrics/compare" element={<MetricCompare />} />
              <Route path="/metrics/:metricId" element={<MetricDetailPage />} />
              <Route path="/roi" element={<RoiPage />} />
              <Route path="/dimensions" element={<DimensionsListPage />} />
              <Route path="/dimensions/:dimensionId" element={<DimensionDetailPage />} />

              <Route path="/saved-queries" element={<SavedQueriesPage />} />
              <Route path="/query" element={<SemanticQueryPage />} />
              <Route path="/query/legacy" element={<QueryRunner />} />

              {/* Graph Routes */}
              <Route path="/graph" element={<GraphExplore />} />
              <Route path="/graph/explore" element={<GraphExplore />} />
              <Route path="/graph/full" element={<GraphExplorer />} />


              {/* Docs Routes */}
              <Route path="/docs" element={<DocsPage />} />
              <Route path="/docs/:slug" element={<DocsPage />} />

              {/* Glossary */}
              <Route path="/glossary" element={<GlossaryHome />} />
              <Route path="/glossary/entities" element={<GlossaryEntityList />} />
              <Route path="/glossary/entity/:name" element={<GlossaryEntityDetail />} />
              <Route path="/glossary/metric/:name" element={<GlossaryMetricView />} />
              <Route path="/glossary/dimension/:name" element={<GlossaryDimensionView />} />
              <Route path="/glossary/term/:term" element={<GlossaryTermView />} />

              {/* Settings */}
              <Route path="/settings" element={<SettingsPage />} />

              <Route path="*" element={<div className="p-8">404 - Not Found</div>} />
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </ErrorBoundary>
  );
}
