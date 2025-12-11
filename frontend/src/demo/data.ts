export const demoModels = [
    { name: "orders", type: "table", source_tables: ["raw.orders"], dimensions: ["date", "user_id", "market"] },
    { name: "users", type: "table", source_tables: ["raw.users"], dimensions: ["user_id", "country"] },
];

export const demoMetrics = [
    { name: "mrr", metric_type: "aggregate", expression: "sum(amount)", model: "orders", tags: ["revenue"] },
    { name: "active_users", metric_type: "aggregate", expression: "count(distinct user_id)", model: "users", tags: ["growth"] },
];

export const demoData = {
    models: [
        { name: "customers", type: "dimension", row_count: 1500 },
        { name: "orders", type: "fact", row_count: 45000 },
        { name: "revenue", type: "mart", row_count: 1200 },
    ],
    metrics: [
        { name: "mrr", type: "currency", value: "$45,230" },
        { name: "active_users", type: "count", value: "3,200" },
        { name: "churn_rate", type: "percent", value: "2.1%" },
    ]
};

export const demoGlossary = {
    stats: {
        status: "available",
        generated_at: new Date().toISOString(),
        counts: { entities: 3, metrics: 3, dimensions: 5, relationships: 2 }
    },
    entities: [
        {
            name: "customers",
            model: "customers",
            description: "Registered users of the platform",
            attributes: [
                { name: "id", data_type: "string", is_pk: true, is_fk: false, source_column: "id", tags: ["pii"] },
                { name: "email", data_type: "string", is_pk: false, is_fk: false, source_column: "email", tags: ["pii"] },
                { name: "region", data_type: "string", is_pk: false, is_fk: false, source_column: "region", tags: [] }
            ],
            metrics: ["active_users", "churn_rate"],
            relationships: [
                { source_entity: "customers", target_entity: "orders", type: "one_to_many", source_key: "id", target_key: "customer_id", description: "Customer places orders" }
            ],
            tags: ["core", "pii"]
        },
        {
            name: "orders",
            model: "orders",
            description: "Transactional order records",
            attributes: [
                { name: "id", data_type: "string", is_pk: true, is_fk: false, source_column: "id", tags: [] },
                { name: "customer_id", data_type: "string", is_pk: false, is_fk: true, source_column: "customer_id", tags: [] },
                { name: "amount", data_type: "number", is_pk: false, is_fk: false, source_column: "amount", tags: [] },
                { name: "status", data_type: "string", is_pk: false, is_fk: false, source_column: "status", tags: [] }
            ],
            metrics: ["mrr", "order_count"],
            relationships: [],
            tags: ["core"]
        },
        {
            name: "products",
            model: "products",
            description: "Product catalog",
            attributes: [
                { name: "id", data_type: "string", is_pk: true, is_fk: false, source_column: "id", tags: [] },
                { name: "name", data_type: "string", is_pk: false, is_fk: false, source_column: "name", tags: [] }
            ],
            metrics: [],
            relationships: [],
            tags: []
        }
    ],
    metrics: [
        {
            name: "mrr",
            expression: "SUM(amount)",
            metric_type: "aggregate",
            dimensions: ["region", "status"],
            description: "Monthly Recurring Revenue based on orders",
            default_filters: ["status = 'completed'"],
            grain: "monthly",
            tags: ["kpi", "finance"],
            sources: ["orders"]
        },
        {
            name: "active_users",
            expression: "COUNT(DISTINCT id)",
            metric_type: "aggregate",
            dimensions: ["region"],
            description: "Users with at least one login",
            default_filters: [],
            grain: "daily",
            tags: ["growth"],
            sources: ["customers"]
        },
        {
            name: "churn_rate",
            expression: "lost_users / total_users",
            metric_type: "ratio",
            dimensions: ["region"],
            description: "Percentage of users lost",
            default_filters: [],
            grain: "monthly",
            tags: ["finance"],
            sources: ["customers"]
        }
    ],
    dimensions: [
        {
            name: "region",
            data_type: "string",
            attributes: ["region"],
            related_metrics: ["mrr", "active_users", "churn_rate"],
            description: "Geographical sales region",
            tags: ["geo", "customer"]
        },
        {
            name: "status",
            data_type: "string",
            attributes: ["status"],
            related_metrics: ["mrr"],
            description: "Order processing status",
            tags: ["order"]
        },
        {
            name: "market",
            data_type: "string",
            attributes: [],
            related_metrics: ["mrr"],
            description: "Major market segment",
            tags: ["marketing"]
        },
        {
            name: "date",
            data_type: "date",
            attributes: ["created_at"],
            related_metrics: ["mrr", "active_users"],
            description: "Standard calendar date dimension",
            tags: ["time", "standard"]
        },
        {
            name: "country",
            data_type: "string",
            attributes: ["country"],
            related_metrics: ["active_users"],
            description: "User country of residence",
            tags: ["geo"]
        }
    ]
};

export const demoGraph = {
    nodes: [
        { id: "orders", type: "model", label: "orders" },
        { id: "users", type: "model", label: "users" },
        { id: "mrr", type: "metric", label: "mrr" },
    ],
    edges: [
        { source: "orders", target: "mrr", label: "defines" },
        { source: "users", target: "orders", label: "joins" },
    ]
};
