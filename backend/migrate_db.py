from sqlalchemy import text
from app.database.session import engine

def migrate():
    with engine.connect() as conn:
        # Check and add columns to pipeline_runs
        columns = [
            ("file_format", "VARCHAR(30) DEFAULT 'CSV'"),
            ("dataset_fingerprint", "VARCHAR(64)"),
            ("config_json", "TEXT"),
            ("artifact_path", "VARCHAR(500)"),
        ]
        for col_name, col_type in columns:
            try:
                conn.execute(text(f"ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                print(f"Added column {col_name} to pipeline_runs")
            except Exception as e:
                print(f"Column {col_name} already exists or error: {e}")
        conn.commit()
    print("Migration finished!")

if __name__ == "__main__":
    migrate()
