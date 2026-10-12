from app.database.session import SessionLocal
from app.models.models import FailureDiagnosisRecord

def check():
    db = SessionLocal()
    try:
        recs = db.query(FailureDiagnosisRecord).all()
        print(f"Total diagnosis records: {len(recs)}")
        for r in recs:
            print(f"- Failure: {r.failure_id}, Run: {r.run_id}, Method: {r.diagnosis_method}")
    finally:
        db.close()

if __name__ == "__main__":
    check()
