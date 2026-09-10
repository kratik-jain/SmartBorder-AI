# SMARTBORDER AI API

`/docs` exposes interactive OpenAPI documentation.

## Authentication
`POST /api/auth/login` with `{ "officer_id": "OB-021", "password": "Smart@1234" }`.
Use the returned Bearer token on protected endpoints.

## Main workflow
`POST /api/screenings/create` accepts multipart form-data:
- `document`: JPG/PNG/WEBP
- `selfie`: optional JPG/PNG/WEBP
- `document_type`: passport / visa / national_id / driving_licence / permit

The endpoint creates a case, stores a SHA-256 digest, runs OCR, MRZ/field validation, forensic analysis, optional face verification, watchlist lookup, risk scoring, and audit events.

## Case lifecycle
- `GET /api/screenings/{case_id}` — complete result
- `POST /api/screenings/{case_id}/action` — officer action
- `GET /api/screenings/{case_id}/audit` — immutable event chain view
- `GET /api/evidence/{case_id}` — generated forensic evidence image

## Registry / reporting
- `GET /api/watchlist/search?q=...`
- `POST /api/watchlist` — administrator only
- `GET /api/reports/summary`
- `GET /api/dashboard/stats`
