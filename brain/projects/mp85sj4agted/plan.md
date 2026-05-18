# Power BI MCP Server for NORDE — Project Plan (R3 Final)

## Objective
Integrate Power BI read-only access for the NORDE FINANCIALS HORIZON dataset into the existing Brain MCP server, exposing workspace 971b901d / report e62727f8 via 5 tool functions.

## Confirmed Spec
- **Workspace:** 971b901d-13b2-415f-93a6-7a39a4c03ea7
- **Report:** e62727f8-0da5-4ef7-98f0-983d4666c3b9
- **Dataset:** FINANCIALS HORIZON (full access)
- **Access mode:** Read-only
- **Integration target:** `/opt/brain-viz/mcp-servers/whatsapp/server.py`
- **Auth:** Manual bearer token via env var (no MSAL, no Azure AD app)

## Validated Architecture (code-verified against server.py)

### File: `/opt/brain-viz/mcp-servers/whatsapp/server.py` (789 lines)

**Insertion Point 1 — Power BI module (after line 27, before `_dashboard_url`):**
```python
# --- Power BI Module ---
POWERBI_TOKEN = os.environ.get("POWERBI_TOKEN", "")
POWERBI_WORKSPACE = os.environ.get("POWERBI_WORKSPACE_ID", "971b901d-13b2-415f-93a6-7a39a4c03ea7")
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"

def call_powerbi(path: str, method: str = "GET", data: dict | None = None) -> dict:
    """Call Power BI REST API. Returns parsed JSON or error dict."""
    if not POWERBI_TOKEN:
        return {"error": "POWERBI_TOKEN not set. See project plan for setup instructions."}
    url = f"{POWERBI_API}/groups/{POWERBI_WORKSPACE}/{path}"
    headers = {
        "Authorization": f"Bearer {POWERBI_TOKEN}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, body, headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.readable() else ""
        if e.code == 429:
            return {"error": "Power BI rate limit hit (200 req/hr). Retry later.", "status": 429}
        if e.code == 403:
            return {"error": "Token expired or insufficient permissions. Get a new bearer token.", "status": 403}
        return {"error": f"Power BI API error {e.code}: {err_body}", "status": e.code}
    except Exception as e:
        return {"error": str(e)}
```

**Insertion Point 2 — Tool definitions (after line 387, before Gmail loader at line 392):**
```python
# --- Power BI Tools ---
TOOLS.extend([
    {
        "name": "powerbi_list_datasets",
        "description": "List all datasets in the NORDE Power BI workspace.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "powerbi_list_tables",
        "description": "List tables and columns in a Power BI dataset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset ID from powerbi_list_datasets"},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "powerbi_run_dax",
        "description": "Execute a DAX query against a Power BI dataset. Returns result rows as JSON.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset ID"},
                "dax_expression": {"type": "string", "description": "DAX query (e.g. EVALUATE SUMMARIZE(...))"},
            },
            "required": ["dataset_id", "dax_expression"],
        },
    },
    {
        "name": "powerbi_get_report_pages",
        "description": "List pages in a Power BI report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string", "description": "Report ID (default: NORDE report)"},
            },
        },
    },
    {
        "name": "powerbi_get_refresh_history",
        "description": "Get refresh history for a Power BI dataset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset ID"},
            },
            "required": ["dataset_id"],
        },
    },
])
```

**Insertion Point 3 — Tool dispatch (before `elif tool_name in GMAIL_TOOL_NAMES:` at line 704):**
```python
        # --- Power BI dispatch ---
        elif tool_name == "powerbi_list_datasets":
            result = call_powerbi("datasets")

        elif tool_name == "powerbi_list_tables":
            result = call_powerbi(f"datasets/{args['dataset_id']}/tables")

        elif tool_name == "powerbi_run_dax":
            payload = {
                "queries": [{"query": args["dax_expression"]}],
                "serializerSettings": {"includeNulls": True}
            }
            result = call_powerbi(f"datasets/{args['dataset_id']}/executeQueries", method="POST", data=payload)

        elif tool_name == "powerbi_get_report_pages":
            rid = args.get("report_id", "e62727f8-0da5-4ef7-98f0-983d4666c3b9")
            result = call_powerbi(f"reports/{rid}/pages")

        elif tool_name == "powerbi_get_refresh_history":
            result = call_powerbi(f"datasets/{args['dataset_id']}/refreshes")
```

### File: `/opt/brain-viz/docker-compose.yml` (line 72-76)

Add to mcp-whatsapp environment block:
```yaml
      - POWERBI_TOKEN=${POWERBI_TOKEN:-}
      - POWERBI_WORKSPACE_ID=${POWERBI_WORKSPACE_ID:-971b901d-13b2-415f-93a6-7a39a4c03ea7}
```

### File: `/opt/brain-viz/.env`

Add:
```
POWERBI_TOKEN=          # Justs pastes bearer token here
```

## Change Summary
- **server.py**: +~95 lines (1 helper function, 5 tool defs via TOOLS.extend, 5 elif branches)
- **docker-compose.yml**: +2 env vars
- **.env**: +1 variable placeholder
- **No new files. No new dependencies. No Dockerfile changes.**

## Deployment
1. Justs provides bearer token (instructions already sent via COMS)
2. I edit the 3 files above
3. `docker compose up -d --build mcp-whatsapp`
4. Test: call `powerbi_list_datasets` from Claude Code session
5. If token works → discover tables, run sample DAX, document schema

## Blocking On
Bearer token from Justs. Everything else is ready to execute.

## Future (post-MVP)
- MSAL service principal for auto-refresh
- Cached schema discovery
- DAX query templates for common FINANCIALS HORIZON queries