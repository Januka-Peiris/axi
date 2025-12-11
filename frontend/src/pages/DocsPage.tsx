import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { DocsLayout } from '../components/docs/DocsLayout';
import { MarkdownRenderer } from '../components/docs/MarkdownRenderer';

// Import markdown files (Vite ?raw import)
import introMd from '../docs/intro.md?raw';
import modelsMd from '../docs/models.md?raw';
import metricsMd from '../docs/metrics.md?raw';
import glossaryMd from '../docs/glossary.md?raw';
import snowflakeMd from '../docs/snowflake.md?raw';
import cliMd from '../docs/cli.md?raw';

const docsMap: Record<string, string> = {
    'undefined': introMd, // Default route /docs
    'models': modelsMd,
    'metrics': metricsMd,
    'glossary': glossaryMd,
    'snowflake': snowflakeMd,
    'cli': cliMd,
    // Fallback
    'help': introMd
};

export const DocsPage: React.FC = () => {
    const { slug } = useParams<{ slug: string }>();
    const [content, setContent] = useState('');

    useEffect(() => {
        // Simple mapping
        const key = slug || 'undefined';
        setContent(docsMap[key] || '# 404 - Doc Not Found');
    }, [slug]);

    return (
        <DocsLayout>
            <MarkdownRenderer content={content} />
        </DocsLayout>
    );
};
