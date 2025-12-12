import React from 'react';

interface SemanticErrorDetail {
  code?: string;
  message?: string;
  hint?: string;
  [key: string]: any;
}

interface Props {
  error?: SemanticErrorDetail | null;
}

export const SemanticErrorAlert: React.FC<Props> = ({ error }) => {
  if (!error) return null;
  const code = error.code || 'ERROR';
  const message = typeof error.message === 'string' ? error.message : 'Request failed';
  const hint = error.hint;

  return (
    <div className="p-4 rounded-lg border border-red-500/20 bg-red-500/10 text-red-200 space-y-2">
      <div className="font-semibold">{code}</div>
      <div className="text-sm">{message}</div>
      {hint && <div className="text-xs italic text-red-300">Hint: {hint}</div>}
      <details className="text-xs text-red-300">
        <summary className="cursor-pointer">Debug info</summary>
        <pre className="mt-1 whitespace-pre-wrap break-words text-red-300/80">
          {JSON.stringify(error, null, 2)}
        </pre>
      </details>
    </div>
  );
};
