import { readdir, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

const LTSPICE_FEATURED_EXAMPLE_IDS = [
  '001_voltage-divider',
  '021_first-order-rc-low-pass-filter',
  '051_series-rlc-resonant-circuit',
  '058_lc-tank-circuit',
];

const EASYEDA_FEATURED_EXAMPLE_IDS = [
  'q01_esp32_environment_logger_education_v01',
  'q11_dual_mcu_bridge_education_v01',
  'q26_regulated_5v_supply_education_v01',
  'q30_digital_logic_trainer_education_v01',
];

const DISPLAY_ACRONYMS = new Set([
  'ac',
  'adc',
  'dac',
  'dc',
  'lc',
  'rc',
  'rl',
  'rlc',
  'rms',
]);

const libraryCache = new Map();

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function numericPrefix(value) {
  const match = String(value).match(/^(\d+)/);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}

function titleWord(value) {
  const lower = String(value).toLowerCase();
  if (DISPLAY_ACRONYMS.has(lower)) return lower.toUpperCase();
  if (/^\d+[a-z]+$/i.test(value)) return String(value).toUpperCase();
  if (/^[a-z]\d+[a-z0-9]*$/i.test(value)) return String(value).toUpperCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function titleFromId(id) {
  return String(id)
    .replace(/^\d+[_-]?/, '')
    .split(/[_-]+/)
    .filter(Boolean)
    .map(titleWord)
    .join(' ');
}

/**
 * Treat file-system separators, hyphens, and underscores as the same input
 * boundary. This is deliberately deterministic: it does not guess that a
 * modified circuit request means an existing library example.
 */
export function normalizeExampleCircuitName(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[\\/_-]+/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

function selectorCandidates(prompt) {
  const initial = normalizeExampleCircuitName(prompt);
  if (!initial) return [];

  const candidates = new Set([initial]);
  const withoutLeadIn = initial.replace(/^(?:please )?(?:generate|build|create|make|open|run)(?: an?| the)? /, '');
  candidates.add(withoutLeadIn);
  candidates.add(withoutLeadIn.replace(/^ltspice /, ''));
  if (withoutLeadIn.endsWith(' circuit')) {
    candidates.add(withoutLeadIn.slice(0, -' circuit'.length).trim());
  }
  return [...candidates].filter(Boolean);
}

function publicExample(entry) {
  return {
    id: entry.id,
    title: entry.title,
    service: entry.service,
  };
}

function librarySettings(service, config) {
  if (service === 'LT') {
    return {
      rootDir: resolve(config.ltspiceExampleLibraryDir),
      featuredIds: LTSPICE_FEATURED_EXAMPLE_IDS,
    };
  }
  if (service === 'EA') {
    return {
      rootDir: resolve(config.easyedaExampleLibraryDir),
      featuredIds: EASYEDA_FEATURED_EXAMPLE_IDS,
    };
  }
  return null;
}

async function loadLibrary(service, config) {
  const settings = librarySettings(service, config);
  if (!settings) return [];
  const cacheKey = `${service}:${settings.rootDir}`;
  if (libraryCache.has(cacheKey)) return libraryCache.get(cacheKey);

  const loading = (async () => {
    let directories;
    try {
      directories = await readdir(settings.rootDir, { withFileTypes: true });
    } catch (error) {
      const detail = error instanceof Error ? error.message : 'unknown filesystem error';
      const libraryError = new Error(`The ${service} example library is unavailable: ${detail}`);
      libraryError.statusCode = 503;
      throw libraryError;
    }

    const entries = await Promise.all(
      directories
        .filter((entry) => entry.isDirectory())
        .sort((left, right) => numericPrefix(left.name) - numericPrefix(right.name) || left.name.localeCompare(right.name))
        .map(async (directory) => {
          const id = directory.name;
          const sourcePath = join(settings.rootDir, id, 'circuit.json');
          const raw = await readFile(sourcePath, 'utf8');
          const mainJson = JSON.parse(raw);
          if (!mainJson || typeof mainJson !== 'object' || Array.isArray(mainJson)) {
            throw new Error(`Example ${id} must contain one canonical circuit JSON object.`);
          }
          const title = String(mainJson?.project?.title || titleFromId(id));
          return {
            id,
            title,
            service,
            mainJson,
            aliases: new Set([
              normalizeExampleCircuitName(id),
              normalizeExampleCircuitName(id.replace(/^\d+[_-]?/, '')),
              normalizeExampleCircuitName(title),
            ]),
          };
        }),
    );

    if (!entries.length) {
      const emptyError = new Error(`The ${service} example library does not contain any canonical circuit JSON files.`);
      emptyError.statusCode = 503;
      throw emptyError;
    }

    return entries;
  })();

  libraryCache.set(cacheKey, loading);
  try {
    return await loading;
  } catch (error) {
    libraryCache.delete(cacheKey);
    throw error;
  }
}

export async function listExampleCircuits({ service, config }) {
  const normalizedService = String(service || '').toUpperCase();
  const settings = librarySettings(normalizedService, config);
  if (!settings) {
    const error = new Error(`No example library is configured for ${normalizedService || 'this service'}.`);
    error.statusCode = 404;
    throw error;
  }

  const entries = await loadLibrary(normalizedService, config);
  const featuredIds = new Set(settings.featuredIds);
  const featuredEntries = entries.filter((entry) => featuredIds.has(entry.id));
  const featured = (featuredEntries.length ? featuredEntries : entries.slice(0, 4)).map(publicExample);
  const featuredIdSet = new Set(featured.map((entry) => entry.id));

  return {
    service: normalizedService,
    total: entries.length,
    featured,
    remaining: entries.filter((entry) => !featuredIdSet.has(entry.id)).map(publicExample),
  };
}

/**
 * Match only known titles and normalized file names. This runs before any
 * model routing so an example never consumes AI budget or provider capacity.
 */
export async function selectDeterministicExampleCircuit({ service, prompt, config }) {
  const normalizedService = String(service || '').toUpperCase();
  if (!librarySettings(normalizedService, config)) return null;

  const candidates = selectorCandidates(prompt);
  if (!candidates.length) return null;
  const entries = await loadLibrary(normalizedService, config);
  const matched = entries.find((entry) => candidates.some((candidate) => entry.aliases.has(candidate)));
  if (!matched) return null;

  return {
    id: matched.id,
    title: matched.title,
    service: matched.service,
    matchType: 'normalized_exact_title',
    mainJson: cloneJson(matched.mainJson),
  };
}

export function clearExampleCircuitLibraryCache() {
  libraryCache.clear();
}
