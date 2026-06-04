# Instructions to Run

Follow these steps to start the Store Intelligence service locally and verify the API.

## 1. Clone the repository

```powershell
git clone https://github.com/jainlavanya14/store-intelligence.git
cd store-intelligence
```

## 2. Start the application with Docker Compose

```powershell
docker compose up --build
```

This launches the FastAPI service on `http://localhost:8000` and mounts the SQLite database in the container.

## 3. Ingest events

Open a second terminal and run:

```powershell
python scripts/ingest_events.py data/events.jsonl
```

Use `data/sample_events.jsonl` for a smaller test dataset if needed.

## 4. Verify the API

### PowerShell

```powershell
Invoke-WebRequest -Uri http://localhost:8000/health -UseBasicParsing | Select-Object -Expand Content
```

### Bash

```bash
curl http://localhost:8000/health
```

## 5. Query store metrics

### PowerShell

```powershell
Invoke-WebRequest -Uri http://localhost:8000/stores/store_1076/metrics -UseBasicParsing | Select-Object -Expand Content
```

### Bash

```bash
curl http://localhost:8000/stores/store_1076/metrics
```

> Replace `store_1076` with the store ID used by your dataset or environment (for example, `STORE_BLR_002` if that is configured by your store mapping).

## 6. Alternative local run (without Docker)

If Docker is unavailable, install Python dependencies and start the app directly:

```powershell
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Then use the same `Invoke-WebRequest` or `curl` commands above.
