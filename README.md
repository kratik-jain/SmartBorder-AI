# SMARTBORDER AI — Complete Backend + Frontend

Full local-first SIH prototype for AI-assisted identity and travel-document screening.

## Included
- Officer login / JWT authentication
- Dashboard and screening history
- New screening case creation
- Multi-document type selection
- Real document image upload
- Document type detection hook
- Tesseract OCR with preprocessing
- Passport MRZ parsing + ICAO-style check-digit validation
- Field/date/required-field validation
- ELA-based forensic analysis with saved evidence image
- Metadata and quality signals
- OpenCV YuNet + SFace face verification when model weights are installed
- Live camera capture in the browser
- Watchlist lookup (synthetic demo data)
- Configurable risk engine
- Officer actions: approve / manual review / investigation
- Chained audit event hashes
- PostgreSQL configuration + Docker Compose
- SQLite fallback for simple Windows execution
- FastAPI `/docs`

## Demo credentials
Officer ID: `OB-021`
Password: `Smart@1234`

Admin ID: `ADMIN-001`
Password: `Admin@1234`

## Windows setup
1. Install Python 3.11+.
2. Install Tesseract OCR. Recommended Windows distribution: https://github.com/UB-Mannheim/tesseract/wiki
3. Extract this project.
4. Open **Command Prompt** in the project folder.
5. Run:
   `run.bat`
6. Open: `http://127.0.0.1:8000`

The code also searches common Windows Tesseract paths. For a custom install, set `TESSERACT_CMD` to the full `tesseract.exe` path.

## Face verification
Run once after dependencies are installed:
`.venv\Scripts\python.exe scripts\download_models.py`
Then restart the server.

## PostgreSQL
Set `DATABASE_URL`, for example:
`postgresql+psycopg://smartborder:smartborder@localhost:5432/smartborder`

Or:
`docker compose up --build`

## Important scope note
The registry is synthetic and intended for SIH demonstration. A production system requires authorized government data connectors, approved document templates, strong privacy/security controls, liveness defenses, calibrated thresholds, and independent model validation.
