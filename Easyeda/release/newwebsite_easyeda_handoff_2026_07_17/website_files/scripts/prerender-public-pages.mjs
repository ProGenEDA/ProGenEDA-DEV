import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.cwd();
const distDir = resolve(root, 'dist');
const ssrEntry = resolve(root, '.tmp-ssr', 'ssr.js');
const siteOrigin = 'https://progeneda.app';

const pages = {
  '/': {
    title: 'ProGenEDA | Circuit Intent In. Native EDA Files Out.',
    description: 'ProGenEDA converts circuit intent into native, editable EDA project files for KiCad, EasyEDA Pro, LTspice, and Proteus using structured circuit data and deterministic exporters.',
    type: 'SoftwareApplication',
  },
  '/get-help': {
    title: 'Get Help with ProGenEDA',
    description: 'Get help writing better circuit prompts, understanding supported components, fixing generation errors, validating outputs, and using ProGenEDA exports.',
    type: 'WebPage',
  },
  '/prompt-guide': {
    title: 'Circuit Prompt Guide | ProGenEDA',
    description: 'Write precise ProGenEDA circuit prompts for KiCad, EasyEDA Pro, Proteus, and LTspice. Learn required engineering details, supported parts, and validation rules.',
    type: 'FAQPage',
  },
  '/terms-of-service': {
    title: 'Terms of Service | ProGenEDA',
    description: 'Read the ProGenEDA Terms of Service for accounts, generated circuit outputs, quotas, acceptable use, safety disclaimers, and third-party EDA tools.',
    type: 'WebPage',
  },
  '/privacy-policy': {
    title: 'Privacy Policy | ProGenEDA',
    description: 'Learn how ProGenEDA processes account data, circuit prompts, usage records, technical logs, and generated project artifacts.',
    type: 'WebPage',
  },
};

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function jsonLdFor({ title, description, type }, path) {
  const url = `${siteOrigin}${path}`;
  if (type === 'SoftwareApplication') {
    return {
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: 'ProGenEDA',
      url,
      applicationCategory: 'EngineeringApplication',
      operatingSystem: 'Web',
      description,
    };
  }
  return {
    '@context': 'https://schema.org',
    '@type': type,
    name: title,
    description,
    url,
    isPartOf: { '@type': 'WebSite', name: 'ProGenEDA', url: siteOrigin },
  };
}

function replaceOne(html, pattern, replacement) {
  if (!pattern.test(html)) throw new Error(`Could not find ${pattern} in the built HTML template.`);
  return html.replace(pattern, replacement);
}

function buildPageHtml(template, markup, page, path) {
  const canonical = `${siteOrigin}${path}`;
  const ogImage = `${siteOrigin}/landing/progeneda-og.png`;
  const jsonLd = JSON.stringify(jsonLdFor(page, path)).replace(/</g, '\\u003c');
  let html = template;
  html = replaceOne(html, /<title>[\s\S]*?<\/title>/, `<title>${escapeHtml(page.title)}</title>`);
  html = replaceOne(html, /<meta name="description" content="[^"]*"\s*\/>/, `<meta name="description" content="${escapeHtml(page.description)}" />`);
  html = replaceOne(html, /<link rel="canonical" href="[^"]*"\s*\/>/, `<link rel="canonical" href="${canonical}" />`);
  html = replaceOne(html, /<meta property="og:title" content="[^"]*"\s*\/>/, `<meta property="og:title" content="${escapeHtml(page.title)}" />`);
  html = replaceOne(html, /<meta property="og:description" content="[^"]*"\s*\/>/, `<meta property="og:description" content="${escapeHtml(page.description)}" />`);
  html = replaceOne(html, /<meta property="og:url" content="[^"]*"\s*\/>/, `<meta property="og:url" content="${canonical}" />`);
  html = replaceOne(html, /<meta name="twitter:title" content="[^"]*"\s*\/>/, `<meta name="twitter:title" content="${escapeHtml(page.title)}" />`);
  html = replaceOne(html, /<meta name="twitter:description" content="[^"]*"\s*\/>/, `<meta name="twitter:description" content="${escapeHtml(page.description)}" />`);
  html = replaceOne(html, /<meta property="og:image" content="[^"]*"\s*\/>/, `<meta property="og:image" content="${ogImage}" />`);
  html = html.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/, `<script type="application/ld+json">${jsonLd}</script>`);
  html = replaceOne(html, /<div id="root"><\/div>/, `<div id="root">${markup}</div>`);
  return html;
}

const { renderPublicPage } = await import(pathToFileURL(ssrEntry).href);
const template = await readFile(resolve(distDir, 'index.html'), 'utf8');

for (const [path, page] of Object.entries(pages)) {
  const outputPath = path === '/'
    ? resolve(distDir, 'index.html')
    : resolve(distDir, path.slice(1), 'index.html');
  await mkdir(resolve(outputPath, '..'), { recursive: true });
  await writeFile(outputPath, buildPageHtml(template, renderPublicPage(path), page, path), 'utf8');
}

const notFound = template
  .replace(/<meta name="robots" content="[^"]*"\s*\/>/, '<meta name="robots" content="noindex, nofollow" />')
  .replace(/<div id="root"><\/div>/, '<div id="root"><main style="min-height:100vh;display:grid;place-items:center;padding:2rem;background:#fff;color:#0b1433;font-family:Arial,sans-serif"><section><p>404</p><h1>Page not found</h1><p>This ProGenEDA page does not exist.</p><a href="/">Go to ProGenEDA</a></section></main></div>');
await writeFile(resolve(distDir, '404.html'), notFound, 'utf8');

await rm(resolve(root, '.tmp-ssr'), { recursive: true, force: true });
console.log(`Prerendered ${Object.keys(pages).length} public ProGenEDA pages.`);
