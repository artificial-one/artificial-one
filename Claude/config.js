/**
 * artificial.one - Automation System Configuration
 * Source of truth for site structure, templates, and conventions.
 * Used by n8n workflows, QA script, sitemap, and deploy.
 */

module.exports = {
  site: {
    url: 'https://artificial.one',
    name: 'artificial.one',
    tagline: 'AI Tools Reviewed BY AI',
    footerText: '© 2026 artificial.one - AI tools reviewed by AI',
    branding: {
      noMentionAIProductNames: true,
      usePhrases: ['our AI systems', 'AI-powered analysis', 'automated analysis', 'AI-powered research'],
    },
  },

  /**
   * Directory structure - actual paths on site
   */
  directories: {
    tools: {
      path: 'tools',
      purpose: 'Individual AI tool review pages',
      filePattern: '{{slug}}.html',
      example: 'tools/chatgpt.html',
      count: 152,
    },
    best: {
      path: 'best',
      purpose: 'Category / best-of lists (e.g. Best AI Image Generators)',
      filePattern: 'best-ai-{{topic}}.html',
      example: 'best/best-ai-image-generators.html',
    },
    compare: {
      path: 'compare',
      purpose: 'Tool vs tool comparison pages',
      filePattern: '{{tool-a}}-vs-{{tool-b}}.html',
      altPattern: 'comparison-{{topic}}.html',
      example: 'compare/chatgpt-vs-jasper.html',
    },
    guides: {
      path: 'guides',
      purpose: 'Guides (lifetime deals, use cases, how-tos)',
      filePattern: '{{slug}}.html',
      example: 'guides/best-lifetime-ai-tools.html',
    },
    tutorials: {
      path: 'tutorials',
      purpose: 'Tutorial pages',
      filePattern: '{{slug}}.html',
      example: 'tutorials/index.html',
    },
    category: {
      path: 'category',
      purpose: 'Category landing pages (Writing, Design, etc.)',
      filePattern: '{{slug}}.html',
      example: 'category/writing-content.html',
    },
    blog: {
      path: null,
      purpose: 'Blog posts at site root',
      filePattern: 'blog-{{slug}}.html',
      example: 'blog-best-appsumo-deals-2026.html',
    },
    images: {
      path: 'images',
      purpose: 'Images; og-tools/ for tool OG images',
    },
  },

  /**
   * Affiliate link pattern - all AppSumo links use this domain
   */
  affiliate: {
    domain: 'appsumo.8odi.net',
    pattern: 'appsumo.8odi.net',
    rel: 'noopener nofollow sponsored',
    disclosure: 'This is an affiliate link. We may earn a commission at no extra cost to you.',
    requirement: 'Use appsumo.8odi.net for lifetime-deal / AppSumo tool CTAs; direct links OK for non-deal tools.',
  },

  /**
   * Meta tag conventions (from existing pages)
   */
  meta: {
    title: {
      maxLength: 60,
      minLength: 30,
      suffix: '| artificial.one',
      pattern: '{{PageTitle}} | artificial.one',
    },
    description: {
      maxLength: 160,
      minLength: 120,
    },
    og: {
      typeArticle: 'article',
      typeWebsite: 'website',
      imagePath: 'images/og-tools/{{tool-slug}}.jpg',
      imageDefault: 'images/og-default.jpg',
    },
    twitter: {
      card: 'summary_large_image',
    },
  },

  /**
   * Navigation - same structure across tool, best, compare, guide pages
   * Path from /tools/ uses ../ for index, reviews, blog, about, category/*, compare/, best/, guides/
   */
  navigation: {
    logoHref: '../index.html',
    logoImg: '../artificial-one-logo-large.svg',
    desktop: [
      { label: 'All Reviews', href: '../reviews.html' },
      { label: 'Blog', href: '../blog.html' },
      { label: 'About', href: '../about.html' },
    ],
    dropdowns: {
      categories: { label: 'Categories ▾', links: [
        { label: '✍️ Writing & Content', href: '../category/writing-content.html' },
        { label: '🎨 Design & Images', href: '../category/design-images.html' },
        { label: '🎬 Video & Animation', href: '../category/video-animation.html' },
        { label: '💻 Coding & Development', href: '../category/coding-development.html' },
        { label: '📊 Productivity & Business', href: '../category/productivity-business.html' },
        { label: '🎙️ Voice & Audio', href: '../category/voice-audio.html' },
        { label: '🔬 Research & Data', href: '../category/research-data.html' },
        { label: '📱 Marketing & Social', href: '../category/marketing-social.html' },
        { label: '📈 Data & Analytics', href: '../category/data-analytics.html' },
      ]},
      explore: { label: 'Explore ▾', links: [
        { label: '🔍 Compare Tools', href: '../compare/index.html' },
        { label: '🏆 Best Of Lists', href: '../best/index.html' },
        { label: '📚 Tutorials', href: '../tutorials/index.html' },
        { label: '📖 Guides', href: '../guides/index.html' },
      ]},
      lifetimeDeals: { label: '💰 Lifetime Deals ▾', links: [
        { label: '🎯 Browse All Deals', href: '../guides/best-lifetime-deal-software-2026.html' },
        { label: '🔍 Compare Tools', href: '../compare/index.html' },
        { label: '🚀 Best for Startups', href: '../guides/use-case-startups.html' },
        { label: '💼 Best for Freelancers', href: '../guides/use-case-freelancers.html' },
        { label: '🤖 AI Tools', href: '../guides/best-lifetime-ai-tools.html' },
      ]},
    },
    ctaButton: { label: 'Browse Tools', href: '../reviews.html', class: 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white px-4 sm:px-6 py-2 rounded-lg font-semibold' },
    mobileMenuId: 'mobile-menu',
    mobileMenuBtnId: 'mobile-menu-btn',
    mobileDropdownClass: 'mobile-dropdown-btn',
  },

  /**
   * CSS classes used on existing pages (for QA and template consistency)
   */
  styling: {
    body: 'bg-white',
    nav: 'bg-white border-b border-gray-200 sticky top-0 z-50',
    container: 'max-w-4xl mx-auto px-4 sm:px-6 lg:px-8',
    article: 'max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12',
    h1: 'text-4xl md:text-5xl font-bold text-gray-900 mb-4',
    h2: 'text-3xl font-bold text-gray-900 mt-12 mb-6',
    prose: 'text-lg text-gray-700 mb-6',
    scoreBadge: 'px-4 py-2 bg-green-100 text-green-800 rounded-lg font-bold text-lg',
    priceBadge: 'px-4 py-2 bg-gray-100 text-gray-800 rounded-lg font-semibold',
    freeBadge: 'px-4 py-2 bg-blue-100 text-blue-800 rounded-lg font-semibold',
    ctaBox: 'bg-gradient-to-r from-purple-100 to-blue-100 rounded-xl p-8 my-12 text-center',
    ctaButton: 'inline-block bg-gradient-to-r from-purple-600 to-blue-600 text-white px-8 py-3 rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700',
    secondaryCtaBox: 'bg-gray-50 rounded-xl p-8 my-12',
    secondaryCtaButton: 'inline-block bg-gray-900 text-white px-6 py-3 rounded-lg font-semibold hover:bg-gray-800',
    footer: 'bg-gray-50 border-t border-gray-200 py-8 mt-16',
    footerInner: 'max-w-4xl mx-auto px-4 text-center text-gray-600',
    dropdown: 'dropdown',
    dropdownContent: 'dropdown-content',
  },

  /**
   * QA-relevant selectors (existing site does not use class="cta"; uses gradient buttons)
   */
  qa: {
    ctaSelectors: [
      'a[class*="bg-gradient-to-r"][class*="purple-600"]',
      'a[class*="from-indigo-600"]',
      'a.btn',
    ],
    emailCaptureSelectors: ['input[type="email"]', '[data-beehiiv]', '.subscribe-form'],
    faqSectionSelectors: ['[class*="faq"]', 'h2:contains("FAQ")', 'h3:contains("FAQ")'],
    schemaTypes: ['BreadcrumbList', 'FAQPage', 'Product', 'Review', 'Article', 'Organization'],
    backLinkText: 'Back to All Reviews',
    backLinkHref: '../reviews.html',
  },

  /**
   * Sitemap format (match existing sitemap.xml)
   */
  sitemap: {
    xmlns: 'http://www.sitemaps.org/schemas/sitemap/0.9',
    rootElement: 'urlset',
    urlElement: 'url',
    childElements: ['loc', 'lastmod', 'changefreq', 'priority'],
    dateFormat: 'YYYY-MM-DD',
    priorities: {
      homepage: 1.0,
      tools: 0.9,
      best: 0.9,
      compare: 0.9,
      guides: 0.8,
      tutorials: 0.7,
      blog: 0.7,
      category: 0.8,
      other: 0.5,
    },
    changefreq: {
      homepage: 'daily',
      tools: 'weekly',
      best: 'weekly',
      compare: 'weekly',
      guides: 'weekly',
      tutorials: 'weekly',
      blog: 'weekly',
      other: 'monthly',
    },
  },

  /**
   * Paths for automation (VPS / n8n)
   */
  paths: {
    repoRoot: process.env.REPO_DIR || '/root/artificial-one',
    tempContent: process.env.TEMP_CONTENT || '/temp-content',
    approvedContent: process.env.APPROVED_CONTENT || '/approved-content',
    scripts: process.env.SCRIPTS_DIR || '/root/n8n/scripts',
    approvedPagesFile: 'APPROVED_PAGES.txt',
  },

  /**
   * Google Sheets (for n8n)
   */
  sheets: {
    masterToolsDb: 'MASTER_TOOLS_DB',
    qaReport: 'QA_REPORT',
    needsFixing: 'NEEDS_FIXING',
    revenueDashboard: 'REVENUE_DASHBOARD',
    gscImprovements: 'GSC_IMPROVEMENTS',
  },
};
