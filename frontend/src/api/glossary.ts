import { useQuery } from "@tanstack/react-query";
import client, { isDemoMode } from "./client";
import { demoGlossary } from "../demo/data";

// --- Types ---

export interface GlossaryAttribute {
    name: string;
    data_type: string;
    description?: string;
    is_pk: boolean;
    is_fk: boolean;
    source_column: string;
    tags: string[];
}

export interface GlossaryRelationship {
    source_entity: string;
    target_entity: string;
    type: string;
    source_key: string;
    target_key: string;
    description?: string;
}

export interface GlossaryEntity {
    name: string;
    model: string;
    description?: string;
    attributes: GlossaryAttribute[];
    metrics: string[];
    relationships: GlossaryRelationship[];
    tags: string[];
}

export interface GlossaryMetric {
    name: string;
    expression: string;
    metric_type: string;
    dimensions: string[];
    description?: string;
    default_filters: string[];
    grain?: string;
    tags: string[];
    sources: string[];
}

export interface GlossaryDimension {
    name: string;
    data_type: string;
    attributes: string[];
    related_metrics: string[];
    description?: string;
    tags: string[];
}

export interface GlossaryStats {
    status: string;
    generated_at: string;
    counts: {
        entities: number;
        metrics: number;
        dimensions: number;
        relationships: number;
    };
}

export interface SearchResult {
    name: string;
    description?: string;
    type: "entity" | "metric" | "dimension";
}

// --- API Functions ---

export const getGlossaryStats = async (): Promise<GlossaryStats> => {
    if (isDemoMode) return demoGlossary.stats;
    const res = await client.get("/api/glossary/");
    return res.data;
};

export const getGlossaryEntities = async (): Promise<GlossaryEntity[]> => {
    if (isDemoMode) return demoGlossary.entities;
    const res = await client.get("/api/glossary/entities");
    return res.data;
};

export const getGlossaryEntity = async (name: string): Promise<GlossaryEntity> => {
    if (isDemoMode) {
        const ent = demoGlossary.entities.find((e) => e.name === name);
        if (!ent) throw new Error("Entity not found");
        return ent;
    }
    const res = await client.get(`/api/glossary/entities/${name}`);
    return res.data;
};

export const getGlossaryMetrics = async (): Promise<GlossaryMetric[]> => {
    if (isDemoMode) return demoGlossary.metrics;
    const res = await client.get("/api/glossary/metrics");
    return res.data;
};

export const getGlossaryMetric = async (name: string): Promise<GlossaryMetric> => {
    if (isDemoMode) {
        const met = demoGlossary.metrics.find((m) => m.name === name);
        if (!met) throw new Error("Metric not found");
        return met;
    }
    const res = await client.get(`/api/glossary/metrics/${name}`);
    return res.data;
};

export const getGlossaryDimension = async (name: string): Promise<GlossaryDimension> => {
    if (isDemoMode) {
        // @ts-ignore
        const dim = demoGlossary.dimensions?.find((d) => d.name === name);
        if (!dim) throw new Error("Dimension not found");
        return dim;
    }
    const res = await client.get(`/api/glossary/dimensions/${name}`);
    return res.data;
};

export const searchGlossary = async (query: string): Promise<SearchResult[]> => {
    if (isDemoMode) {
        const lowerQ = query.toLowerCase();
        const results: SearchResult[] = [];
        demoGlossary.entities.forEach(e => {
            if (e.name.toLowerCase().includes(lowerQ)) results.push({ name: e.name, type: "entity", description: e.description });
        });
        demoGlossary.metrics.forEach(m => {
            if (m.name.toLowerCase().includes(lowerQ)) results.push({ name: m.name, type: "metric", description: m.description });
        });
        // @ts-ignore
        demoGlossary.dimensions?.forEach(d => {
            if (d.name.toLowerCase().includes(lowerQ)) results.push({ name: d.name, type: "dimension", description: d.description });
        });
        return results;
    }
    const res = await client.get(`/api/glossary/search?q=${query}`);
    return res.data;
};


// --- React Query Hooks ---

export const useGlossaryStats = () => {
    return useQuery({ queryKey: ["glossary", "stats"], queryFn: getGlossaryStats });
};

export const useGlossaryEntities = () => {
    return useQuery({ queryKey: ["glossary", "entities"], queryFn: getGlossaryEntities });
};

export const useGlossaryEntity = (name: string) => {
    return useQuery({ queryKey: ["glossary", "entity", name], queryFn: () => getGlossaryEntity(name), enabled: !!name });
};

export const useGlossaryMetrics = () => {
    return useQuery({ queryKey: ["glossary", "metrics"], queryFn: getGlossaryMetrics });
};

export const useGlossaryMetric = (name: string) => {
    return useQuery({ queryKey: ["glossary", "metric", name], queryFn: () => getGlossaryMetric(name), enabled: !!name });
};

export const useGlossaryDimension = (name: string) => {
    return useQuery({ queryKey: ["glossary", "dimension", name], queryFn: () => getGlossaryDimension(name), enabled: !!name });
};

export const useGlossarySearch = (query: string) => {
    return useQuery({ queryKey: ["glossary", "search", query], queryFn: () => searchGlossary(query), enabled: !!query });
};
