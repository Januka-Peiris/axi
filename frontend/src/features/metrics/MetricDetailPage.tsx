import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Calendar, Eye, Edit, Trash2, AlertTriangle } from 'lucide-react';
import {
  useMetric,
  useMetricDimensions,
  useMetricEntities,
  useMetricSample,
  useMetricVersions,
} from './api';
import { useDeleteMetric } from './api/deleteMetric';
import {
  LinkedDimensionsTable,
  LinkedEntitiesTable,
  MetricExpression,
  GeneratedSqlModal,
  MetricBuilder,
  DeleteConfirmModal,
  ServerMetricVersionHistory,
  IntentAndCompiledSqlSection,
  MetricUsageSection,
} from './components';
import { LineageView } from '../../components/LineageView';
import { Comments } from '../../components/Comments';
import { VersionHistory } from '../../components/VersionHistory';
import { GlossaryTermList } from '../../components/glossary/GlossaryTermList';

export const MetricDetailPage: React.FC = () => {
  const { metricId } = useParams<{ metricId: string }>();
  const navigate = useNavigate();
  // Ensure metricId is valid (not null, undefined, or the string "null")
  const validMetricId = metricId && metricId !== 'null' && metricId !== 'undefined' ? metricId : undefined;
  const { data: metric, isLoading: metricLoading, error: metricError, refetch: refetchMetric } = useMetric(validMetricId);
  const { data: dimensions, isLoading: dimensionsLoading } = useMetricDimensions(validMetricId);
  const { data: entities, isLoading: entitiesLoading } = useMetricEntities(validMetricId);
  const { data: sample } = useMetricSample(validMetricId);
  const { data: versionsData, isLoading: versionsLoading } = useMetricVersions(validMetricId);
  const [showSqlModal, setShowSqlModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const deleteMetric = useDeleteMetric();

  if (metricLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
      </div>
    );
  }

  if (metricError || !metric) {
    return (
      <div className="max-w-7xl mx-auto p-10 text-center">
        <div className="text-red-400 mb-4">Metric not found</div>
        <Link
          to="/metrics"
          className="inline-flex items-center gap-2 text-cyan-400 hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Metrics
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-20">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Link to="/" className="hover:text-white transition-colors">
          Home
        </Link>
        <span>/</span>
        <Link to="/metrics" className="hover:text-white transition-colors">
          Metrics
        </Link>
        <span>/</span>
        <span className="text-white">{metric.name}</span>
      </div>

      {/* Back Link */}
      <Link
        to="/metrics"
        className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Metrics
      </Link>

      {/* Header */}
      <div className="space-y-4 border-b border-white/10 pb-8">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <h1 className="text-3xl font-black text-white">{metric.name}</h1>
              <span className="px-3 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 text-sm font-bold uppercase tracking-wider">
                {metric.type}
              </span>
              <span className="px-2 py-1 rounded border text-xs font-mono text-slate-400 border-white/10">
                v{metric.version ?? '1.0'}
              </span>
              <span
                className={`px-2 py-1 rounded border text-xs font-medium capitalize ${
                  metric.status === 'active'
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : metric.status === 'deprecated'
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      : 'bg-red-500/10 text-red-400 border-red-500/20'
                }`}
              >
                {metric.status ?? 'active'}
              </span>
              {(metric.entity_name || metric.entity) && (
                <span className="px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-sm font-bold uppercase tracking-wider">
                  {metric.entity_name || metric.entity}
                </span>
              )}
            </div>
            {metric.tags && metric.tags.length > 0 && (
              <div className="flex gap-2 mb-2">
                {(Array.isArray(metric.tags) ? metric.tags : [])
                  .filter(tag => tag != null && tag !== '')
                  .map((tag, idx) => (
                  <span
                    key={tag || `tag-${idx}`}
                    className="px-2 py-0.5 rounded-full bg-white/5 text-slate-400 border border-white/5 text-xs"
                  >
                    #{tag}
                  </span>
                ))}
              </div>
            )}
            {(metric.updated_at || metric.created_at) && (
              <div className="flex items-center gap-4 text-sm text-slate-500">
                {metric.updated_at && (
                  <div className="flex items-center gap-1">
                    <Calendar className="w-4 h-4" />
                    Updated: {new Date(metric.updated_at).toLocaleDateString()}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Deprecation banner */}
      {metric.status === 'deprecated' && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-amber-200 font-medium">This metric is deprecated.</p>
            {metric.replacement_metric ? (
              <p className="text-slate-300 text-sm mt-1">
                Use{' '}
                <Link
                  to={`/metrics/${metric.replacement_metric}`}
                  className="text-cyan-400 hover:underline font-medium"
                >
                  {metric.replacement_metric}
                </Link>
                instead.
              </p>
            ) : (
              <p className="text-slate-400 text-sm mt-1">No replacement metric specified.</p>
            )}
            {metric.deprecation_date && (
              <p className="text-slate-500 text-xs mt-1">Deprecation date: {metric.deprecation_date}</p>
            )}
          </div>
        </div>
      )}

      {/* Description */}
      {metric.description && (
        <div className="p-6 rounded-xl bg-[#151821] border border-white/10 relative z-0">
          <h2 className="text-lg font-bold text-white mb-3">Description</h2>
          <p className="text-slate-300 leading-relaxed whitespace-pre-wrap break-words">{metric.description}</p>
        </div>
      )}

      {/* Expression */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white">Expression</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowEditModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20 transition-colors"
            >
              <Edit className="w-4 h-4" />
              Edit
            </button>
            <button
              onClick={() => setShowSqlModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded-lg border border-cyan-500/20 transition-colors"
              title="Ad-hoc semantic query SQL (from current dimensions/filters)"
            >
              <Eye className="w-4 h-4" />
              View generated SQL (ad-hoc)
            </button>
            <button
              onClick={() => setShowDeleteModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg border border-red-500/20 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          </div>
        </div>
        <MetricExpression expression={metric.expression} />
      </div>

      {/* Intent & governed compiled SQL (read-only; no execution) */}
      <IntentAndCompiledSqlSection metricId={metric.name} />

      {/* Usage (adoption, version breakdown, deprecated warning) */}
      <MetricUsageSection metricId={metric.name} />

      {/* Lineage View */}
      <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
        <h2 className="text-lg font-bold text-white mb-2">Data Lineage</h2>
        <p className="text-sm text-slate-500 mb-4">Shows upstream sources and downstream usage</p>
        <LineageView metricName={metric.name} />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-8">
          {/* Linked Dimensions */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">Linked Dimensions</h2>
            <LinkedDimensionsTable
              dimensions={dimensions || []}
              isLoading={dimensionsLoading}
            />
          </div>

          {/* Linked Entities */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">Linked Entities</h2>
            <LinkedEntitiesTable entities={entities || []} isLoading={entitiesLoading} />
          </div>

          {/* Sample Values */}
          {sample && sample.rows && sample.rows.length > 0 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-white">Sample Values</h2>
              <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-white/5 border-b border-white/10">
                    <tr>
                      {sample.columns.map((col) => (
                        <th key={col} className="p-4 font-semibold text-slate-300">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {sample.rows.map((row: any, idx: number) => (
                      <tr key={idx} className="hover:bg-white/5">
                        {sample.columns.map((col) => (
                          <td key={col} className="p-4 text-slate-400 font-mono text-sm">
                            {String(row[col] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Metadata */}
          <div className="p-6 rounded-xl bg-[#151821] border border-white/10 space-y-4">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
              Metadata
            </h3>
            {metric.source_model && (
              <div>
                <label className="text-xs font-bold text-slate-600 uppercase">Source Model</label>
                <p className="text-slate-300 font-mono text-sm">{metric.source_model}</p>
              </div>
            )}
            {metric.grain && (
              <div>
                <label className="text-xs font-bold text-slate-600 uppercase">Grain</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {(Array.isArray(metric.grain) ? metric.grain : (metric.grain ? [metric.grain] : []))
                    .filter(g => g != null && g !== '')
                    .map((g, idx) => (
                    <span
                      key={g || `grain-${idx}`}
                      className="px-2 py-1 rounded bg-white/5 text-slate-400 font-mono text-xs border border-white/5"
                    >
                      {g}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {metric.default_dimensions && metric.default_dimensions.length > 0 && (
              <div>
                <label className="text-xs font-bold text-slate-600 uppercase">
                  Default Dimensions
                </label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {(Array.isArray(metric.default_dimensions) ? metric.default_dimensions : [])
                    .filter(dim => dim != null && dim !== '')
                    .map((dim, idx) => (
                    <span
                      key={dim || `dim-${idx}`}
                      className="px-2 py-1 rounded bg-white/5 text-slate-400 font-mono text-xs border border-white/5"
                    >
                      {dim}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Server version history */}
          <ServerMetricVersionHistory
            versions={versionsData?.versions ?? []}
            isLoading={versionsLoading}
            metricName={metric.name}
          />

          {/* Local snapshots (client-side) */}
          <VersionHistory
            entityType="metric"
            entityId={metric.name}
            currentData={{
              name: metric.name,
              expression: metric.expression,
              type: metric.type,
              entity: metric.entity_name || metric.entity,
              description: metric.description
            }}
          />

          {/* Comments */}
          <Comments
            entityType="metric"
            entityId={metric.name}
          />

          {/* Glossary */}
          <GlossaryTermList linkedMetric={metric.name} linkedEntity={metric.entity_name || metric.entity || undefined} />
        </div>
      </div>

      {/* SQL Modal */}
      {metric && (
        <GeneratedSqlModal
          metric={metric}
          isOpen={showSqlModal}
          onClose={() => setShowSqlModal(false)}
        />
      )}

      {/* Edit Modal */}
      {metric && (
        <MetricBuilder
          initialData={{
            metric: metric.name,
            description: metric.description || '',
            entity: metric.entity_name || metric.entity || '',
            expression: metric.expression || '',
            type: metric.type || '',
            grain: Array.isArray(metric.grain) ? metric.grain : (metric.grain ? [metric.grain] : []),
            dimensions: Array.isArray(metric.default_dimensions) ? metric.default_dimensions : [],
            tags: Array.isArray(metric.tags) ? metric.tags : [],
          }}
          isOpen={showEditModal}
          onClose={() => setShowEditModal(false)}
          onSuccess={() => {
            setShowEditModal(false);
            refetchMetric();
          }}
        />
      )}

      {/* Delete Confirmation Modal */}
      {metric && (
        <DeleteConfirmModal
          isOpen={showDeleteModal}
          metricName={metric.name}
          onConfirm={async () => {
            try {
              await deleteMetric.mutateAsync(metric.name);
              navigate('/metrics');
              // Show success notification (you can add toast library if needed)
            } catch (error) {
              console.error('Failed to delete metric:', error);
              // Show error notification
            }
          }}
          onCancel={() => setShowDeleteModal(false)}
          isDeleting={deleteMetric.isPending}
        />
      )}
    </div>
  );
};
