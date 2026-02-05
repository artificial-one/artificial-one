# artificial.one – VPS Deploy Checklist

Go from empty VPS to system running automatically. Do steps in order. Zero guesswork.

---

## 1. API keys and where to get them

| Key / credential | Where to get it | Used by |
|-----------------|----------------|---------|
| **Anthropic API key** | https://console.anthropic.com → API Keys | Agent 1, 2, 4, 7 (Claude). Same key works for Sonnet and Haiku; model is specified per API call. |
| **Google Sheets OAuth** | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client (Desktop) | All agents that read/write sheets |
| **Google Sheet ID** | From the sheet URL: `https://docs.google.com/spreadsheets/d/<THIS_IS_THE_ID>/edit` | All agents |
| **Beehiiv API key** | Beehiiv Dashboard → Settings → API | Agent 7 |
| **Beehiiv Publication ID** | Beehiiv Dashboard → Publication settings | Agent 7 |
| **Product Hunt API key** | https://api.producthunt.com/v2/dashboard | Agent 1 (A1_Scrape_ProductHunt) |
| **GitHub token** (optional) | GitHub → Settings → Developer settings → Personal access tokens | Agent 5 (if deploy pushes to GitHub) |
| **Google Search Console** | GSC property verified; service account with "Full" access | Agent 6 (agent6_gsc_monitor.py) |

Create the keys before VPS setup. Store them somewhere safe; you’ll add them to n8n and env later.

---

## 2. VPS setup (copy-paste)

Assumes Ubuntu 22.04. Run as root or with sudo.

```bash
# Update system
apt update && apt upgrade -y

# Create app user (optional but recommended)
adduser n8n --disabled-password --gecos ""
usermod -aG sudo n8n

# Create directories
mkdir -p /root/n8n/scripts
mkdir -p /temp-content
mkdir -p /approved-content
# If using a separate repo clone:
mkdir -p /root/artificial-one
```

Set ownership if you use the `n8n` user:

```bash
chown -R n8n:n8n /root/n8n /temp-content /approved-content
```

---

## 3. Docker and n8n (copy-paste)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Create n8n data directory
mkdir -p /root/n8n-data

# Run n8n (persistent). Copy Claude/.env.example to .env, fill in values, then:
docker run -d \
  --name n8n \
  --restart unless-stopped \
  -p 5678:5678 \
  -v /root/n8n-data:/home/node/.n8n \
  -v /root/n8n/scripts:/root/n8n/scripts:ro \
  -v /temp-content:/temp-content \
  -v /approved-content:/approved-content \
  -e N8N_HOST=0.0.0.0 \
  -e GENERIC_TIMEZONE=UTC \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e GOOGLE_SHEET_ID="${GOOGLE_SHEET_ID}" \
  -e BEEHIIV_API_KEY="${BEEHIIV_API_KEY}" \
  -e BEEHIIV_PUBLICATION_ID="${BEEHIIV_PUBLICATION_ID}" \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  -e GITHUB_REPO="${GITHUB_REPO}" \
  -e SITE_URL="${SITE_URL}" \
  -e REPO_DIR="${REPO_DIR}" \
  -e TEMP_CONTENT="${TEMP_CONTENT}" \
  -e APPROVED_CONTENT="${APPROVED_CONTENT}" \
  -e SCRIPTS_DIR="${SCRIPTS_DIR}" \
  -e PRODUCTHUNT_API_KEY="${PRODUCTHUNT_API_KEY}" \
  -e GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS}" \
  n8nio/n8n:latest
```

**Env vars:** Copy `Claude/.env.example` to `.env` in the directory where you run `docker run`, fill in your values, and the `-e` flags above will pass them into the n8n container. The workflow references them as `{{ $env.ANTHROPIC_API_KEY }}` etc.

Open: `http://YOUR_VPS_IP:5678`. Create admin user when prompted.

---

## 4. Upload files to VPS

From your local machine (paths assume project root is `artificial.one`):

