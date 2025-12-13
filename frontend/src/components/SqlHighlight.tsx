import { useMemo, useState } from 'react';
import { Copy, CheckCircle, Play } from 'lucide-react';

interface SqlHighlightProps {
    sql: string;
    onRun?: (sql: string) => void;
    showLineNumbers?: boolean;
    maxHeight?: string;
}

// SQL keywords for highlighting
const KEYWORDS = [
    'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL',
    'ON', 'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL', 'AS', 'DISTINCT', 'ALL',
    'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'INTERSECT',
    'EXCEPT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'CAST', 'COALESCE',
    'WITH', 'CTE', 'OVER', 'PARTITION', 'ROW_NUMBER', 'RANK', 'DENSE_RANK',
    'SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'FIRST', 'LAST',
    'CREATE', 'TABLE', 'VIEW', 'INDEX', 'DROP', 'ALTER', 'INSERT', 'UPDATE', 'DELETE',
    'INTO', 'VALUES', 'SET', 'TRUNCATE', 'REPLACE',
    'TRUE', 'FALSE', 'ASC', 'DESC', 'NULLS', 'FIRST', 'LAST',
    'BETWEEN', 'LIKE', 'ILIKE', 'EXISTS', 'ANY', 'SOME',
    'DATE', 'TIMESTAMP', 'INTERVAL', 'EXTRACT', 'DATEADD', 'DATEDIFF',
];

const FUNCTIONS = [
    'SUM', 'COUNT', 'AVG', 'MIN', 'MAX', 'COALESCE', 'NULLIF', 'CAST',
    'CONCAT', 'SUBSTRING', 'TRIM', 'UPPER', 'LOWER', 'LENGTH', 'REPLACE',
    'DATE_TRUNC', 'TO_DATE', 'TO_CHAR', 'EXTRACT', 'CURRENT_DATE', 'CURRENT_TIMESTAMP',
    'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'LAG', 'LEAD', 'FIRST_VALUE', 'LAST_VALUE',
    'ABS', 'ROUND', 'CEIL', 'FLOOR', 'MOD', 'POWER', 'SQRT',
    'IFF', 'DECODE', 'NVL', 'ZEROIFNULL', 'IFNULL',
];

export const SqlHighlight = ({
    sql,
    onRun,
    showLineNumbers = true,
    maxHeight = '400px'
}: SqlHighlightProps) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(sql);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const highlightedLines = useMemo(() => {
        const lines = sql.split('\n');

        return lines.map(line => {
            let highlighted = line;

            // Escape HTML
            highlighted = highlighted
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            // Highlight strings (single quotes)
            highlighted = highlighted.replace(
                /'([^']*)'|"([^"]*)"/g,
                '<span class="text-green-400">$&</span>'
            );

            // Highlight numbers
            highlighted = highlighted.replace(
                /\b(\d+\.?\d*)\b/g,
                '<span class="text-orange-400">$1</span>'
            );

            // Highlight keywords (case insensitive)
            const keywordPattern = new RegExp(
                `\\b(${KEYWORDS.join('|')})\\b`,
                'gi'
            );
            highlighted = highlighted.replace(
                keywordPattern,
                '<span class="text-cyan-400 font-semibold">$1</span>'
            );

            // Highlight functions
            const functionPattern = new RegExp(
                `\\b(${FUNCTIONS.join('|')})\\s*\\(`,
                'gi'
            );
            highlighted = highlighted.replace(
                functionPattern,
                '<span class="text-purple-400">$1</span>('
            );

            // Highlight comments
            highlighted = highlighted.replace(
                /(--.*$)/gm,
                '<span class="text-slate-500 italic">$1</span>'
            );

            // Highlight table.column notation
            highlighted = highlighted.replace(
                /\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b/g,
                '<span class="text-yellow-300">$1</span>.<span class="text-yellow-200">$2</span>'
            );

            return highlighted;
        });
    }, [sql]);

    return (
        <div className="relative group">
            {/* Toolbar */}
            <div className="absolute top-2 right-2 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                {onRun && (
                    <button
                        onClick={() => onRun(sql)}
                        className="p-1.5 bg-green-500/20 hover:bg-green-500/30 rounded text-green-400 transition-colors"
                        title="Run query"
                    >
                        <Play className="w-4 h-4" />
                    </button>
                )}
                <button
                    onClick={handleCopy}
                    className="p-1.5 bg-white/10 hover:bg-white/20 rounded text-slate-300 transition-colors"
                    title="Copy to clipboard"
                >
                    {copied ? (
                        <CheckCircle className="w-4 h-4 text-green-400" />
                    ) : (
                        <Copy className="w-4 h-4" />
                    )}
                </button>
            </div>

            {/* Code Block */}
            <div
                className="bg-[#0d1117] border border-white/10 rounded-lg overflow-auto font-mono text-sm"
                style={{ maxHeight }}
            >
                <table className="w-full">
                    <tbody>
                        {highlightedLines.map((line, index) => (
                            <tr key={index} className="hover:bg-white/5">
                                {showLineNumbers && (
                                    <td className="px-3 py-0.5 text-right text-slate-600 select-none border-r border-white/5 w-12">
                                        {index + 1}
                                    </td>
                                )}
                                <td className="px-4 py-0.5">
                                    <pre
                                        className="whitespace-pre text-slate-300"
                                        dangerouslySetInnerHTML={{ __html: line || '&nbsp;' }}
                                    />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default SqlHighlight;
