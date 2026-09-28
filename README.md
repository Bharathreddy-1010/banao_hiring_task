# Vireo Audio — AI Support Desk & SLA Defense Engine

An intelligent support operations and SLA recovery system built for Vireo Audio (Bengaluru). It addresses the root cause of first-response SLA breaches, prevents wrongful blame on morning agents, and provides automated, context-aware overnight triage and immediate first response.

---

## 🚀 Quick Start (Clean Machine in Under 60 Seconds)

### 1. Clone & Set Up Environment
```bash
# 1. Clone repository
git clone https://github.com/Bharathreddy-1010/banao_hiring_task.git
cd banao_hiring_task

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install lightweight dependencies
pip install -r requirements.txt
```

### 2. Configure API Key
Create a `.env` file in the root directory:
```bash
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
```
*(Note: If no API key is provided, the tool gracefully falls back to deterministic heuristic parsing).*

---

## 🛠 Usage & Core Commands

### 1. Executive SLA Root-Cause Audit
Disproves the naive "agent fault" hypothesis, reveals the unstaffed night shift cliff, and exposes unfair blame attribution to morning shift agents.
```bash
python app.py audit
```

### 2. Overnight Triage & Automated First-Responder Demo
Simulates real incoming overnight tickets (22:00 to 06:00 IST), queries `orders.csv`, `products.csv`, and `customers.csv`, flags policy violations (e.g., Section 5 double refunds), and drafts instant (<30 sec) first responses to halt SLA breach clocks.
```bash
python app.py triage --limit 5
```

### 3. Evaluation Benchmark Suite
Evaluates category classification accuracy, entity extraction, and latency against a benchmark sample from `tickets.csv`.
```bash
python app.py evaluate --sample 30
```

### 4. Interactive Live Test Prompt
Test any custom customer message in real time to see intent classification, entity extraction, VIP Care+ lookup, and auto-generated response:
```bash
python app.py interactive
```

---

## 📊 Key Findings & Business Impact

| Metric | Pre-July 2025 (Staffed Night) | Post-July 2025 (Unstaffed Night) | Target with AI Defense Engine |
| :--- | :--- | :--- | :--- |
| **Overall SLA Breach Rate** | **9.3%** | **25.0%** | **< 8.5%** |
| **Chat SLA Breach Rate** | **8.5%** | **32.5% (100% Overnight)** | **< 7.5%** |
| **Median Night Chat Wait** | **4.0 minutes** | **432.0 minutes (7.2 hrs)** | **< 1.0 minute** |
| **Quarterly SLA Credit Bleed**| **~Rs 37,000** | **~Rs 2,00,000** | **< Rs 55,000** |
| **Average CSAT Rating** | **3.53 / 5.0** | **2.79 / 5.0** | **3.50+ / 5.0** |

**Net Quarterly Financial Recovery:** **Rs 1,47,000 per quarter (~Rs 5,88,000 annually)** in direct Rs 350 SLA breach credits saved at Vireo's volume of ~650 tickets/week.

---

## 🏗 System Architecture & Project Layout

* **`data_given/`**: Stores input datasets (`tickets.csv`, `orders.csv`, `customers.csv`, `products.csv`, `agents.csv`, `support-policy.pdf`).
* **`src/data_loader.py`**: Ingests datasets from `data_given/`, deduplicates legacy vs helpdesk records, handles UTC to IST (+5:30) conversion, and assigns shift schedules.
* **`src/sla_audit.py`**: Computes accurate queue wait times, tracks quarterly breach trajectories, and generates the attribution report exonerating morning agents.
* **`src/triage_agent.py`**: Intercepts customer inquiries, extracts Order IDs (`VRxxxxxx`) and SKU details, enriches data via reference catalogs, verifies Section 5 double-dipping policy rules, and generates human-grade first responses.
* **`src/evaluator.py`**: Measures precision, recall, latency, and error failure modes.
* **`app.py`**: Unified command-line interface.