```bash
# Set your VPS IP
VPS=root@YOUR_VPS_IP

# Scripts and config
scp Claude/agent3_quality_assurance.py $VPS:/root/n8n/scripts/
scp Claude/agent6_gsc_monitor.py $VPS:/root/n8n/scripts/
scp Claude/deploy.sh $VPS:/root/n8n/scripts/
scp Claude/update_sitemap.py $VPS:/root/n8n/scripts/

# Make scripts executable
ssh $VPS "chmod +x /root/n8n/scripts/*.py /root/n8n/scripts/deploy.sh"
```

Install Python deps on VPS:

```bash
ssh $VPS "apt install -y python3 python3-pip && pip3 install beautifulsoup4 anthropic requests python-dotenv"
```

If the repo is on the VPS (for deploy):

```bash
# Option A: clone on VPS
ssh $VPS "cd /root && git clone https://github.com/YOUR_USER/artificial.one.git artificial-one"

# Option B: rsync from local
rsync -avz --exclude node_modules --exclude .git . $VPS:/root/artificial-one/
```

Set `REPO_DIR` in env or in `deploy.sh` to the repo path on the VPS (e.g. `/root/artificial-one`).

---

## 5. n8n workflow import

1. In n8n: **Workflows** → **Import from File**.
2. Select `Claude/n8n_workflow.json`.
3. After import:
   - Open **Settings** (gear) → **Variables** and add (if not using Docker env):
     - `GOOGLE_SHEET_ID`
     - `ANTHROPIC_API_KEY`
     - `PRODUCTHUNT_API_KEY`
     - `TEMP_CONTENT` = `/temp-content`
     - `APPROVED_CONTENT` = `/approved-content`
     - `SCRIPTS_DIR` = `/root/n8n/scripts`
     - `REPO_DIR` = `/root/artificial-one`
     - `BEEHIIV_PUBLICATION_ID`
   - In each node that uses credentials, set:
     - **Google Sheets**: your OAuth client (see Google Sheets setup below).
     - **Anthropic**: Header Auth, name e.g. `x-api-key`, value = your Anthropic key.
     - **Beehiiv**: Header Auth for Agent 7 (Beehiiv API key).
4. Save the workflow.
5. **Activate** the workflow (toggle top right) so schedules run.

---

## 6. Google Sheets setup

1. Create a Google Sheet. Name it e.g. `artificial.one Automation`.
2. Create these sheets (tabs) with exact names:
   - **MASTER_TOOLS_DB** – columns: Tool Name, Category, Priority, Description, Status, Date Added (add Tool_Slug if Agent 2 uses it).
   - **NEEDS_FIXING** – columns: File, Issues, Attempts.
  - **REVENUE_DASHBOARD** – columns: Date, Event, Pages Published (or Notes / Subject); for Agent 6 add: Pages Indexed, Clicks, Impressions, CTR (or use a separate GSC row with Event = "GSC Hourly" and metrics in Notes).
  - **GSC_IMPROVEMENTS** – columns: Date, Type (or Issue Type), Priority, Issue (or Recommendation), Action, Status.
3. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.
4. In n8n: **Credentials** → **Add credential** → **Google Sheets OAuth2**. Follow the wizard (Google Cloud project, OAuth consent, client ID/secret). Test and save.
5. Set `GOOGLE_SHEET_ID` in n8n variables (or in Docker env) to that Sheet ID.

---

## Agent 6: Google Search Console Monitoring

**Purpose:** Track indexing, request indexing for new pages, identify winning content.

**Schedule:** Runs hourly (on the :05 mark — cron `5 * * * *`).

**What it does:**
1. Runs `agent6_gsc_monitor.py`, which calls the GSC API.
2. Logs metrics (indexed pages, clicks, impressions, CTR) to **REVENUE_DASHBOARD**.
3. Saves improvement recommendations to **GSC_IMPROVEMENTS** sheet.
4. **Feedback loop:** If tool reviews perform better than comparisons/blogs, it automatically boosts priority of PENDING_CONTENT tools in **MASTER_TOOLS_DB** so Agent 2 creates more of what’s working.

**Files used:**
- `/scripts/agent6_gsc_monitor.py` (Python script)
- `/scripts/gsc_report.json` (output from script)
- Google Sheets: **REVENUE_DASHBOARD**, **GSC_IMPROVEMENTS**, **MASTER_TOOLS_DB**

