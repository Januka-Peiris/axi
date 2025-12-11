// Quick script to check if exports are accessible
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const filePath = join(__dirname, 'src/components/graph/VisGraph.tsx');
const content = readFileSync(filePath, 'utf8');

console.log('Checking exports in VisGraph.tsx:');
console.log('Has VisGraphNode:', content.includes('export interface VisGraphNode'));
console.log('Has VisGraphEdge:', content.includes('export interface VisGraphEdge'));
console.log('Has VisGraph:', content.includes('export const VisGraph'));

// Check for syntax issues
const exportLines = content.split('\n').filter((line, i) => {
    if (line.includes('export')) {
        console.log(`Line ${i+1}: ${line.trim()}`);
        return true;
    }
    return false;
});

console.log(`\nTotal export statements: ${exportLines.length}`);



