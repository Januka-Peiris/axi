import { useQuery } from "@tanstack/react-query";
import client from "./client";

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

export interface GlossaryTerm {
    term: string;
    definition: string;
    status: "draft" | "approved" | "deprecated";
    version: number;
    derived_from: string[];
    applies_to_entities: string[];
    scope?: string | null;
    notes?: string | null;
    synonyms: string[];
    source: string;
    created_at?: string;
    updated_at?: string;
}

// --- API Functions ---

export const getGlossaryStats = async (): Promise<GlossaryStats> => {
    const res = await client.get("/api/glossary/");
    return res.data;
};

export const getGlossaryEntities = async (): Promise<GlossaryEntity[]> => {
    const res = await client.get("/api/glossary/entities");
    return res.data;
};

export const getGlossaryEntity = async (name: string): Promise<GlossaryEntity> => {
    const res = await client.get(`/api/glossary/entities/${name}`);
    return res.data;
};

export const getGlossaryMetrics = async (): Promise<GlossaryMetric[]> => {
    const res = await client.get("/api/glossary/metrics");
    return res.data;
};

export const getGlossaryMetric = async (name: string): Promise<GlossaryMetric> => {
    const res = await client.get(`/api/glossary/metrics/${name}`);
    return res.data;
};

export const getGlossaryDimension = async (name: string): Promise<GlossaryDimension> => {
    const res = await client.get(`/api/glossary/dimensions/${name}`);
    return res.data;
};

export const searchGlossary = async (query: string): Promise<SearchResult[]> => {
    const res = await client.get(`/api/glossary/search?q=${query}`);
    return res.data;
};

export const getGlossaryTerms = async (params?: { linked_entity?: string; linked_metric?: string; }): Promise<GlossaryTerm[]> => {
    const query = new URLSearchParams();
    if (params?.linked_entity) query.append("linked_entity", params.linked_entity);
    if (params?.linked_metric) query.append("linked_metric", params.linked_metric);
    const res = await client.get(`/api/glossary/terms${query.toString() ? `?${query.toString()}` : ""}`);
    return res.data;
};

export const getGlossaryTerm = async (term: string): Promise<GlossaryTerm> => {
    const res = await client.get(`/api/glossary/terms/${term}`);
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

export const useGlossaryTerms = (params?: { linked_entity?: string; linked_metric?: string; }) => {
    return useQuery({ queryKey: ["glossary", "terms", params], queryFn: () => getGlossaryTerms(params) });
};

export const useGlossaryTerm = (term: string) => {
    return useQuery({ queryKey: ["glossary", "term", term], queryFn: () => getGlossaryTerm(term), enabled: !!term });
};
