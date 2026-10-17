import polars as pl
from typing import Tuple


def calculate_dataset(df: pl.DataFrame) -> Tuple[pl.DataFrame, int, int]:
    """
    Computes derived calculation columns:
    - calculated_total = quantity * unit_price
    - calculation_difference = total_amount - calculated_total
    Preserves both total_amount and calculated_total for audits.
    """
    input_rows = len(df)

    calc_df = df
    if "quantity" in calc_df.columns and calc_df["quantity"].dtype in (pl.Utf8, pl.String):
        calc_df = calc_df.with_columns(pl.col("quantity").cast(pl.Int32, strict=False).alias("quantity"))
    if "unit_price" in calc_df.columns and calc_df["unit_price"].dtype in (pl.Utf8, pl.String):
        calc_df = calc_df.with_columns(pl.col("unit_price").cast(pl.Float64, strict=False).alias("unit_price"))
    if "total_amount" in calc_df.columns and calc_df["total_amount"].dtype in (pl.Utf8, pl.String):
        calc_df = calc_df.with_columns(pl.col("total_amount").cast(pl.Float64, strict=False).alias("total_amount"))

    calculated_df = calc_df.with_columns([
        (pl.col("quantity") * pl.col("unit_price")).round(2).alias("calculated_total"),
        (pl.col("total_amount") - (pl.col("quantity") * pl.col("unit_price"))).round(4).alias("calculation_difference")
    ])

    output_rows = len(calculated_df)
    return calculated_df, input_rows, output_rows
