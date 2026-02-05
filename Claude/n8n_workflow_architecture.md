# n8n Workflow Architecture
# Complete automation system for artificial.one

## Overview
This document describes the n8n workflow structure. The actual workflow JSON
will be created separately and can be imported into n8n.

---

## WORKFLOW STRUCTURE

### Workflow 1: Main Content Generation (Daily at 8 AM)

**Trigger:** Cron - Daily at 8:00 AM

**Flow:**

1. **Read Pending Tools** (Google Sheets node)
   - Sheet: MASTER_TOOLS_DB
   - Filter: Status = "PENDING_CONTENT"
   - Limit: 20 tools

2. **For Each Tool** (Loop node)
   
   a. **Generate Tool Review** (HTTP Request to Claude API)
      - Endpoint: https://api.anthropic.com/v1/messages
      - Method: POST
      - Headers: x-api-key: {{$env.ANTHROPIC_API_KEY}}
      - Body: {
          model: "claude-sonnet-4-20250514",
          max_tokens: 8000,
          messages: [{
            role: "user",
            content: [TOOL_REVIEW_PROMPT with tool data]
          }]
        }
   
   b. **Save Review HTML** (Write File node)
      - Path: /temp-content/tools/{{toolName}}-review.html
   
   c. **Generate 3 Comparisons** (Loop 3 times)
      - HTTP Request to Claude API for each comparison
      - Save to /temp-content/comparisons/
   
   d. **Generate Alternative Page** (if high-priority category)
      - HTTP Request to Claude API
      - Save to /temp-content/alternatives/
   
   e. **Update Tool Status** (Google Sheets node)
      - Update row: Status = "CONTENT_CREATED"

3. **Generate Daily Blog Post** (HTTP Request to Claude API)
   - Prompt: Weekly roundup of tools added
   - Save to /temp-content/blog/

4. **Update Category Pages** (For each affected category)
   - Read existing category page
   - Generate updates with Claude
   - Save to /temp-content/best/

5. **Trigger QA Workflow** (Webhook)
   - Send signal to QA workflow to start testing

---

### Workflow 2: Quality Assurance (Triggered after content generation)

**Trigger:** Webhook from Workflow 1

**Flow:**

1. **Run QA Script** (Execute Command node)
   - Command: python3 /scripts/agent3_quality_assurance.py
   - Wait for completion

2. **Read QA Results** (Read File node)
   - File: /scripts/qa_results.json

3. **Split Results** (Switch node)
   - Route PASS to approval
   - Route FAIL to fix workflow

4. **For PASS Pages** (Filter + Move)
   - Append to /approved-content/APPROVED_PAGES.txt

5. **For FAIL Pages** (Write to Google Sheets)
   - Sheet: NEEDS_FIXING
   - Include issues and suggestions

6. **If any failures** (Conditional)
   - Trigger Fix Workflow

7. **If all pass or after fixes** (Conditional)
   - Trigger Deployment Workflow

---

### Workflow 3: Fix & Enhance (Triggered by QA failures)

**Trigger:** Webhook from QA Workflow

**Flow:**

1. **Read Failed Pages** (Google Sheets node)
   - Sheet: NEEDS_FIXING
   - Filter: Attempts < 2

2. **For Each Failed Page** (Loop)
   
   a. **Read Original HTML** (Read File node)
   
   b. **Generate Fix** (HTTP Request to Claude API)
      - Prompt: Fix based on specific issues
      - Include original HTML
      - Include QA feedback
   
   c. **Save Fixed HTML** (Write File node)
      - Overwrite original in /temp-content/
   
   d. **Re-run QA on Fixed Page** (Execute Command)
      - Run QA script on single file
   
   e. **Check Result** (Switch node)
      - If PASS: Move to approved
      - If FAIL & attempts < 2: Increment attempts, try again
      - If FAIL & attempts >= 2: Flag for human review

3. **Update NEEDS_FIXING Sheet**
   - Mark fixed pages as resolved

4. **Trigger Deployment** (Webhook)
   - When all fixes complete

---

### Workflow 4: Staged Deployment (Triggered after QA/Fix)

**Trigger:** Webhook from QA or Fix Workflow

**Flow:**

1. **Check Approved Pages** (Read File node)
   - File: /approved-content/APPROVED_PAGES.txt
   - Count pages

2. **If pages exist** (Conditional)
   
   a. **Run Deployment Script** (Execute Command node)
      - Command: bash /scripts/deploy.sh
      - This script handles:
        - Staged commits (4 batches throughout day)
        - Sitemap updates
        - Git push
        - Archiving deployed files

3. **Log Deployment** (Google Sheets node)
   - Sheet: REVENUE_DASHBOARD
   - Update: Pages published, date

4. **Trigger GSC Monitoring** (Webhook)
   - Signal to check indexing

---

### Workflow 5: GSC Monitoring & Optimization (Hourly)

**Trigger:** Cron - Every hour

**Flow:**

