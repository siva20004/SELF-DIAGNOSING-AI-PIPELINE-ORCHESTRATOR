import polars as pl
from typing import Tuple


def transform_dataset(df: pl.DataFrame) -> Tuple[pl.DataFrame, int, int]:
    """
    Transforms dataset columns into strong domain types:
    - Casts numeric fields (quantity -> Int32, unit_price -> Float64, total_amount -> Float64)
    - Formats transaction_date to standard YYYY-MM-DD
    """
    input_rows = len(df)

    exprs = []
    if "quantity" in df.columns:
        exprs.append(pl.col("quantity").cast(pl.Int32, strict=False).alias("quantity"))
    if "unit_price" in df.columns:
        exprs.append(pl.col("unit_price").cast(pl.Float64, strict=False).alias("unit_price"))
    if "total_amount" in df.columns:
        exprs.append(pl.col("total_amount").cast(pl.Float64, strict=False).alias("total_amount"))
    if "transaction_date" in df.columns:
        from app.services.time_utils import normalize_date_val
        raw_dates = df["transaction_date"].to_list()
        norm_dates = [normalize_date_val(d) for d in raw_dates]
        exprs.append(pl.Series("transaction_date", norm_dates, dtype=pl.String))

    transformed_df = df.with_columns(exprs) if exprs else df
    output_rows = len(transformed_df)

    return transformed_df, input_rows, output_rows
