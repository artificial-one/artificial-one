# artificial.one - Complete Automation System Setup Guide

## Overview
This guide will help you set up a fully automated content generation system that produces 100 high-quality pages per week with zero human intervention after setup.

**Total Setup Time:** 4-6 hours  
**Monthly Cost:** ~$270  
**Expected Output:** 100 pages/week, fully automated  

---

## PHASE 1: Infrastructure Setup (1-2 hours)

### Step 1: Create DigitalOcean Droplet

1. Go to https://digitalocean.com
2. Create account (use this link for $200 credit: https://m.do.co/c/...)
3. Create Droplet:
   - **Image:** Ubuntu 22.04 LTS
   - **Plan:** Basic
   - **CPU Options:** Regular - $24/month (4GB RAM, 2 vCPUs)
   - **Datacenter:** Choose closest to you
   - **Authentication:** SSH Key (generate if needed)
   - **Hostname:** artificial-one-automation

4. Wait 2 minutes for droplet creation
5. Note your droplet's IP address

### Step 2: Install Docker on VPS

```bash
# SSH into your droplet
ssh root@YOUR_DROPLET_IP

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

### Step 3: Install n8n

```bash
# Create n8n directory
mkdir -p /root/n8n
cd /root/n8n

# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=CHANGE_THIS_PASSWORD
      - N8N_HOST=YOUR_DROPLET_IP
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=http://YOUR_DROPLET_IP:5678/
      - GENERIC_TIMEZONE=America/New_York
    volumes:
      - ./n8n_data:/home/node/.n8n
      - ./scripts:/scripts
      - ./temp-content:/temp-content
      - ./approved-content:/approved-content
EOF

# Replace placeholders
nano docker-compose.yml
# Change CHANGE_THIS_PASSWORD to a strong password
# Change YOUR_DROPLET_IP to your actual IP

# Start n8n
docker-compose up -d

# Check if running
docker-compose ps
```

### Step 4: Access n8n

1. Open browser: http://YOUR_DROPLET_IP:5678
2. Login with credentials from docker-compose.yml
3. You should see n8n interface

---

## PHASE 2: API Keys & Services Setup (30 minutes)

### Step 1: Anthropic API (Claude)

1. Go to https://console.anthropic.com
2. Sign up / Log in
3. Go to "API Keys"
4. Create new key: "artificial-one-automation"
5. Copy key (starts with `sk-ant-...`)
6. **Save to password manager** - you'll need this

**Pricing:** ~$150/month for 100 pages/week

### Step 2: Google Cloud Setup (for Search Console API)

1. Go to https://console.cloud.google.com
2. Create new project: "artificial-one-automation"
3. Enable APIs:
   - Google Search Console API
   - Google Analytics Data API (optional)

4. Create Service Account:
   - Go to "IAM & Admin" → "Service Accounts"
   - Create Service Account: "n8n-automation"
   - Grant role: "Owner"
   - Create JSON key
   - Download JSON file
   - Save as `gsc-service-account.json`

5. Add service account to Search Console:
   - Go to https://search.google.com/search-console
   - Select your property (artificial.one)
   - Settings → Users and permissions
   - Add user: [service account email from JSON]
   - Permission: "Full"

### Step 3: Google Sheets Setup

1. Go to https://sheets.google.com
2. Create new spreadsheet: "artificial-one-automation-db"
3. Create these sheets:
   - **MASTER_TOOLS_DB**
   - **QA_REPORT**
   - **NEEDS_FIXING**
   - **REVENUE_DASHBOARD**
   - **GSC_IMPROVEMENTS**

4. Share spreadsheet with service account email (from JSON)
5. Copy spreadsheet ID from URL

### Step 4: Beehiiv Email Setup

1. Go to https://beehiiv.com
2. Login to your account
3. Go to Settings → Integrations → API
4. Create API Key: "n8n-automation"
5. Copy API key
6. Note your Publication ID

### Step 5: GitHub Setup

1. Go to GitHub → Settings → Developer Settings → Personal Access Tokens
2. Generate new token (classic)
3. Scopes: `repo` (full control)
4. Copy token

---

## PHASE 3: Scripts Setup (30 minutes)

Scripts will be provided in separate files. Upload them to your VPS at `/root/n8n/scripts/`

---

## PHASE 4: n8n Workflow Import (1 hour)

1. Import workflow JSON (provided separately)
2. Configure all credentials
3. Test each agent
4. Enable automated schedule

---

## PHASE 5-7: See full guide for deployment, monitoring, and scaling

[Complete documentation continues in full setup guide...]

---

**Next:** Review Python scripts and n8n workflow files provided in this package.
