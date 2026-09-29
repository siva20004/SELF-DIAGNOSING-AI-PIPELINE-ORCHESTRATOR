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

    calculated_df = df.with_columns([
        (pl.col("quantity") * pl.col("unit_price")).round(2).alias("calculated_total"),
        (pl.col("total_amount") - (pl.col("quantity") * pl.col("unit_price"))).round(4).alias("calculation_difference")
    ])

    output_rows = len(calculated_df)
    return calculated_df, input_rows, output_rows
