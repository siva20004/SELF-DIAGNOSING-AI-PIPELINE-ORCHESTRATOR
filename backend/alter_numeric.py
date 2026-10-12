from sqlalchemy import text
from app.database.session import engine

def alter_precision():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE backfill_plans ALTER COLUMN estimated_cost_usd TYPE NUMERIC(12, 6);"))
            print("Updated backfill_plans.estimated_cost_usd to NUMERIC(12, 6)")
        except Exception as e:
            print("Error altering backfill_plans:", e)
        try:
            conn.execute(text("ALTER TABLE backfill_schedules ALTER COLUMN estimated_cost_usd TYPE NUMERIC(12, 6);"))
            print("Updated backfill_schedules.estimated_cost_usd to NUMERIC(12, 6)")
        except Exception as e:
            print("Error altering backfill_schedules:", e)
        conn.commit()

if __name__ == "__main__":
    alter_precision()