**Setup requirements:**
- Google Search Console property verified for artificial.one (or your SITE_URL).
- Service account added as user in GSC with **Full** permissions.
- Service account JSON in `/scripts/` (e.g. `gsc-service-account.json`).
- `GOOGLE_APPLICATION_CREDENTIALS` env var set (path to that JSON). Pass it into the Docker container with `-e GOOGLE_APPLICATION_CREDENTIALS=/root/n8n/scripts/gsc-service-account.json` and mount the file.

**How the winning content logic works:**
- The script analyzes top 10 performing pages (by clicks).
- It counts page types: `/tools/` vs `/compare/` vs `/best/` (categories).
- Whichever type has the most pages in the top 10 = winning type.
- The workflow boosts priority of PENDING_CONTENT tools (if `tool_reviews` win).
- This creates a closed feedback loop: GSC data → content strategy.

**Example:**  
If top 10 pages = 7 tool reviews + 2 comparisons + 1 category → `tool_reviews` win → workflow boosts up to 10 PENDING_CONTENT tools (Priority +2, cap 10) → Agent 2 picks these first next run → more tool reviews get created.

---

## 7. Test each agent manually

- **Agent 1 (Discovery)**  
  - Execute **A1_Trigger_6AM** (or run from “Execute Workflow” with no input).  
  - Check: A1_Read_Existing_Tools runs, A1_Append_MASTER_TOOLS_DB appends new rows (if any).  
  - Ensure MASTER_TOOLS_DB has at least columns used by the append node.

- **Agent 2 (Content)**  
  - Put at least one row in MASTER_TOOLS_DB with Status = `PENDING_CONTENT` and Tool_Slug (or tool_slug).  
  - Run from **A2_Trigger_8AM** or **A2_Read_Pending_Tools**.  
  - Check: HTML file appears under `/temp-content/tools/<slug>.html`.

- **Agent 3 (QA)**  
  - Run **A3_Run_QA_Script** (or run `python3 agent3_quality_assurance.py` on VPS).  
  - Check: `SCRIPTS_DIR/qa_results.json` exists and has pass/fail per file.

- **Agent 4 (Fix loop)**  
  - Triggered only when Agent 3 routes to “fail”.  
  - Manually run from **A4_Expand_Failed** with one failed item in input (or run full flow from A2 with one failing page).  
  - Check: Fix nodes run, file is written with `writeData`, re-QA runs, APPROVED_PAGES.txt or NEEDS_FIXING updated.

- **Agent 5 (Deploy)**  
  - Add a path (e.g. `tools/test.html`) to `/approved-content/APPROVED_PAGES.txt` and ensure that file exists under `/temp-content/tools/test.html`.  
  - Run **A5_Run_Deploy**.  
  - Check: File copied to `REPO_DIR`, REVENUE_DASHBOARD row added.

- **Agent 6 (GSC)**  
  - Run **A6_Run_GSC_Monitor** (ensure `GOOGLE_APPLICATION_CREDENTIALS` and `SITE_URL` are set).  
  - Check: `SCRIPTS_DIR/gsc_report.json` exists; **A6_Extract_Metrics** → **A6_Log_To_Dashboard** (REVENUE_DASHBOARD); **A6_Check_Recommendations** → **A6_Process_Recommendations** → **A6_Log_Recommendation** (GSC_IMPROVEMENTS); if winning content = tool_reviews, **A6_Adjust_Priorities** → **A6_Read_Master_DB** → **A6_Boost_Tool_Priorities** → **A6_Update_Priorities** → **A6_Log_Priority_Changes**.

- **Agent 7 (Email)**  
  - Run from **A7_Read_Yesterday_Tools** (ensure MASTER_TOOLS_DB has some rows).  
  - Check: **A7_Parse_Email_Response** gets subject/html_content, **A7_Beehiiv_Send** returns 2xx, REVENUE_DASHBOARD logged.

---

## 8. Enable automated schedules

