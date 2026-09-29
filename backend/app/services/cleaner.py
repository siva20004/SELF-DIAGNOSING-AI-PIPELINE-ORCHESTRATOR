import polars as pl
from typing import Tuple


def clean_dataset(df: pl.DataFrame) -> Tuple[pl.DataFrame, int, int]:
    """
    Cleans dataset using safe, configured operations:
    - Strips leading/trailing whitespace from string columns.
    - Does NOT invent data or replace nulls with fake placeholders.
    """
    input_rows = len(df)

    exprs = []
    for col in df.columns:
        if df[col].dtype in (pl.Utf8, pl.String):
            exprs.append(pl.col(col).str.strip_chars().alias(col))
        else:
            exprs.append(pl.col(col))

    cleaned_df = df.with_columns(exprs)
    output_rows = len(cleaned_df)

    return cleaned_df, input_rows, output_rows
