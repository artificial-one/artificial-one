# Open Graph Image Creation Guide

## 📐 Specifications

- **Dimensions:** 1200 x 630 pixels (1.91:1 aspect ratio)
- **Format:** JPG or PNG
- **File Size:** Under 1MB (optimize for web)
- **Text:** Keep text readable at small sizes (minimum 24px font)

---

## 🎨 Design Guidelines

### Essential Elements:
1. **Tool/Page Name** - Large, bold, readable
2. **Rating** (for tool reviews) - Star rating or score
3. **Key Benefit** - One-line value proposition
4. **Branding** - Your logo or site name
5. **Background** - Gradient or solid color matching your brand

### Color Scheme:
- Use your brand colors (purple/indigo gradients from your site)
- Ensure good contrast for readability
- Consider dark mode compatibility

---

## 🛠️ Tools & Methods

### Option 1: Canva (Easiest - Recommended)
1. Go to [Canva.com](https://www.canva.com)
2. Create custom size: 1200 x 630px
3. Use templates or create from scratch
4. Export as JPG (optimized for web)
5. **Pro Tip:** Create one template, then duplicate and change text

### Option 2: Figma (Professional)
1. Create 1200x630px frame
2. Design template with components
3. Use variables for dynamic content
4. Export as JPG

### Option 3: Photoshop/Illustrator
1. Create 1200x630px document
2. Design template
3. Use data merge for batch creation
4. Export optimized JPGs

### Option 4: Automated Tools
- **Bannerbear API** - Generate images via API
- **Cloudinary** - Dynamic image generation
- **ImageKit** - On-the-fly image generation

### Option 5: AI Image Generators
- **Midjourney** - Generate backgrounds
- **DALL-E** - Create custom designs
- **Stable Diffusion** - Open source option

---

## 📋 Image Checklist

### Priority 1 (Create First):
- [ ] `/images/og-homepage.jpg` - Homepage
- [ ] `/images/og-default.jpg` - Fallback for all pages
- [ ] `/images/og-compare.jpg` - Comparison pages
- [ ] `/images/og-best-of.jpg` - Best of pages
- [ ] `/images/og-guides.jpg` - Guide pages

### Priority 2 (Category Pages):
- [ ] `/images/og-categories/writing-content.jpg`
- [ ] `/images/og-categories/design-images.jpg`
- [ ] `/images/og-categories/video-animation.jpg`
- [ ] `/images/og-categories/coding-development.jpg`
- [ ] `/images/og-categories/productivity-business.jpg`
- [ ] `/images/og-categories/voice-audio.jpg`
- [ ] `/images/og-categories/research-data.jpg`
- [ ] `/images/og-categories/marketing-social.jpg`
- [ ] `/images/og-categories/data-analytics.jpg`

### Priority 3 (Top Tool Reviews):
Create for your top 20-50 most popular tools:
- [ ] `/images/og-tools/chatgpt.jpg`
- [ ] `/images/og-tools/claude.jpg`
- [ ] `/images/og-tools/midjourney.jpg`
- [ ] ... (see script output for full list)

### Priority 4 (Blog Posts):
- [ ] `/images/og-blog/ai-seo-tools.jpg`
- [ ] `/images/og-blog/chatgpt-vs-claude.jpg`
- [ ] ... (create as needed)

---

## 🎯 Template Design Ideas

### For Tool Reviews:
```
┌─────────────────────────────────────┐
│  [Background: Purple gradient]      │
│                                     │
│  [Tool Logo/Icon]                   │
│                                     │
│  Tool Name                          │
│  ⭐⭐⭐⭐⭐ 4.5/5              │
│                                     │
│  "Key benefit in one line"          │
│                                     │
│  artificial.one                     │
└─────────────────────────────────────┘
```

### For Comparison Pages:
```
┌─────────────────────────────────────┐
│  [Background: Blue gradient]        │
│                                     │
│  Tool A  vs  Tool B                │
│                                     │
│  Compare features, pricing & reviews │
│                                     │
│  Find the best tool for your needs  │
│                                     │
│  artificial.one                     │
└─────────────────────────────────────┘
```

### For Category Pages:
```
┌─────────────────────────────────────┐
│  [Background: Category color]       │
│                                     │
│  [Category Icon]                    │
│                                     │
│  Writing & Content AI Tools         │
│                                     │
│  Browse 25+ tools, compare reviews  │
│                                     │
│  artificial.one                     │
└─────────────────────────────────────┘
```

---

## 🚀 Quick Start with Canva

1. **Create Template:**
   - New design → Custom size: 1200 x 630
   - Add gradient background (purple to indigo)
   - Add text box for tool name (font: 48-60px, bold)
   - Add rating display
   - Add tagline text
   - Add your logo at bottom

2. **Save as Template:**
   - Save design as template
   - Duplicate for each tool/page

3. **Batch Create:**
   - Use Canva's bulk create feature
   - Upload CSV with tool names, ratings, etc.
   - Auto-generate all images

4. **Export:**
   - Download as JPG
   - Optimize with TinyPNG or similar
   - Upload to `/images/og-*/` directories

---

## 📝 CSV Template for Bulk Creation

If using Canva's bulk create:

```csv
Tool Name,Rating,Benefit,Image Path
ChatGPT,4.8,AI assistant for writing and coding,og-tools/chatgpt.jpg
Claude,4.7,Advanced AI for analysis and writing,og-tools/claude.jpg
Midjourney,4.9,AI image generation,og-tools/midjourney.jpg
```

---

## 🔧 Automation Script

I've created a script (`list_og_images_needed.py`) that will:
- List all OG images needed
- Generate a CSV for bulk creation
- Show which images are missing

Run it to see exactly what you need!

---

## 💡 Pro Tips

1. **Start Small:** Create 5-10 images first, test them, then scale
2. **Use Templates:** One good template can be reused for hundreds
3. **Optimize:** Compress images to reduce load time
4. **Test:** Use Facebook's Sharing Debugger to preview
5. **CDN:** Consider using a CDN for faster delivery

---

## 🧪 Testing Your Images

1. **Facebook Debugger:**
   - https://developers.facebook.com/tools/debug/
   - Enter URL, click "Scrape Again"
   - Preview how it looks when shared

2. **Twitter Card Validator:**
   - https://cards-dev.twitter.com/validator
   - Test Twitter sharing appearance

3. **LinkedIn Post Inspector:**
   - https://www.linkedin.com/post-inspector/
   - Test LinkedIn sharing

---

## 📊 Expected Impact

- **2-3x better** social media engagement
- **Higher CTR** from social traffic
- **More professional** brand appearance
- **Better** first impression

---

## 🎨 Design Resources

- **Free Stock Photos:** Unsplash, Pexels
- **Icons:** Flaticon, Icons8
- **Fonts:** Google Fonts (use your site fonts)
- **Color Palettes:** Coolors.co, Adobe Color

---

## ⚡ Quick Win: Use a Service

If you want to outsource:
- **Fiverr:** $50-200 for 50-100 images
- **99designs:** Professional designs
- **Design Pickle:** Monthly subscription

---

**Next Step:** Run `list_og_images_needed.py` to see exactly which images you need!
