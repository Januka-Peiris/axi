import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import Prism from 'prismjs';
import 'prismjs/components/prism-sql';
import 'prismjs/themes/prism-tomorrow.css';

interface SqlPreviewProps {
  sql: string | null;
  isLoading?: boolean;
}

export const SqlPreview: React.FC<SqlPreviewProps> = ({ sql, isLoading }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (sql) {
      navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const sqlHtml = sql ? Prism.highlight(sql, Prism.languages.sql, 'sql') : '';

  return (
    <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">SQL Preview</h3>
        <div className="flex items-center gap-2">
          {sql && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-white/5 hover:bg-white/10 rounded border border-white/10 transition-colors"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  Copy
                </>
              )}
            </button>
          )}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-slate-400 hover:text-white transition-colors"
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-4">
          {isLoading ? (
            <div className="text-center text-slate-500 py-8">Generating SQL...</div>
          ) : sql ? (
            <div className="overflow-x-auto">
              <pre
                className="text-sm font-mono bg-[#0d0f15] p-4 rounded border border-white/5 overflow-x-auto"
                dangerouslySetInnerHTML={{ __html: sqlHtml }}
              />
            </div>
          ) : (
            <div className="text-center text-slate-500 py-8 italic">
              Select metrics and dimensions to generate SQL
            </div>
          )}
        </div>
      )}
    </div>
  );
};