1. **Run GSC Monitor Script** (Execute Command node)
   - Command: python3 /scripts/agent6_gsc_monitor.py

2. **Read GSC Report** (Read File node)
   - File: /scripts/gsc_report.json

3. **Update Dashboard** (Google Sheets node)
   - Sheet: REVENUE_DASHBOARD
   - Update: Indexed pages, clicks, impressions

4. **Check for Improvements** (Process JSON)
   - Extract recommendations from report

5. **Save Improvements** (Google Sheets node)
   - Sheet: GSC_IMPROVEMENTS
   - Log recommendations

6. **If winning patterns found** (Conditional)
   - Extract content types that perform best
   - Update priorities in MASTER_TOOLS_DB
   - Queue similar content for generation

---

### Workflow 6: Email Marketing (Daily at 9 AM)

**Trigger:** Cron - Daily at 9:00 AM

**Flow:**

1. **Get Yesterday's New Tools** (Google Sheets node)
   - Sheet: MASTER_TOOLS_DB
   - Filter: Date Added = yesterday
   - Limit: 10 best

2. **Generate Email Content** (HTTP Request to Claude API)
   - Prompt: Daily deal alert template
   - Include top 3 tools
   - Generate subject line variants (A/B test)

3. **Format Email HTML** (Function node)
   - Clean HTML for email
   - Add unsubscribe link
   - Add tracking pixels

4. **Send via Beehiiv** (HTTP Request to Beehiiv API)
   - Endpoint: https://api.beehiiv.com/v2/emails
   - Headers: Authorization: Bearer {{$env.BEEHIIV_API_KEY}}
   - Body: {
       publication_id: "...",
       subject: "...",
       html_content: "...",
       send_time: "now"
     }

5. **Log Email Sent** (Google Sheets node)
   - Track: Date, subject, tools featured, send count

---

### Workflow 7: Tool Discovery (Daily at 6 AM)

**Trigger:** Cron - Daily at 6:00 AM

**Flow:**

1. **Scrape AppSumo** (HTTP Request node)
   - URL: https://appsumo.com/collections/all/
   - Extract new deals

2. **Scrape Product Hunt** (HTTP Request node)
   - URL: https://api.producthunt.com/v2/api/graphql
   - Get today's launches

3. **Scrape BetaList** (HTTP Request)
   - Get new startups

4. **For Each Found Tool** (Loop)
   
   a. **Check If Exists** (Google Sheets lookup)
      - Skip if already in database
   
   b. **Research Tool** (HTTP Request to Claude with web_search)
      - Use Claude API with web search tool
      - Gather: description, features, pricing, screenshots
      - Find 3 competitors
   
   c. **Calculate Priority** (Function node)
      - Score based on: category, search volume, commission potential
   
   d. **Add to Database** (Google Sheets append)
      - Sheet: MASTER_TOOLS_DB
      - Status: PENDING_CONTENT

5. **Summary** (Send notification)
   - Log: X new tools discovered

---

## CREDENTIALS SETUP IN N8N

### Claude API (HTTP Request Auth)
- **Type:** Header Auth
- **Name:** x-api-key
- **Value:** {{$env.ANTHROPIC_API_KEY}}

### Google Sheets
- **Type:** Service Account
- **JSON Key:** Upload gsc-service-account.json

### GitHub
- **Type:** Header Auth  
- **Name:** Authorization
- **Value:** Bearer {{$env.GITHUB_TOKEN}}

### Beehiiv
- **Type:** Header Auth
- **Name:** Authorization
- **Value:** Bearer {{$env.BEEHIIV_API_KEY}}

### Environment Variables
Set in n8n UI or docker-compose.yml:
- ANTHROPIC_API_KEY
- GITHUB_TOKEN
- BEEHIIV_API_KEY
- BEEHIIV_PUBLICATION_ID
- GOOGLE_SHEET_ID
- SITE_URL

---

## ERROR HANDLING

Each workflow includes:

1. **Error Trigger nodes** - Catch workflow errors
2. **Retry logic** - For API failures (3 retries with backoff)
3. **Logging** - All errors logged to Google Sheets
4. **Notifications** - Critical errors send alerts (email/Slack)

---

## MONITORING

Dashboard in Google Sheets shows:
- Pages published (daily/weekly/monthly)
- Pages indexed (from GSC)
- Traffic (clicks, impressions, CTR)
- Conversions & revenue
- Email subscribers
- System health (errors, success rates)

---

## SCALING

To increase from 100 to 200 pages/week:

1. Adjust loop limits in Workflow 1 (20 → 40 tools)
2. Increase VPS RAM (4GB → 8GB)
3. Adjust deployment script batch sizes
4. Monitor Claude API costs

---

## CUSTOMIZATION

Easy modifications:
- **Content types:** Add new templates to prompts.md
- **Priorities:** Adjust tool scoring in Workflow 7
- **Frequency:** Change cron schedules
- **Quality thresholds:** Modify QA script pass criteria

---

**Next Step:** Import n8n-workflow.json file into n8n interface
