-- Inventory analysis mart for stock levels, turnover, and procurement insights
with stock_holdings as (
    select * from staging.warehouse.stg__warehouse__stockitemholdings
    where _fivetran_deleted = false
),

stock_transactions as (
    select * from staging.warehouse.stg__warehouse__stockitemtransactions
    where _fivetran_deleted = false
      -- Removed date filter to include all available transaction data
),

stock_items as (
    select * from canon.dims.dim_stock_items
),

suppliers as (
    select * from canon.dims.dim_suppliers
),

purchase_order_lines as (
    select * from staging.purchasing.stg__purchasing__purchaseorderlines
    where _fivetran_deleted = false
),

-- Calculate inventory metrics per stock item
inventory_metrics as (
    select
        sh.stockitemid as stock_item_id,
        
        -- Current stock levels
        sh.quantityonhand as quantity_on_hand,
        sh.binlocation as bin_location,
        sh.laststocktakequantity as last_stocktake_quantity,
        sh.lastcostprice as last_cost_price,
        sh.reorderlevel as reorder_level,
        sh.targetstocklevel as target_stock_level,
        
        -- Stock value
        sh.quantityonhand * sh.lastcostprice as current_stock_value,
        
        -- Transaction analysis (all available data)
        count(st.stockitemtransactionid) as total_transactions,
        sum(case when st.quantity > 0 then st.quantity else 0 end) as total_inbound_quantity,
        sum(case when st.quantity < 0 then abs(st.quantity) else 0 end) as total_outbound_quantity,
        0 as total_sales_value, -- transaction amount not available in source data
        
        -- Purchase order analysis
        count(distinct pol.purchaseorderid) as total_purchase_orders,
        sum(pol.orderedouters) as total_ordered_outers,
        sum(pol.receivedouters) as total_received_outers,
        avg(pol.expectedunitpriceperouter) as avg_purchase_price_per_outer,
        
        -- Stock movement frequency
        count(distinct date_trunc('month', st.transactionoccurredwhen)) as months_with_activity,
        
        -- Latest transaction dates
        max(case when st.quantity > 0 then st.transactionoccurredwhen end) as last_inbound_date,
        max(case when st.quantity < 0 then st.transactionoccurredwhen end) as last_outbound_date
        
    from stock_holdings sh
    left join stock_transactions st on sh.stockitemid = st.stockitemid
    left join purchase_order_lines pol on sh.stockitemid = pol.stockitemid
        -- Removed date filter to include all purchase order data
    
    group by 
        sh.stockitemid,
        sh.quantityonhand,
        sh.binlocation,
        sh.laststocktakequantity,
        sh.lastcostprice,
        sh.reorderlevel,
        sh.targetstocklevel
),

-- Calculate turnover and performance metrics
inventory_performance as (
    select
        im.*,
        
        -- Stock turnover calculations
        case 
            when im.quantity_on_hand > 0 and im.total_outbound_quantity > 0
            then im.total_outbound_quantity / im.quantity_on_hand
            else 0
        end as inventory_turnover_ratio,
        
        case 
            when im.total_outbound_quantity > 0
            then (im.quantity_on_hand / im.total_outbound_quantity) * 365
            else null
        end as days_of_inventory_on_hand,
        
        -- Stock status indicators
        case
            when im.quantity_on_hand <= 0 then 'Out of Stock'
            when im.reorder_level > 0 and im.quantity_on_hand <= im.reorder_level then 'Below Reorder Level'
            when im.target_stock_level > 0 and im.quantity_on_hand >= im.target_stock_level * 1.5 then 'Overstocked'
            when im.target_stock_level > 0 and im.quantity_on_hand >= im.target_stock_level then 'Well Stocked'
            else 'Normal'
        end as stock_status,
        
        -- Activity level
        case
            when im.months_with_activity >= 10 then 'High Activity'
            when im.months_with_activity >= 6 then 'Medium Activity'
            when im.months_with_activity >= 3 then 'Low Activity'
            else 'Inactive'
        end as activity_level,
        
        -- Purchase efficiency
        case
            when im.total_ordered_outers > 0
            then (im.total_received_outers / im.total_ordered_outers) * 100
            else null
        end as purchase_fulfillment_rate
        
    from inventory_metrics im
),

final as (
    select
        ip.*,
        
        -- Enrich with product and supplier information
        si.stock_item_name,
        si.brand,
        si.supplier_name,
        si.color_name,
        si.stock_groups,
        si.unit_price as current_unit_price,
        si.is_chiller_stock,
        si.lead_time_days,
        si.quantity_per_outer,
        
        -- Supplier information
        s.supplier_category_name,
        s.payment_days as supplier_payment_days,
        
        -- Calculate additional insights using max transaction date as reference
        case
            when ip.last_outbound_date is not null
            then (select max(transactionoccurredwhen)::date from staging.warehouse.stg__warehouse__stockitemtransactions) - ip.last_outbound_date::date
            else null
        end as days_since_last_sale,
        
        case
            when ip.last_inbound_date is not null
            then (select max(transactionoccurredwhen)::date from staging.warehouse.stg__warehouse__stockitemtransactions) - ip.last_inbound_date::date
            else null
        end as days_since_last_receipt,
        
        -- Risk indicators
        case
            when ip.stock_status = 'Out of Stock' and ip.activity_level in ('High Activity', 'Medium Activity')
            then 'High Risk - Out of Stock on Active Item'
            when ip.stock_status = 'Below Reorder Level' and si.lead_time_days > 7
            then 'Medium Risk - Low Stock with Long Lead Time'
            when ip.activity_level = 'Inactive' and ip.current_stock_value > 1000
            then 'Medium Risk - High Value Inactive Stock'
            when ip.stock_status = 'Overstocked'
            then 'Low Risk - Overstocked'
            else 'Normal Risk'
        end as risk_category
        
    from inventory_performance ip
    left join stock_items si on ip.stock_item_id = si.stock_item_id
    left join suppliers s on si.supplier_name = s.supplier_name -- joining on name since supplier_id not available
)

select * from final
