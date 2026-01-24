# OG Images Creation Guide

## Quick Overview

You need to create **1200x630px** images for social media sharing. These images appear when your pages are shared on Facebook, Twitter, LinkedIn, etc.

---

## Image Specifications

- **Dimensions:** 1200px × 630px (1.91:1 aspect ratio)
- **Format:** JPG or PNG
- **File Size:** Under 1MB (optimize for web)
- **Text:** Keep text large and readable (minimum 24px font)
- **Safe Zone:** Keep important content within 1200×630px (some platforms crop edges)

---

## Tools You Can Use

### 1. **Canva (Easiest - Recommended)**
- **Cost:** Free plan available, Pro is $12.99/month
- **URL:** https://canva.com
- **Steps:**
  1. Create account
  2. Search for "Facebook Post" or "Open Graph" template
  3. Customize with your branding
  4. Export as JPG (1200×630px)
- **Pros:** Easy, templates, no design skills needed
- **Best for:** Quick creation, consistent branding

### 2. **Figma (Free & Professional)**
- **Cost:** Free
- **URL:** https://figma.com
- **Steps:**
  1. Create new design file
  2. Set frame to 1200×630px
  3. Design your image
  4. Export as JPG
- **Pros:** Free, professional, collaborative
- **Best for:** Custom designs, team collaboration

### 3. **AI Image Generators (Fastest)**
- **Tools:** Midjourney, DALL-E, Stable Diffusion, Leonardo.ai
- **Cost:** $10-30/month
- **Steps:**
  1. Use prompt: "Create a professional social media image for [Tool Name] review, 1200x630px, modern design, includes rating stars, clean layout"
  2. Generate image
  3. Add text overlay with tool name and rating
- **Pros:** Fast, unique designs
- **Cons:** May need text overlay added separately

### 4. **Photoshop / GIMP**
- **Cost:** Photoshop $20/month, GIMP is free
- **Best for:** Full control, advanced editing

---

## Image Templates & Structure

### Homepage OG Image
**File:** `/images/og-homepage.jpg`
**Content:**
- Logo: "artificial.one"
- Tagline: "Find the Right AI Tool in 5 Minutes"
- Stats: "220+ Tools Reviewed"
- Background: Gradient (purple/indigo)
- CTA: "Browse Reviews"

### Tool Review Images
**File:** `/images/og-tools/{tool-name}.jpg`
**Content:**
- Tool name (large, bold)
- Rating (e.g., "4.5/5 ⭐⭐⭐⭐⭐")
- Key benefit (1-2 lines)
- Category badge
- Background: Tool-specific color or gradient

**Example for ChatGPT:**
- Title: "ChatGPT Review"
- Rating: "9.2/10 ⭐⭐⭐⭐⭐"
- Benefit: "Most versatile AI assistant"
- Category: "Writing & Content"

### Category Images
**File:** `/images/og-categories/{category-name}.jpg`
**Content:**
- Category name
- Number of tools (e.g., "25 Tools Reviewed")
- Icon/emoji for category
- Gradient background

### Blog Post Images
**File:** `/images/og-blog/{blog-name}.jpg`
**Content:**
- Blog post title
- Subtitle or key point
- Date: "2026"
- Background: Relevant to topic

---

## Batch Creation Strategy

### Phase 1: Priority Images (Week 1)
Create these first:
1. **Homepage** - `/images/og-homepage.jpg`
2. **Top 20 Tool Reviews** - Most popular/important tools
3. **9 Category Pages** - All category pages
4. **Default Fallback** - `/images/og-default.jpg`

### Phase 2: Remaining Images (Week 2-4)
- Remaining tool reviews (create as needed)
- Blog post images (create when publishing)

---

## Automated Solutions

### Option 1: Use a Service
- **Bannerbear** ($99/month) - Auto-generates OG images from templates
- **Cloudinary** - Can generate images on-the-fly
- **ImageKit** - Similar to Cloudinary

### Option 2: Create a Template System
Use a design tool with variables:
- **Canva Brand Kit** - Create template, duplicate for each tool
- **Figma Components** - Create reusable components

### Option 3: Script-Based Generation (Advanced)
Use Python libraries:
- **Pillow (PIL)** - Generate images programmatically
- **ReportLab** - Create images with text/graphics

---

## Quick Start: Canva Template

### Step-by-Step:

1. **Create Template:**
   - Go to Canva.com
   - Create custom size: 1200×630px
   - Add your logo
   - Create text boxes for: Tool Name, Rating, Category
   - Save as template

2. **For Each Tool:**
   - Duplicate template
   - Update tool name
   - Update rating
   - Update category
   - Export as JPG
   - Name file: `{tool-name}.jpg`
   - Upload to `/images/og-tools/`

3. **Time Estimate:**
   - Template creation: 30 minutes
   - Each image: 2-3 minutes
   - 20 priority images: ~1 hour
   - All 500+ tool images: 15-20 hours (spread over time)

---

## Image Optimization

After creating images:

1. **Compress:**
   - Use TinyPNG or Squoosh
   - Target: Under 200KB per image
   - Maintain quality at 80-85%

2. **Test:**
   - Use Facebook Sharing Debugger: https://developers.facebook.com/tools/debug/
   - Use Twitter Card Validator: https://cards-dev.twitter.com/validator
   - Verify images load correctly

3. **Organize:**
   - Keep consistent naming: `tool-name.jpg`
   - Use lowercase, hyphens
   - Store in organized folders

---

## Cost Estimates

### DIY (Canva Free):
- **Time:** 15-20 hours for all images
- **Cost:** $0
- **Quality:** Good

### DIY (Canva Pro):
- **Time:** 10-15 hours (better templates)
- **Cost:** $12.99/month
- **Quality:** Excellent

### AI Generation + Editing:
- **Time:** 5-10 hours
- **Cost:** $20-50/month (AI tool)
- **Quality:** Very good

### Service (Bannerbear):
- **Time:** 2-3 hours setup
- **Cost:** $99/month
- **Quality:** Excellent, automated

---

## Recommended Approach

**For You (Best Balance):**

1. **Week 1:** Create homepage + top 20 tools manually in Canva
2. **Week 2-4:** Create remaining tool images as needed (when pages get traffic)
3. **Ongoing:** Create blog post images when publishing

**Why This Works:**
- Prioritizes high-traffic pages first
- Spreads work over time
- Focuses on pages that matter most
- Can improve images later based on performance

---

## Next Steps

1. ✅ Create `/images/` directory structure
2. ✅ Create homepage OG image
3. ✅ Create top 20 tool review images
4. ✅ Create 9 category images
5. ✅ Create default fallback image
6. ✅ Test images with Facebook/Twitter validators
7. ✅ Upload to your server
8. ✅ Verify images load correctly

---

## Need Help?

I can create a Python script that:
- Lists all images you need to create
- Generates a CSV/spreadsheet for tracking
- Creates placeholder images (if you want)
- Validates image URLs once uploaded

Let me know if you'd like me to create that helper script!
