#!/bin/bash
#
# Agent 5: Deployment Script
# Stages deployment of new content to GitHub in natural-looking batches
#

set -e  # Exit on error

# Configuration
REPO_DIR="${REPO_DIR:-/home/claude/artificial.one}"
TEMP_CONTENT_DIR="${TEMP_CONTENT_DIR:-/temp-content}"
APPROVED_FILE="${APPROVED_FILE:-/approved-content/APPROVED_PAGES.txt}"

echo "=========================================="
echo "Deployment Script - Agent 5"
echo "=========================================="
echo "Repository: $REPO_DIR"
echo "Temp Content: $TEMP_CONTENT_DIR"
echo "Approved Pages: $APPROVED_FILE"
echo ""

# Change to repo directory
cd "$REPO_DIR" || exit 1

# Check if approved pages file exists
if [ ! -f "$APPROVED_FILE" ]; then
    echo "No approved pages file found. Nothing to deploy."
    exit 0
fi

# Read approved pages
mapfile -t APPROVED_PAGES < "$APPROVED_FILE"
TOTAL_PAGES=${#APPROVED_PAGES[@]}

if [ $TOTAL_PAGES -eq 0 ]; then
    echo "No pages to deploy."
    exit 0
fi

echo "Found $TOTAL_PAGES pages to deploy"
echo ""

# Function to deploy a batch of pages
deploy_batch() {
    local batch_num=$1
    local start_idx=$2
    local end_idx=$3
    local commit_msg=$4
    
    echo "----------------------------------------"
    echo "Batch $batch_num: Deploying pages $start_idx to $end_idx"
    echo "----------------------------------------"
    
    # Copy files from temp to repo
    local count=0
    for ((i=start_idx; i<end_idx && i<TOTAL_PAGES; i++)); do
        page="${APPROVED_PAGES[$i]}"
        page=$(echo "$page" | tr -d '\r\n')  # Remove any line endings
        
        if [ -z "$page" ]; then
            continue
        fi
        
        source_file="$TEMP_CONTENT_DIR/$page"
        dest_file="$REPO_DIR/$page"
        
        if [ -f "$source_file" ]; then
            # Create directory if needed
            dest_dir=$(dirname "$dest_file")
            mkdir -p "$dest_dir"
            
            # Copy file
            cp "$source_file" "$dest_file"
            echo "  ✓ $page"
            ((count++))
        else
            echo "  ✗ $page (source not found)"
        fi
    done
    
    echo ""
    echo "Copied $count files"
    
    # Update sitemap
    echo "Updating sitemap..."
    python3 /scripts/update_sitemap.py
    
    # Git add all changes
    git add .
    
    # Check if there are changes to commit
    if git diff --cached --quiet; then
        echo "No changes to commit in this batch"
        return
    fi
    
    # Commit
    echo "Committing changes..."
    git commit -m "$commit_msg"
    
    # Push
    echo "Pushing to GitHub..."
    git push origin main
    
    echo "✓ Batch $batch_num deployed successfully"
    echo ""
}

# Deploy in 4 staged batches to look natural
# Batch sizes: 20, 30, 25, 25 (or whatever remains)

BATCH1_SIZE=20
BATCH2_SIZE=30
BATCH3_SIZE=25

echo "Deploying in staged batches..."
echo ""

# Batch 1 - Tool reviews and high-priority pages (20 pages)
deploy_batch 1 0 $BATCH1_SIZE "Add new tool reviews and updates"

# Wait 2 hours (in production)
# For testing, wait is reduced
# sleep 7200  # Uncomment for production

# Batch 2 - Comparisons and alternatives (30 pages)
START2=$BATCH1_SIZE
END2=$((START2 + BATCH2_SIZE))
deploy_batch 2 $START2 $END2 "Add comparison pages and alternatives"

# Wait 3 hours (in production)
# sleep 10800  # Uncomment for production

# Batch 3 - Category updates and guides (25 pages)
START3=$END2
END3=$((START3 + BATCH3_SIZE))
deploy_batch 3 $START3 $END3 "Update category pages and add guides"

# Wait 4 hours (in production)
# sleep 14400  # Uncomment for production

# Batch 4 - Remaining pages (blog posts, tutorials, etc.)
START4=$END3
END4=$TOTAL_PAGES
if [ $START4 -lt $TOTAL_PAGES ]; then
    deploy_batch 4 $START4 $END4 "Add blog posts and tutorials"
fi

# Clean up - move deployed files from temp to archive
echo "----------------------------------------"
echo "Archiving deployed files..."
echo "----------------------------------------"

ARCHIVE_DIR="/temp-content/archive/$(date +%Y-%m-%d)"
mkdir -p "$ARCHIVE_DIR"

for page in "${APPROVED_PAGES[@]}"; do
    page=$(echo "$page" | tr -d '\r\n')
    
    if [ -z "$page" ]; then
        continue
    fi
    
    source_file="$TEMP_CONTENT_DIR/$page"
    
    if [ -f "$source_file" ]; then
        archive_path="$ARCHIVE_DIR/$page"
        archive_dir=$(dirname "$archive_path")
        mkdir -p "$archive_dir"
        mv "$source_file" "$archive_path"
    fi
done

# Clear approved pages file
> "$APPROVED_FILE"

echo "✓ Files archived to $ARCHIVE_DIR"
echo ""

# Log deployment
DEPLOY_LOG="/scripts/deployment.log"
echo "[$(date)] Deployed $TOTAL_PAGES pages" >> "$DEPLOY_LOG"

echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "Total pages deployed: $TOTAL_PAGES"
echo "Repository updated: $REPO_DIR"
echo "Netlify will auto-deploy from GitHub"
echo ""
echo "Check Netlify deploy status:"
echo "https://app.netlify.com/sites/YOUR-SITE/deploys"
echo "=========================================="
