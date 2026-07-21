# MAF AgenticAI — Cloud Incident Triage PoC

Azure-only AI agent that triages cloud incidents end-to-end using  
**Microsoft Agent Framework (MAF)** + **Azure AI Foundry (GPT-4o)**.

## Architecture

```
Azure Monitor Alert
       │
       ▼
┌─────────────────────────────────────────────────────┐
│  IncidentTriageAgent  (agents/incident_triage_agent) │
│                                                      │
│  OBSERVE ──► Log Analytics + Resource Graph          │
│  ANALYSE ──► Foundry LLM (GPT-4o) ──► JSON plan     │
│  APPROVE ──► Human-in-the-loop gate                  │
│  ACT     ──► RemediationTool (VM/App restart,        │
│              Runbook, scale-out, notify)              │
│  AUDIT   ──► Structured result log                   │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
MAF_AgenticAI/
├── agents/
│   └── incident_triage_agent.py   # MAF orchestration loop
├── llm/
│   └── foundry_client.py          # Azure AI Foundry LLM adapter
├── tools/
│   ├── log_analytics_tool.py      # Log Analytics context queries
│   ├── resource_graph_tool.py     # Resource Graph state queries
│   └── remediation_tool.py        # Safe remediation actions
├── models/
│   ├── alert.py                   # Azure Monitor alert model
│   └── remediation_plan.py        # Structured LLM plan model
├── approval/
│   └── human_approval.py          # Human-in-the-loop approval gate
├── config/
│   └── settings.py                # Central config from env vars
├── tests/
│   ├── test_models.py             # Unit tests (no Azure creds needed)
│   └── test_agent.py              # Agent integration tests (mocked)
├── main.py                        # CLI entry point
├── requirements.txt
└── .env.example
```

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Azure CLI logged in (`az login`) or Managed Identity
- Azure AI Foundry project with a GPT-4o deployment

### 2. Install dependencies
```bash
cd "Documents/VSCODE Folder/My_Project/MAF_AgenticAI"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — set AZURE_AI_PROJECT_ENDPOINT, LOG_ANALYTICS_WORKSPACE_ID, etc.
```

### 4. Run tests (no Azure credentials needed)
```bash
pytest tests/ -v
```

### 5. Run with demo alert (auto-approval mode)
```bash
APPROVAL_MODE=auto python main.py --demo
```

### 6. Run with a real alert file
```bash
python main.py --alert path/to/alert.json
```

## MAF ↔ Foundry Integration Map

| MAF Layer | Azure Service |
|-----------|--------------|
| Agent orchestration | `IncidentTriageAgent` (Python) |
| LLM inference | Azure AI Foundry — GPT-4o |
| Context / memory | Azure Log Analytics + Resource Graph |
| Tool execution | Azure Automation Runbooks / mgmt SDKs |
| Auth | `DefaultAzureCredential` (Managed Identity) |
| Observability | Azure App Insights / stdout logs |
| Approval workflow | Console (PoC) → Teams webhook / Logic Apps (prod) |

## Deployment (Azure Functions)
The `main.py` `run_triage()` function can be wrapped as an Azure Function HTTP trigger.
See `azure_function_app/` (planned) for the Function wrapper.

## Security Notes
- All credentials use `DefaultAzureCredential` — no secrets in code.
- Remediation actions are idempotent and non-destructive by design.
- `safe_to_automate=False` actions always require human approval before execution.

