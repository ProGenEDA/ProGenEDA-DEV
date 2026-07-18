import { extname } from 'node:path';

const DEFAULT_EXTENSION = {
  KC: '.zip',
  PR: '.pdsprj',
  LT: '.asc',
  EA: '.eprj',
};

function safeFileStem(value, fallback = 'circuit') {
  const title = String(value || '')
    .replace(/^main\s+json\s+catalog\s+\d+\s*[:-]?\s*/i, '');
  const normalized = title
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 44);

  return normalized || fallback;
}

function safeExtension(service, sourceFileName) {
  const candidate = extname(String(sourceFileName || '')).toLowerCase();
  if (/^\.[a-z0-9]{1,10}$/.test(candidate)) return candidate;
  return DEFAULT_EXTENSION[service] || '.bin';
}

export function buildExportFileName({ service, title, sourceFileName }) {
  return `ProGenEDA-${service}-${safeFileStem(title)}${safeExtension(service, sourceFileName)}`;
}

export function buildBatchFileName({ service, itemCount }) {
  const count = Math.max(1, Math.min(50, Number(itemCount) || 1));
  const serviceName = service === 'KC' ? 'KiCad' : service === 'PR' ? 'Proteus' : service === 'LT' ? 'LTspice' : service === 'EA' ? 'EasyEDA' : service;
  return `ProGenEDA-${serviceName}-batch-${count}.zip`;
}
