import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';




interface Props {
    content: string;
}

export const MarkdownRenderer: React.FC<Props> = ({ content }) => {
    React.useEffect(() => {
        Prism.highlightAll();
    }, []);

    React.useEffect(() => {
        Prism.highlightAll();
    }, [content]);

    return (
        <div className="prose prose-invert prose-slate max-w-none prose-headings:text-transparent prose-headings:bg-clip-text prose-headings:bg-gradient-to-r prose-headings:from-cyan-400 prose-headings:to-violet-400">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    code({ className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || '')
                        return match ? (
                            <div className="relative group">
                                <div className="absolute right-2 top-2 text-xs text-slate-500 font-mono uppercase opacity-0 group-hover:opacity-100 transition-opacity">
                                    {match[1]}
                                </div>
                                <code className={className} {...props}>
                                    {children}
                                </code>
                            </div>
                        ) : (
                            <code className="px-1 py-0.5 rounded bg-white/10 text-cyan-300 font-mono text-sm" {...props}>
                                {children}
                            </code>
                        )
                    },
                    table({ children }) {
                        return (
                            <div className="overflow-x-auto my-8 border border-white/10 rounded-lg">
                                <table className="w-full text-left bg-[#151821]">{children}</table>
                            </div>
                        )
                    },
                    thead({ children }) {
                        return <thead className="bg-white/5 border-b border-white/10 text-slate-200">{children}</thead>
                    },
                    th({ children }) {
                        return <th className="p-4 font-semibold">{children}</th>
                    },
                    td({ children }) {
                        return <td className="p-4 border-b border-white/5 text-slate-400">{children}</td>
                    },
                    blockquote({ children }) {
                        return <blockquote className="border-l-4 border-cyan-500 pl-4 py-1 my-4 bg-cyan-500/5 italic text-slate-300 rounded-r">{children}</blockquote>
                    }
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
};
