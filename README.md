## AI Alarm Audit API ChatBot

A Flask-based REST API that generates AI-powered audit reports for industrial alarm management dashboards (Summary, Analysis, Sequence of Events, and KPI views) using Google's Gemini model.

### Overview

This service accepts raw alarm/dashboard JSON payloads from an alarm management system (e.g. `inSisProSense/AlarmManagement`), filters and shapes the data based on the requested dashboard type, sends it to a Gemini model with a role-specific engineering prompt, and returns a structured Markdown audit report.

### Features

- **Multi-dashboard support** — routes data through dedicated filters for four dashboard profiles:
  - `summary` — Executive alarm metrics, top assets, and event log
  - `analysis` — Bad actors, chattering alarms, severity distribution
  - `soe` — Sequence of Events
  - `kpi` — Shift performance, response times, unacknowledged alarm backlog
  - `alarm_kpi` — Combined pass-through profile
- **Token-aware ingestion** — uses a Hugging Face tokenizer (`gpt2` base) to measure payload size and reject requests exceeding a configurable context window (default: 30,000 tokens)
- **Automatic fallback profile** — unrecognized `dashboard_type` values fall back to a generic auditor profile instead of failing
- **Persisted reports** — each response is also saved locally as a Markdown file (`latest_<dashboard_type>_audit_report.md`)
- **Structured prompting** — enforces a consistent 4-section report structure per dashboard type, with strict "no markdown tables" formatting rules

### Requirements

- Python 3.9+
- [Flask](https://flask.palletsprojects.com/)
- [google-genai](https://pypi.org/project/google-genai/)
- [transformers](https://pypi.org/project/transformers/)

### Installation

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install flask google-genai transformers
```

### Configuration

Before running the app, set the following in your environment (recommended) rather than hardcoding them in source:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export ALARM_MANAGEMENT_URL="https://ai.insisluna.com/inSisProSense/AlarmManagement"
export MODEL_ID="gemini-3.1-flash-lite"
```

### Running the App

```bash
python app.py
```

The server starts on `http://0.0.0.0:5000` (debug mode enabled by default — disable for production).

### API Reference

#### `POST /api/audit`

Generates an AI audit report for a given dashboard payload.

**Request Body (JSON):**

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | ✅ | The question/prompt to ask about the dashboard data |
| `input_data` | object | ✅ | Raw dashboard payload (also accepts `inputdata.json` key, or the full body as fallback) |
| `dashboard_type` / `page_id` | string | ❌ | One of `summary`, `analysis`, `soe`, `kpi`, `alarm_kpi`. Defaults to `summary` |

**Example Request:**

```bash
curl -X POST http://localhost:5000/api/audit \
  -H "Content-Type: application/json" \
  -d '{
        "question": "What are the top recurring alarms this shift?",
        "dashboard_type": "analysis",
        "input_data": {
          "SeverityDistribution": {"Critical": 12, "High": 40, "Low": 88},
          "TopBadActors": [{"Tag": "PIC-101", "Count": 34}],
          "HourlyAlarmTrends": [],
          "ChatteringAlarmsList": [],
          "SuppressedAlarms": []
        }
      }'
```

**Example Response:**

```json
{
  "status": "Success",
  "page_id": "analysis",
  "question": "What are the top recurring alarms this shift?",
  "input": { "...": "..." },
  "tokens_used": 143,
  "chat_response": "## 1. BAD ACTOR IDENTIFICATION\n...",
  "report_saved_to": "latest_analysis_audit_report.md"
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `400` | Empty payload, invalid JSON, missing `question`, or token count exceeds window limit |
| `500` | Ingestion failure or Gemini generation/processing exception |

### Dashboard Filter Logic

Each dashboard type maps to a filter function that reshapes the raw payload before it's sent to the model:

- `filter_alarm_summary` → extracts `TotalAlarmCount`, top assets, and alarm list view
- `filter_alarm_analysis` → extracts severity distribution, top 10 bad actors, hourly trends, chattering/suppressed alarms
- `filter_sequence_of_events` → normalizes alarm occurrences into a chronological event log (title, unit, tag, level, origin/clear time)
- `filter_kpi_metrics` → extracts shift performance, response times, KPI targets, and unacknowledged backlog (passes through raw data if it already matches expected KPI keys)

If a filter function throws an exception, the API falls back to sending the raw, unfiltered `input_data`.

### Project Structure

```
.
├── app.py                             # Main Flask application
├── latest_<dashboard_type>_audit_report.md   # Auto-generated report output (created at runtime)
└── README.md
```

### Notes & Recommendations

- `debug=True` should be disabled before deploying to production.
- Consider adding request authentication/rate limiting, since this endpoint accepts arbitrary JSON and calls a paid LLM API.
- The `WINDOW_LIMIT` (30,000 tokens) is currently hardcoded and can be made configurable via environment variable if needed.
