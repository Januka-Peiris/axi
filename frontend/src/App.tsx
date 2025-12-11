
import { Routes, Route, HashRouter } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import { Shell } from './layout/Shell';
import { ErrorBoundary } from './components/ErrorBoundary';

const PromotionDashboard = lazy(() => import('./features/promotion/PromotionDashboard').then(m => ({ default: m.PromotionDashboard })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Models = lazy(() => import('./pages/Models').then(m => ({ default: m.Models })));
const GraphExplorer = lazy(() => import('./pages/GraphExplorer').then(m => ({ default: m.GraphExplorer })));
const FilteredGraphExplorer = lazy(() => import('./pages/FilteredGraphExplorer').then(m => ({ default: m.FilteredGraphExplorer })));
const QueryRunner = lazy(() => import('./pages/QueryRunner').then(m => ({ default: m.QueryRunner })));
const DocsPage = lazy(() => import('./pages/DocsPage').then(m => ({ default: m.DocsPage })));
const DimensionsListPage = lazy(() => import('./features/dimensions/DimensionsListPage').then(m => ({ default: m.DimensionsListPage })));
const DimensionDetailPage = lazy(() => import('./features/dimensions/DimensionDetailPage').then(m => ({ default: m.DimensionDetailPage })));
const MetricsListPage = lazy(() => import('./features/metrics/MetricsListPage').then(m => ({ default: m.MetricsListPage })));
const MetricDetailPage = lazy(() => import('./features/metrics/MetricDetailPage').then(m => ({ default: m.MetricDetailPage })));
const SemanticQueryPage = lazy(() => import('./features/query/SemanticQueryPage').then(m => ({ default: m.SemanticQueryPage })));

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
              <Route path="/metrics/:metricId" element={<MetricDetailPage />} />
              <Route path="/dimensions" element={<DimensionsListPage />} />
              <Route path="/dimensions/:dimensionId" element={<DimensionDetailPage />} />
              <Route path="/graph" element={<GraphExplorer />} />
              <Route path="/graph/explore" element={<FilteredGraphExplorer />} />
              <Route path="/query" element={<SemanticQueryPage />} />
              <Route path="/query/legacy" element={<QueryRunner />} />


              {/* Docs Routes */}
              <Route path="/docs" element={<DocsPage />} />
              <Route path="/docs/:slug" element={<DocsPage />} />

              <Route path="*" element={<div className="p-8">404 - Not Found</div>} />
            </Route>
          </Routes>
        </Suspense>
      </HashRouter>
    </ErrorBoundary>
  );
}
