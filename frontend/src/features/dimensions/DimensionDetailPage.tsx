import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import {
  DimensionHeader,
  LinkedMetricsTable,
  LinkedEntitiesTable,
  SampleValuesPanel,
} from './components';
import { LocalSubgraph } from '../../components/graph/LocalSubgraph';
import {
  useDimension,
  useDimensionMetrics,
  useDimensionEntities,
} from './api';

export const DimensionDetailPage: React.FC = () => {
  const { dimensionId } = useParams<{ dimensionId: string }>();
  const { data: dimension, isLoading: dimLoading, error: dimError } = useDimension(dimensionId);
  const { data: metrics, isLoading: metricsLoading } = useDimensionMetrics(dimensionId);
  const { data: entities, isLoading: entitiesLoading } = useDimensionEntities(dimensionId);

  if (dimLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="animate-spin text-cyan-500 w-8 h-8" />
      </div>
    );
  }

  if (dimError || !dimension) {
    return (
      <div className="max-w-7xl mx-auto p-10 text-center">
        <div className="text-red-400 mb-4">Dimension not found</div>
        <Link
          to="/dimensions"
          className="inline-flex items-center gap-2 text-cyan-400 hover:underline"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dimensions
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
        <Link to="/dimensions" className="hover:text-white transition-colors">
          Dimensions
        </Link>
        <span>/</span>
        <span className="text-white">{dimension.name}</span>
      </div>

      {/* Back Link */}
      <Link
        to="/dimensions"
        className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dimensions
      </Link>

      {/* Header */}
      <DimensionHeader dimension={dimension} />

      {/* Description Box */}
      {dimension.description && (
        <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
          <h2 className="text-lg font-bold text-white mb-3">Description</h2>
          <p className="text-slate-300 leading-relaxed">{dimension.description}</p>
        </div>
      )}

      {/* Local Subgraph */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white">Graph View</h2>
        <LocalSubgraph 
          nodeId={dimension.name} 
          depth={1}
          height="400px"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-8">
          {/* Linked Metrics */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">Linked Metrics</h2>
            <LinkedMetricsTable metrics={metrics || []} isLoading={metricsLoading} />
          </div>

          {/* Linked Entities */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-white">Linked Entities</h2>
            <LinkedEntitiesTable entities={entities || []} isLoading={entitiesLoading} />
          </div>

          {/* Sample Values Panel */}
          <SampleValuesPanel dimensionId={dimensionId!} />
        </div>

        {/* Sidebar - Reserved for future content */}
        <div className="space-y-8">
          {/* Placeholder for additional metadata or actions */}
        </div>
      </div>
    </div>
  );
};

