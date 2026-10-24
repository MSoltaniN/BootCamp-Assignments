# Reproducing day3.sqlite and the deliverables from scratch

1. `python -m pip install -r requirements.txt`
2. Download the pinned embedding model once, then work offline:
   `python scripts/download_model.py`
3. Build the database (schema, 20 users, 120 cases, 24 documents, 1286 provenance chunks):
   `python work/sec06_sqlite/run_section6.py`
   `python work/sec07_ingestion/run_section7.py`
4. Verify the database:
   `python grading/check_day3_db.py day3.sqlite`   # expect status: passed, exit 0
5. Rebuild evaluation artifacts (choose on dev, then lock):
   `python work/sec09_evaluation/run_section09.py` (see section 9 for the exact command)
6. Regenerate the predictions:
   `python work/sec09_evaluation/run_section9.py`
7. Run the regression gate:
   `python work/sec12_integration/run_section12.py`

No password, token, API key, or personal path is required at any step.