1. In n8n workflow, confirm trigger nodes:
   - **A1_Trigger_6AM** – cron `0 6 * * *` (6:00 daily).
   - **A2_Trigger_8AM** – cron `0 8 * * *` (8:00 daily).
   - **A6_Trigger_Hourly** – cron `5 * * * *` (every hour at :05).
   - **A7_Trigger_9AM** – cron `0 9 * * *` (9:00 daily).
2. Workflow must be **Active** (toggle on).
3. In **Settings** → **Execution settings**, set timezone if needed (e.g. `America/New_York`).
4. Optional: set **Save Execution Progress** and **Save Manual Executions** for debugging.

---

## 9. After first 24 hours – what to check

- [ ] **Agent 1**: New rows in MASTER_TOOLS_DB (if new tools were found).
- [ ] **Agent 2**: New HTML files under `/temp-content/tools/` for PENDING_CONTENT rows.
- [ ] **Agent 3**: `qa_results.json` updated after each A2 run; pass/fail counts make sense.
- [ ] **Agent 4**: If there were failures, fix loop ran; APPROVED_PAGES or NEEDS_FIXING updated.
- [ ] **Agent 5**: Deploy ran when there were approved pages; files in repo and REVENUE_DASHBOARD logged.
- [ ] **Agent 6**: GSC_IMPROVEMENTS has new rows (if script and report exist).
- [ ] **Agent 7**: One email sent; REVENUE_DASHBOARD has “Email Sent” row.
- [ ] No repeated errors in n8n **Executions**; fix any red nodes (credentials, paths, or missing env).

---

## 10. Troubleshooting

| Problem | Check |
|--------|--------|
| “File not found” in A3/A4 | `SCRIPTS_DIR`, `TEMP_CONTENT`, and `APPROVED_CONTENT` match paths on VPS; scripts and dirs exist. |
| Write node errors (A2, A4_Save_HTML) | Preceding **Prepare_Write** node sets `writeData.data` and `writeData.fileName`; readWriteFile uses `fileName` = `$json.writeData.fileName` and `dataPropertyName` = `writeData.data`. |
| Google Sheets “Permission denied” | Reconnect Google Sheets OAuth; ensure sheet is shared with the same Google account. |
| Claude “Unauthorized” | Anthropic key is correct and has credits; header name/value match what n8n expects. |
| Beehiiv 4xx | Publication ID and API key; payload has `subject`, `html_content`, `send_time`. |
| deploy.sh fails | `REPO_DIR`, `TEMP_CONTENT_DIR`, `APPROVED_FILE` set; APPROVED_PAGES.txt has one path per line; source files exist under temp-content. |
| A6_Update_Priorities fails | Ensure MASTER_TOOLS_DB has column "Tool Name"; in n8n Google Sheets Update node, set lookup column to "Tool Name" and map Priority so the node can find the row to update. |

---

---

## 11. Monthly cost estimate

| What | Cost | Details |
|------|------|---------|
| VPS (DigitalOcean) | $24 | 4GB RAM, runs n8n 24/7 |
| Claude API – Sonnet | ~$24 | 35 tool reviews/week |
| Claude API – Haiku | ~$2 | Comparisons, blogs, emails, fixes |
| **Total** | **~$50/month** | |

**Sonnet breakdown**

- 35 reviews/week × 1 call each = 35 calls/week  
- ~7,000 tokens per call ≈ 245K tokens/week ≈ 1.05M tokens/month  
- Input (~30%): 315K × $3/1M ≈ $0.95  
- Output (~70%): 735K × $15/1M ≈ $11  
- Monthly Sonnet: ~$12–24 (depends on length)

**Haiku breakdown**

- ~15 pages/week (comparisons, blogs) + emails + fix loop ≈ 15–20 calls/week  
- ~3–5K tokens per call ≈ 75K tokens/week ≈ 325K tokens/month  
- Haiku is ~20× cheaper than Sonnet  
- Monthly Haiku: ~$2

*Actual costs depend on page length and research data size. Monitor via Anthropic console.*

---

**Last updated:** 2026-02-01. Paths and sheet names match `config.js` and `n8n_workflow.json`.
