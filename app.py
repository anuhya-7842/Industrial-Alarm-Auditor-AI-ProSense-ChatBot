import os
import json
from flask import Flask, request, jsonify
from google import genai
from transformers import AutoTokenizer

app = Flask(__name__)

# --- CONFIGURATION ---
ALARM_MANAGEMENT_URL = "https://ai.insisluna.com/inSisProSense/AlarmManagement"
MODEL_ID = "gemini-3.1-flash-lite"

# Initialize Tokenizer (v4.54.1) using 'gpt2' as a base
TOKENIZER_NAME = "gpt2"
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)

# Initialize Client
client = genai.Client(api_key="AIzaSyCEe7YoCHjUNjuImDBTO4umy9YWiKMau3Q")

# =====================================================================
# MULTI-DASHBOARD DATA FILTERING ENGINE
# =====================================================================

def filter_alarm_summary(raw_data):
    counts = raw_data.get("TotalAlarmCount", {})
    return {
        "SystemInfo": {
            "TargetLink": ALARM_MANAGEMENT_URL,
            "TotalAlarms": counts.get("Total", 0),
            "ActiveAlarms": counts.get("ActiveAlarms", 0),
            "CriticalAlarms": counts.get("CriticalAlarms", 0),
            "AlarmRatePerMinute": counts.get("AlarmRatePerMinute", 0)
        },
        "TopAssets": raw_data.get("TopAlarmsByAsset", []),
        "TopAlarmsByDuration": raw_data.get("TopAlarmsByDuration", []),
        "AlarmListView": raw_data.get("AlarmListView", [])
    }

def filter_alarm_analysis(raw_data):
    return {
        "DistributionBySeverity": raw_data.get("SeverityDistribution", {}),
        "BadActors": raw_data.get("TopBadActors", [])[:10],
        "HourlyTrends": raw_data.get("HourlyAlarmTrends", []),
        "ChatteringAlarms": raw_data.get("ChatteringAlarmsList", []),
        "ShelvedOrSuppressed": raw_data.get("SuppressedAlarms", [])
    }

def filter_sequence_of_events(raw_data):
    filtered_events = []
    occurrences = raw_data.get("AllAlarmOccurrences") or raw_data.get("Occurrences") or []
    for occurrence in occurrences:
        msg = (occurrence.get("AlarmTitle") or occurrence.get("NotificationMessageModified") or "").strip()
        if not msg:
            msg = f"Event ID {occurrence.get('ID')}"
        filtered_events.append({
            "AlarmMessage": msg,
            "Unit": occurrence.get("Unit"),
            "TagID": occurrence.get("TagID") or occurrence.get("ID"),
            "Level": occurrence.get("Level"),
            "OriginTime": occurrence.get("OriginTime"),
            "ClearTime": occurrence.get("ClearTime")
        })
    return {"ChronologicalEventLog": filtered_events}

def filter_kpi_metrics(raw_data):
    if "Top5Sources" in raw_data or "inputdata.json" in raw_data:
        return raw_data
        
    return {
        "ShiftPerformance": raw_data.get("ShiftPerformanceMetrics", []),
        "AverageResponseTimes": raw_data.get("OperatorResponseTimes", {}),
        "TargetVsActualKPIs": raw_data.get("KPITargets", {}),
        "UnacknowledgedAlarmsOvertime": raw_data.get("UnacknowledgedBacklog", [])
    }

# Dynamic mapping dictionary
DASHBOARD_MAP = {
    "summary": {
        "filter_func": filter_alarm_summary,
        "role": "Expert Lead Automation and Process Root-Cause Engineer auditing Alarm Summaries.",
        "headers": "## 1. EXECUTIVE METRIC AUDIT\n## 2. PARETO ALARM FREQUENCY & ROOT-CAUSE ANALYSIS\n## 3. ENGINEERING SUGGESTIONS & MITIGATION PROTOCOLS\n## 4. CHRONOLOGICAL EVENT LOG FLOW"
    },
    "analysis": {
        "filter_func": filter_alarm_analysis,
        "role": "Expert Reliability and Maintenance Engineer auditing Bad Actors & Recurrent Alarm Trends.",
        "headers": "## 1. BAD ACTOR IDENTIFICATION\n## 2. CHATTERING & RECURRENT PATTERN ANALYSIS\n## 3. ALARM RATIONALIZATION & SHELVING RECOMMENDATIONS\n## 4. SEVERITY DISTRIBUTION METRICS"
    },
    "soe": {
        "filter_func": filter_sequence_of_events,
        "role": "Expert Forensic Process Safety Engineer analyzing Cascading Sequence of Events (SOE).",
        "headers": "## 1. CRITICAL EVENT CHRONOLOGY TIMELINE\n## 2. PRIMARY TRIGGERING ANOMALY DIAGNOSIS\n## 3. CASCADING TRIP OR DOMINO EFFECT ANALYSIS\n## 4. CORRECTIVE INSTRUMENTATION ACTION PLAN"
    },
    "kpi": {
        "filter_func": filter_kpi_metrics,
        "role": "Operations Manager and Shift Performance Auditor checking plant operational health.",
        "headers": "## 1. SHIFT BENCHMARKING & PERFORMANCE SCORECARD\n## 2. OPERATOR RESPONSE TIME & ACKNOWLEDGMENT AUDIT\n## 3. UNACKNOWLEDGED ALARM RISK EXPOSURE\n## 4. RECOMMENDED WORKLOAD BALANCE ADJUSTMENTS"
    },
    "alarm_kpi": {
        "filter_func": lambda x: x,
        "role": "Operations Manager and Shift Performance Auditor checking plant operational health.",
        "headers": "## 1. EXECUTIVE METRIC AUDIT\n## 2. PARETO ALARM FREQUENCY & ROOT-CAUSE ANALYSIS\n## 3. ENGINEERING SUGGESTIONS & MITIGATION PROTOCOLS\n## 4. CHRONOLOGICAL EVENT LOG FLOW"
    }
}

