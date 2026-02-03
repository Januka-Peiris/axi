import React, { useState } from 'react';
import { FileJson, Code, Loader2, AlertCircle, Copy, Check } from 'lucide-react';
import { useMetricIntent, useMetricCompiledSql } from '../api';
import Prism from 'prismjs';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-json';
import 'prismjs/themes/prism-tomorrow.css';

interface IntentAndCompiledSqlSectionProps {
  metricId: string;
}

type Tab = 'intent' | 'compiled-sql';

export const IntentAndCompiledSqlSection: React.FC<IntentAndCompiledSqlSectionProps> = ({ metricId }) => {
  const [tab, setTab] = useState<Tab>('intent');
  const [copied, setCopied] = useState(false);
  const { data: intent, isLoading: intentLoading, error: intentError } = useMetricIntent(metricId);
  const { data: compiled, isLoading: sqlLoading, error: sqlError } = useMetricCompiledSql(metricId);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const contentToCopy = tab === 'intent' && intent ? JSON.stringify(intent, null, 2) : tab === 'compiled-sql' && compiled?.sql ? compiled.sql : '';

  return (
    <div className="p-6 rounded-xl bg-[#151821] border border-white/10 space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h3 className="text-lg font-bold text-white mb-1">Intent & governed SQL</h3>
          <p className="text-sm text-slate-500">
            Read-only. Semantic query SQL (Query page or &quot;View Generated SQL&quot;) is ad-hoc; AXI Compiled SQL is governed and intent-based.
          </p>
        </div>
      </div>

      <div className="flex gap-2 border-b border-white/10">
        <button
          type="button"
          onClick={() => setTab('intent')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t transition-colors ${
            tab === 'intent'
              ? 'bg-cyan-500/10 text-cyan-400 border border-b-0 border-cyan-500/30 -mb-px border-white/10'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <FileJson className="w-4 h-4" />
          Semantic Intent
        </button>
        <button
          type="button"
          onClick={() => setTab('compiled-sql')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t transition-colors ${
            tab === 'compiled-sql'
              ? 'bg-cyan-500/10 text-cyan-400 border border-b-0 border-cyan-500/30 -mb-px border-white/10'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Code className="w-4 h-4" />
          AXI Compiled SQL
        </button>
      </div>

      <div className="min-h-[200px] relative">
        {tab === 'intent' && (
          <>
            {intentLoading && (
              <div className="flex items-center gap-2 text-slate-500 py-8">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading intent…
              </div>
            )}
            {intentError && (
              <div className="flex items-center gap-2 text-amber-400 py-4">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{(intentError as Error)?.message ?? 'Failed to load intent'}</span>
              </div>
            )}
            {!intentLoading && !intentError && intent && (
              <>
                <div className="absolute top-2 right-2 z-10">
                  <button
                    type="button"
                    onClick={() => handleCopy(JSON.stringify(intent, null, 2))}
                    className="flex items-center gap-2 px-2 py-1 rounded bg-white/5 text-slate-400 hover:text-white text-xs"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre className="p-4 rounded bg-black/30 border border-white/5 text-sm text-slate-300 overflow-x-auto overflow-y-auto max-h-[400px] pr-24">
                  <code
                    dangerouslySetInnerHTML={{
                      __html: Prism.highlight(
                        JSON.stringify(intent, null, 2),
                        Prism.languages.json,
                        'json'
                      ),
                    }}
                  />
                </pre>
              </>
            )}
          </>
        )}

        {tab === 'compiled-sql' && (
          <>
            {sqlLoading && (
              <div className="flex items-center gap-2 text-slate-500 py-8">
                <Loader2 className="w-5 h-5 animate-spin" />
                Loading compiled SQL…
              </div>
            )}
            {sqlError && (
              <div className="flex items-center gap-2 text-amber-400 py-4">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{(sqlError as Error)?.message ?? 'Failed to load compiled SQL (metric may be disabled)'}</span>
              </div>
            )}
            {!sqlLoading && !sqlError && compiled?.sql && (
              <>
                <div className="absolute top-2 right-2 z-10">
                  <button
                    type="button"
                    onClick={() => handleCopy(compiled.sql)}
                    className="flex items-center gap-2 px-2 py-1 rounded bg-white/5 text-slate-400 hover:text-white text-xs"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre className="p-4 rounded bg-black/30 border border-white/5 text-sm overflow-x-auto overflow-y-auto max-h-[400px] pr-24">
                  <code
                    className="language-sql"
                    dangerouslySetInnerHTML={{
                      __html: Prism.highlight(compiled.sql, Prism.languages.sql, 'sql'),
                    }}
                  />
                </pre>
                <p className="text-xs text-slate-500 mt-2">
                  Governed SQL from Semantic Intent · v{compiled.version} · {compiled.warehouse} · Includes AXI metadata comments; fingerprintable.
                </p>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};
