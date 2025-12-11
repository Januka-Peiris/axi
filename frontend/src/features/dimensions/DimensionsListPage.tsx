import { Link } from 'react-router-dom';
import { Layers } from 'lucide-react';
import { DimensionListTable } from './components/DimensionListTable';
import { useDimensions } from './api/getDimensions';

export const DimensionsListPage: React.FC = () => {
  const { data: dimensions, isLoading, error } = useDimensions();

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-20">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <Link to="/" className="hover:text-white transition-colors">
          Home
        </Link>
        <span>/</span>
        <span className="text-white">Dimensions</span>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Layers className="w-8 h-8 text-cyan-400" />
            <h1 className="text-3xl font-black text-white">Dimensions</h1>
          </div>
          <p className="text-slate-400">
            Browse and explore all dimensions across your semantic layer
          </p>
        </div>
      </div>

      {/* Content */}
      {error ? (
        <div className="p-8 text-center text-red-400 rounded-xl border border-red-500/20 bg-red-500/10">
          Failed to load dimensions. Please try again later.
        </div>
      ) : (
        <DimensionListTable
          dimensions={dimensions || []}
          isLoading={isLoading}
        />
      )}
    </div>
  );
};