# =====================================================================
# MAIN FLASK API ROUTE
# =====================================================================

@app.route('/api/audit', methods=['POST'])
def audit():
    try:
        # 1. Capture raw input data string to calculate exact token sizes
        raw_data_str = request.get_data(as_text=True)
        
        if not raw_data_str:
            return jsonify({"status": "error", "message": "Empty payload"}), 400
            
        # 2. Tokenize using the Hugging Face tokenizer
        tokens = tokenizer.encode(raw_data_str, add_special_tokens=False)
        token_count = len(tokens)
        print(f"Received payload. Current Token Count: {token_count}")

        # 3. Apply window limit check
        WINDOW_LIMIT = 30000
        if token_count > WINDOW_LIMIT:
            return jsonify({
                "status": "error", 
                "message": f"Size of {token_count} tokens exceeds window limit of {WINDOW_LIMIT}."
            }), 400

        # Safe parsing after passing the token check
        data = json.loads(raw_data_str)
    except json.JSONDecodeError:
        return jsonify({"status": "error", "message": "Invalid JSON format"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Initial ingestion failure: {str(e)}"}), 500

    # 4. Extract payloads and parameters
    user_question = data.get("question")
    input_data = data.get("input_data") or data.get("inputdata.json") or data
    
    dashboard_type = data.get("dashboard_type") or data.get("page_id") or "summary"
    dashboard_type = str(dashboard_type).lower().strip()

    if not user_question:
        return jsonify({"error": "Missing 'question' parameter in payload body."}), 400

    # Fallback profile setup if profile name is unmapped
    if dashboard_type not in DASHBOARD_MAP:
        config = {
            "filter_func": lambda x: x,
            "role": "Automation Quality Control and Process Performance Auditor.",
            "headers": "## 1. EXECUTIVE METRIC AUDIT\n## 2. PARETO ALARM FREQUENCY & ROOT-CAUSE ANALYSIS\n## 3. ENGINEERING SUGGESTIONS & MITIGATION PROTOCOLS\n## 4. CHRONOLOGICAL EVENT LOG FLOW"
        }
    else:
        config = DASHBOARD_MAP[dashboard_type]
    
    # Process dashboard context data filtering
    try:
        cleaned_data = config["filter_func"](input_data)
        filtered_context = json.dumps(cleaned_data, indent=2)
    except Exception as e:
        filtered_context = json.dumps(input_data, indent=2)

    # Build prompt for LLM execution
    system_prompt = (
        f"You are an {config['role']}\n"
        f"STRICT INSTRUCTION: Look ONLY at the actual numbers, totals, and timestamps provided in the [FRESH DATA PAYLOAD] below. "
        "Do NOT claim the payload is empty or void if metrics are present under any custom key structures.\n\n"
        f"STRUCTURE YOUR RESPONSE INTO THESE EXACT SECTIONS:\n{config['headers']}\n\n"
        "STRICT VISUAL RULE: Do not use markdown grid tables. Use text paragraphs, bold headers, and bullet points."
    )

    dynamic_prompt = (
        f"{system_prompt}\n\n"
        f"--- CURRENT TURN INPUTS ---\n"
        f"[DASHBOARD CONTEXT PROFILE]: {dashboard_type.upper()}\n"
        f"[FRESH DATA PAYLOAD FOR THIS TURN]:\n{filtered_context}\n\n"
        f"Current User Question: {user_question}"
    )

    # 5. Execute Generator Client Request
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=dynamic_prompt
        )

        report_filename = f"latest_{dashboard_type}_audit_report.md"
        with open(report_filename, "w", encoding="utf-8") as report_file:
            report_file.write(response.text)

        return jsonify({
            "status": "Success",
            "page_id": dashboard_type,
            "question": user_question,
            "input": input_data,
            "tokens_used": token_count,
            "chat_response": response.text,
            "report_saved_to": report_filename
        }), 200

    except Exception as e:
        return jsonify({"error": f"Processing Failure Exception: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)