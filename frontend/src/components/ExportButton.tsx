import { useState } from 'react';
import { Download, FileSpreadsheet, FileText, ChevronDown, Check, Loader2 } from 'lucide-react';

interface ExportButtonProps {
    data: {
        columns: string[];
        rows: any[][];
    };
    filename?: string;
    disabled?: boolean;
}

type ExportFormat = 'csv' | 'json' | 'excel';

export const ExportButton = ({ data, filename = 'export', disabled = false }: ExportButtonProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [exporting, setExporting] = useState<ExportFormat | null>(null);

    const exportToCSV = () => {
        setExporting('csv');

        try {
            // Build CSV content
            const headers = data.columns.join(',');
            const rows = data.rows.map(row =>
                row.map(cell => {
                    if (cell === null || cell === undefined) return '';
                    const str = String(cell);
                    // Escape quotes and wrap in quotes if contains comma, quote, or newline
                    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                        return `"${str.replace(/"/g, '""')}"`;
                    }
                    return str;
                }).join(',')
            );

            const csvContent = [headers, ...rows].join('\n');

            // Create and download
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            downloadBlob(blob, `${filename}.csv`);
        } finally {
            setExporting(null);
            setIsOpen(false);
        }
    };

    const exportToJSON = () => {
        setExporting('json');

        try {
            // Convert rows to objects
            const jsonData = data.rows.map(row => {
                const obj: Record<string, any> = {};
                data.columns.forEach((col, i) => {
                    obj[col] = row[i];
                });
                return obj;
            });

            const jsonContent = JSON.stringify(jsonData, null, 2);

            const blob = new Blob([jsonContent], { type: 'application/json' });
            downloadBlob(blob, `${filename}.json`);
        } finally {
            setExporting(null);
            setIsOpen(false);
        }
    };

    const exportToExcel = () => {
        setExporting('excel');

        try {
            // Create a simple HTML table that Excel can open
            const tableRows = data.rows.map(row =>
                `<tr>${row.map(cell => `<td>${cell ?? ''}</td>`).join('')}</tr>`
            ).join('');

            const htmlContent = `
                <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
                <head>
                    <meta charset="UTF-8">
                    <!--[if gte mso 9]>
                    <xml>
                        <x:ExcelWorkbook>
                            <x:ExcelWorksheets>
                                <x:ExcelWorksheet>
                                    <x:Name>Data</x:Name>
                                    <x:WorksheetOptions>
                                        <x:DisplayGridlines/>
                                    </x:WorksheetOptions>
                                </x:ExcelWorksheet>
                            </x:ExcelWorksheets>
                        </x:ExcelWorkbook>
                    </xml>
                    <![endif]-->
                </head>
                <body>
                    <table border="1">
                        <thead>
                            <tr>${data.columns.map(col => `<th style="background:#f0f0f0;font-weight:bold;">${col}</th>`).join('')}</tr>
                        </thead>
                        <tbody>
                            ${tableRows}
                        </tbody>
                    </table>
                </body>
                </html>
            `;

            const blob = new Blob([htmlContent], { type: 'application/vnd.ms-excel' });
            downloadBlob(blob, `${filename}.xls`);
        } finally {
            setExporting(null);
            setIsOpen(false);
        }
    };

    const downloadBlob = (blob: Blob, filename: string) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const hasData = data.columns.length > 0 && data.rows.length > 0;

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                disabled={disabled || !hasData}
                className="flex items-center gap-2 px-4 py-2 bg-[#151821] border border-white/10 rounded-lg hover:border-cyan-500/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <Download className="w-4 h-4 text-cyan-400" />
                <span className="text-sm text-slate-300">Export</span>
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <>
                    <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
                    <div className="absolute top-full right-0 mt-2 bg-[#151821] border border-white/10 rounded-xl shadow-xl z-50 min-w-[200px]">
                        <div className="p-2">
                            <button
                                onClick={exportToCSV}
                                disabled={exporting !== null}
                                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left hover:bg-white/5 transition-colors disabled:opacity-50"
                            >
                                {exporting === 'csv' ? (
                                    <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                                ) : (
                                    <FileText className="w-5 h-5 text-green-400" />
                                )}
                                <div>
                                    <div className="text-sm text-slate-300">CSV</div>
                                    <div className="text-xs text-slate-500">Comma-separated values</div>
                                </div>
                            </button>

                            <button
                                onClick={exportToExcel}
                                disabled={exporting !== null}
                                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left hover:bg-white/5 transition-colors disabled:opacity-50"
                            >
                                {exporting === 'excel' ? (
                                    <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                                ) : (
                                    <FileSpreadsheet className="w-5 h-5 text-emerald-400" />
                                )}
                                <div>
                                    <div className="text-sm text-slate-300">Excel</div>
                                    <div className="text-xs text-slate-500">Microsoft Excel format</div>
                                </div>
                            </button>

                            <button
                                onClick={exportToJSON}
                                disabled={exporting !== null}
                                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left hover:bg-white/5 transition-colors disabled:opacity-50"
                            >
                                {exporting === 'json' ? (
                                    <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
                                ) : (
                                    <FileText className="w-5 h-5 text-yellow-400" />
                                )}
                                <div>
                                    <div className="text-sm text-slate-300">JSON</div>
                                    <div className="text-xs text-slate-500">JavaScript Object Notation</div>
                                </div>
                            </button>
                        </div>

                        <div className="border-t border-white/10 px-3 py-2">
                            <div className="text-xs text-slate-500">
                                {data.rows.length} rows, {data.columns.length} columns
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default ExportButton;
