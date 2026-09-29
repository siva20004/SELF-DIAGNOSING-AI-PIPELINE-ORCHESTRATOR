import polars as pl
from typing import Dict, Any, List


def aggregate_dataset(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Computes overall pipeline metrics and grouped aggregates:
    - Total Sales, Total Quantity, Transaction Count, Average Transaction Value
    - Sales by City
    - Sales by Category
    - Sales by Transaction Date
    """
    tx_count = len(df)
    if tx_count == 0:
        return {
            "metrics": {
                "total_sales": 0.0,
                "total_quantity": 0,
                "transaction_count": 0,
                "average_transaction_value": 0.0,
            },
            "sales_by_city": [],
            "sales_by_category": [],
            "sales_by_date": [],
        }

    total_sales = float(df["total_amount"].sum())
    total_quantity = int(df["quantity"].sum())
    avg_tx_val = round(total_sales / tx_count, 2) if tx_count > 0 else 0.0

    # Sales by City
    city_agg = (
        df.group_by("city")
        .agg([
            pl.col("total_amount").sum().round(2).alias("total_sales"),
            pl.col("quantity").sum().alias("total_quantity"),
            pl.len().alias("transaction_count")
        ])
        .sort("total_sales", descending=True)
    )
    sales_by_city = [
        {
            "city": row["city"],
            "total_sales": float(row["total_sales"]),
            "total_quantity": int(row["total_quantity"]),
            "transaction_count": int(row["transaction_count"]),
        }
        for row in city_agg.to_dicts()
    ]

    # Sales by Category
    cat_agg = (
        df.group_by("category")
        .agg([
            pl.col("total_amount").sum().round(2).alias("total_sales"),
            pl.col("quantity").sum().alias("total_quantity"),
            pl.len().alias("transaction_count")
        ])
        .sort("total_sales", descending=True)
    )
    sales_by_category = [
        {
            "category": row["category"],
            "total_sales": float(row["total_sales"]),
            "total_quantity": int(row["total_quantity"]),
            "transaction_count": int(row["transaction_count"]),
        }
        for row in cat_agg.to_dicts()
    ]

    # Sales by Date
    date_agg = (
        df.group_by("transaction_date")
        .agg([
            pl.col("total_amount").sum().round(2).alias("total_sales"),
            pl.col("quantity").sum().alias("total_quantity"),
            pl.len().alias("transaction_count")
        ])
        .sort("transaction_date")
    )
    sales_by_date = [
        {
            "transaction_date": str(row["transaction_date"]),
            "total_sales": float(row["total_sales"]),
            "total_quantity": int(row["total_quantity"]),
            "transaction_count": int(row["transaction_count"]),
        }
        for row in date_agg.to_dicts()
    ]

    return {
        "metrics": {
            "total_sales": round(total_sales, 2),
            "total_quantity": total_quantity,
            "transaction_count": tx_count,
            "average_transaction_value": avg_tx_val,
        },
        "sales_by_city": sales_by_city,
        "sales_by_category": sales_by_category,
        "sales_by_date": sales_by_date,
    }
