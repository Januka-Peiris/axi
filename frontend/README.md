# AXI Frontend

Semantic Explorer UI for AXI - a React application for browsing and querying your semantic layer.

## Features

- **Metrics Explorer**: Browse, compare, and analyze metrics
- **Dimension Analysis**: Explore dimensions and their relationships
- **Entity Graph**: Visualize entity relationships
- **Query Builder**: Build semantic queries with live SQL preview
- **Business Glossary**: Search and browse business terms
- **Saved Queries**: Save and reuse common queries

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- React Query (data fetching)
- D3.js (visualizations)

## Development

### Prerequisites

- Node.js 18+
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The UI will be available at http://localhost:5173

### Build

```bash
# Production build
npm run build

# Preview production build
npm run preview
```

### Linting

```bash
npm run lint
```

## Configuration

The frontend connects to the AXI backend API. Configure the API URL via environment variables:

```bash
# .env.local
VITE_API_URL=http://localhost:8000
```

## Project Structure

```
src/
├── api/           # API client and hooks
├── components/    # Reusable UI components
├── features/      # Feature-specific modules
│   ├── metrics/
│   ├── dimensions/
│   └── query/
├── layout/        # Layout components (Shell, Nav)
├── pages/         # Page components
└── docs/          # In-app documentation (markdown)
```

## License

MIT. See LICENSE.
