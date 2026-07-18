import { createServer } from 'node:http';
import { mkdir } from 'node:fs/promises';
import { URL } from 'node:url';
import { config } from './config.mjs';
import { LocalJsonDb, createId } from '../../../packages/db-adapter/local-json-db.mjs';
import { LocalStorageService } from '../../../packages/storage-adapter/local-storage-service.mjs';
import { createStoredZip } from '../../../packages/storage-adapter/zip-writer.mjs';
import { parseSerial } from '../../../packages/serial-system/index.mjs';
import { buildBatchFileName } from './services/artifact-naming.mjs';
import { assertSafePrompt, authContextFromRequest } from './security/prompt-security.mjs';
import { CircuitService } from './services/circuit-service.mjs';
import { buildApiCenterSnapshot } from './services/api-center-service.mjs';
import {
  requireOwnerAdmin,
  SystemConfigService,
} from './services/system-config-service.mjs';
import {
  applyKiCadNormalChanges,
  assertAdvancedEditorAccess,
  buildKiCadEditorDocument,
  validateKiCadMainJson,
} from './services/kicad-json-editor-service.mjs';
import {
  applyLtspiceNormalChanges,
  buildLtspiceEditorDocument,
  validateLtspiceMainJson,
} from './services/ltspice-json-editor-service.mjs';
import {
  applyEasyedaNormalChanges,
  buildEasyedaEditorDocument,
  validateEasyedaMainJson,
} from './services/easyeda-json-editor-service.mjs';
import {
  aiPlannerStatus,
  planKicadMainJson,
} from './services/kicad-main-json-planner-service.mjs';
import {
  analyzeCircuitPrompt,
  proteusComponentGuide,
} from './services/prompt-guide-service.mjs';
import { listExampleCircuits } from './services/example-circuit-library-service.mjs';

const db = new LocalJsonDb({ path: config.dbPath });
const storage = new LocalStorageService({ rootDir: config.localDataDir });
const systemConfigService = new SystemConfigService({ db, config });
const circuitService = new CircuitService({
  db,
  storage,
  config,
  systemConfigService,
});
const aiTestRequestWindows = new Map();

function corsOrigin(request) {
  const origin = request.headers.origin || '';
  if (origin.startsWith('http://localhost:') || origin.startsWith('http://127.0.0.1:')) return origin;
  return config.frontendOrigin;
}

const API_SECURITY_HEADERS = {
  'Cache-Control': 'no-store',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Cross-Origin-Resource-Policy': 'same-site',
  Vary: 'Origin',
};

function send(response, statusCode, payload, headers = {}) {
  const body = typeof payload === 'string' || Buffer.isBuffer(payload)
    ? payload
    : Buffer.from(JSON.stringify(payload));

  response.writeHead(statusCode, {
    ...API_SECURITY_HEADERS,
    'Content-Length': Buffer.byteLength(body),
    ...headers,
  });
  response.end(body);
}

function sendJson(request, response, statusCode, payload) {
  send(response, statusCode, payload, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': corsOrigin(request),
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-ProGenEDA-User-Email,X-ProGenEDA-Display-Name,X-ProGenEDA-Plan,X-ProGenEDA-Role,X-ProGenEDA-User-Id',
  });
}

function sendNoContent(request, response) {
  response.writeHead(204, {
    ...API_SECURITY_HEADERS,
    'Access-Control-Allow-Origin': corsOrigin(request),
    'Access-Control-Allow-Methods': 'GET,POST,PATCH,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-ProGenEDA-User-Email,X-ProGenEDA-Display-Name,X-ProGenEDA-Plan,X-ProGenEDA-Role,X-ProGenEDA-User-Id',
  });
  response.end();
}

async function readJson(request, maxBytes = 2 * 1024 * 1024) {
  const chunks = [];
  let totalBytes = 0;
  for await (const chunk of request) {
    totalBytes += chunk.length;
    if (totalBytes > maxBytes) {
      const error = new Error('Request body is too large.');
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  if (!chunks.length) return {};

  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch (error) {
    error.statusCode = 400;
    error.message = 'Request body must be JSON.';
    throw error;
  }
}

function isAdvancedGenerationUser(user) {
  return user.role === 'admin' || user.role === 'demo';
}

function assertAiTestRateLimit(user) {
  const now = Date.now();
  const cutoff = now - config.aiTestWindowMs;
  const previous = (aiTestRequestWindows.get(user.id) || []).filter((timestamp) => timestamp >= cutoff);
  if (previous.length >= config.aiTestMaxRequests) {
    const retryAfterSeconds = Math.ceil((previous[0] + config.aiTestWindowMs - now) / 1_000);
    const error = new Error(`AI test limit reached. Try again in ${Math.max(1, retryAfterSeconds)} seconds.`);
    error.statusCode = 429;
    throw error;
  }
  previous.push(now);
  aiTestRequestWindows.set(user.id, previous);
}

function editorAdapterForService(service) {
  if (service === 'KC') {
    return {
      label: 'KiCad JSON Lab',
      build: buildKiCadEditorDocument,
      validate: validateKiCadMainJson,
      apply: applyKiCadNormalChanges,
    };
  }
  if (service === 'LT') {
    return {
      label: 'LTspice JSON Lab',
      build: buildLtspiceEditorDocument,
      validate: validateLtspiceMainJson,
      apply: applyLtspiceNormalChanges,
    };
  }
  if (service === 'EA') {
    return {
      label: 'EasyEDA JSON Lab',
      build: buildEasyedaEditorDocument,
      validate: validateEasyedaMainJson,
      apply: applyEasyedaNormalChanges,
    };
  }
  const error = new Error('JSON editing is unavailable for this generator until its deterministic runtime is integrated.');
  error.statusCode = 409;
  throw error;
}

function assertMainJson(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    const error = new Error('Direct JSON generation requires one JSON object per circuit.');
    error.statusCode = 400;
    throw error;
  }
  return value;
}

function routingModeFromPayload(value) {
  const mode = String(value || 'combination').toLowerCase();
  return ['wire', 'terminal', 'combination'].includes(mode) ? mode : 'combination';
}

function routingModeForService(service, value) {
  const hasExplicitMode = value !== undefined && value !== null && String(value).trim() !== '';
  const mode = routingModeFromPayload(value);
  if (service !== 'LT') return mode;
  if (hasExplicitMode && mode !== 'wire') {
    const error = new Error('LTspice donor-native generation requires routingMode "wire".');
    error.statusCode = 400;
    throw error;
  }
  return 'wire';
}

function animationBudgetFromPayload(value) {
  if (value === undefined || value === null || value === '') return null;
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds > 300) {
    const error = new Error('animationBudgetSeconds must be a positive number no greater than 300 seconds.');
    error.statusCode = 400;
    throw error;
  }
  return seconds;
}

function startNdjson(request, response) {
  response.writeHead(200, {
    ...API_SECURITY_HEADERS,
    'Content-Type': 'application/x-ndjson; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
    'Access-Control-Allow-Origin': corsOrigin(request),
    'Access-Control-Expose-Headers': 'Content-Type',
  });
}

function writeNdjson(response, payload) {
  if (!response.writableEnded && !response.destroyed) {
    response.write(`${JSON.stringify(payload)}\n`);
  }
}

function promptForMainJson(mainJson, fallback = 'Direct JSON circuit generation') {
  return String(
    mainJson?.project?.title
      || mainJson?.project?.name
      || mainJson?.circuit_name
      || mainJson?.project_name
      || fallback,
  );
}

function publicCircuit(circuit) {
  return {
    serial: circuit.serial,
    title: circuit.title,
    description: circuit.description,
    service: circuit.service_name,
    status: circuit.status,
    sharingVisibility: circuit.sharing_visibility,
    componentSummary: circuit.component_summary_json,
    componentCount: circuit.component_count,
    uniqueUserDownloads: circuit.unique_user_downloads,
    totalDownloads: circuit.total_downloads,
    sharedReuseCount: circuit.shared_reuse_count,
    canDownload: circuit.status === 'success' && circuit.export_status === 'ready',
    createdAt: circuit.created_at,
  };
}

function routeMatch(pathname, pattern) {
  const pathParts = pathname.split('/').filter(Boolean);
  const patternParts = pattern.split('/').filter(Boolean);
  if (pathParts.length !== patternParts.length) return null;
  const params = {};

  for (let index = 0; index < patternParts.length; index += 1) {
    const expected = patternParts[index];
    const actual = pathParts[index];
    if (expected.startsWith(':')) {
      params[expected.slice(1)] = decodeURIComponent(actual);
    } else if (expected !== actual) {
      return null;
    }
  }

  return params;
}

function confirmationNameForUser(user) {
  return String(user.displayName || String(user.email || '').split('@')[0] || user.id || 'user')
    .replace(/[^a-z0-9_-]+/gi, '');
}

function expectedKeyConfirmation(user, action) {
  return `i${confirmationNameForUser(user)}wantto${action}`;
}

function assertKeyConfirmation({ user, action, confirmation }) {
  const expected = expectedKeyConfirmation(user, action);
  if (confirmation !== expected) {
    const error = new Error(`Type ${expected} to confirm.`);
    error.statusCode = 400;
    throw error;
  }
}

function positiveNumberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

function publicProviderKeyRecord(key) {
  const fingerprint = String(key.public_key_fingerprint || '').replace(/[^a-z0-9]/gi, '');
  return {
    id: key.id,
    provider: key.provider,
    displayName: key.display_name,
    keyRole: key.key_role,
    environmentVariable: key.environment_variable || null,
    maskedKey: fingerprint.length >= 2 ? `***${fingerprint.slice(-2)}` : '****',
    monthlyTokenLimit: key.monthly_token_limit ?? null,
    ownerEnteredLimitUsd: key.owner_entered_limit_usd ?? null,
    routingAvailable: Boolean(key.routing_available),
    healthStatus: key.health_status,
  };
}

async function handleApi(request, response) {
  const url = new URL(request.url, `http://${request.headers.host || 'localhost'}`);
  const user = authContextFromRequest(request, config);

  if (request.method === 'OPTIONS') {
    sendNoContent(request, response);
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/health') {
    const currentDb = await db.read();
    sendJson(request, response, 200, {
      ok: true,
      service: 'progeneda-local-api',
      storageDriver: 'local',
      dbDriver: 'local_json',
      circuits: currentDb.circuits.length,
      serials: currentDb.serial_registry.length,
    });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/ai/status') {
    sendJson(request, response, 200, {
      ...aiPlannerStatus(config),
      testWindowSeconds: Math.round(config.aiTestWindowMs / 1_000),
      testMaxRequests: config.aiTestMaxRequests,
      serverOnlyCredentials: true,
    });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/example-circuits') {
    const service = String(url.searchParams.get('service') || '').toUpperCase();
    const examples = await listExampleCircuits({ service, config });
    sendJson(request, response, 200, examples);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/prompt-guide/analyze') {
    const payload = await readJson(request, 32 * 1024);
    const prompt = assertSafePrompt(payload.prompt || '');
    sendJson(request, response, 200, analyzeCircuitPrompt({
      prompt,
      targetService: payload.targetService,
    }));
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/prompt-guide/proteus-components') {
    sendJson(request, response, 200, {
      service: 'PR',
      components: proteusComponentGuide(),
      integratedCircuitLimitPerPart: 15,
    });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/ai/test/kicad-plan') {
    if (!isAdvancedGenerationUser(user)) {
      sendJson(request, response, 403, { detail: 'AI planner testing is limited to demo and admin accounts.' });
      return;
    }
    assertAiTestRateLimit(user);
    const payload = await readJson(request, 32 * 1024);
    const prompt = assertSafePrompt(payload.prompt || '');
    const plan = await planKicadMainJson({ prompt, config });
    sendJson(request, response, 200, {
      provider: plan.provider,
      model: plan.model,
      adapter: plan.adapter,
      providerUsage: plan.providerUsage,
      validation: plan.validation,
      mainJson: plan.mainJson,
    });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/admin/config') {
    requireOwnerAdmin(user, config);
    const items = await systemConfigService.listActiveConfigs();
    sendJson(request, response, 200, { items });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/admin/config-audit') {
    requireOwnerAdmin(user, config);
    const items = await systemConfigService.listAudit();
    sendJson(request, response, 200, { items });
    return;
  }

  const adminConfigParams = routeMatch(url.pathname, '/api/admin/config/:configKey');
  if (request.method === 'PATCH' && adminConfigParams) {
    const payload = await readJson(request);
    const item = await systemConfigService.updateConfig({
      configKey: adminConfigParams.configKey,
      value: payload.value,
      reason: payload.reason || '',
      user,
      request,
    });
    sendJson(request, response, 200, { item });
    return;
  }

  const adminRollbackParams = routeMatch(url.pathname, '/api/admin/config/:configKey/rollback');
  if (request.method === 'POST' && adminRollbackParams) {
    const payload = await readJson(request);
    const item = await systemConfigService.rollbackConfig({
      configKey: adminRollbackParams.configKey,
      targetVersion: payload.targetVersion,
      reason: payload.reason || '',
      user,
      request,
    });
    sendJson(request, response, 200, { item });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/admin/model-calls') {
    requireOwnerAdmin(user, config);
    const currentDb = await db.read();
    const limit = Math.min(100, Math.max(1, Number(url.searchParams.get('limit')) || 50));
    const items = [...currentDb.model_calls]
      .sort((left, right) => right.created_at.localeCompare(left.created_at))
      .slice(0, limit);
    sendJson(request, response, 200, { items });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/api-center') {
    requireOwnerAdmin(user, config);
    const currentDb = await db.read();
    const configs = await systemConfigService.activeConfigMap();
    sendJson(request, response, 200, buildApiCenterSnapshot(currentDb, configs, user));
    return;
  }

  const providerKeyParams = routeMatch(url.pathname, '/api/provider-keys/:id');
  if (request.method === 'PATCH' && providerKeyParams) {
    requireOwnerAdmin(user, config);
    const payload = await readJson(request);
    assertKeyConfirmation({ user, action: 'edit', confirmation: payload.confirmation });

    const updated = await db.transact(async (currentDb) => {
      const key = currentDb.provider_keys.find((item) => item.id === providerKeyParams.id);
      if (!key) return null;

      if (payload.apiKeyValue) {
        const error = new Error('Provider credentials are configured server-side and cannot be changed from the browser.');
        error.statusCode = 400;
        throw error;
      }

      if (typeof payload.displayName === 'string' && payload.displayName.trim()) {
        key.display_name = payload.displayName.trim().slice(0, 80);
      }
      const monthlyTokenLimit = positiveNumberOrNull(payload.monthlyTokenLimit);
      if (monthlyTokenLimit !== null) key.monthly_token_limit = Math.round(monthlyTokenLimit);
      const ownerEnteredLimitUsd = positiveNumberOrNull(payload.ownerEnteredLimitUsd);
      if (ownerEnteredLimitUsd !== null) key.owner_entered_limit_usd = ownerEnteredLimitUsd;
      if (payload.limitMode === 'tokens' || payload.limitMode === 'usd') key.limit_mode = payload.limitMode;
      key.updated_at = new Date().toISOString();
      return publicProviderKeyRecord(key);
    });

    if (!updated) {
      sendJson(request, response, 404, { detail: 'Provider key not found.' });
      return;
    }

    sendJson(request, response, 200, { providerKey: updated });
    return;
  }

  if (request.method === 'DELETE' && providerKeyParams) {
    requireOwnerAdmin(user, config);
    const payload = await readJson(request);
    assertKeyConfirmation({ user, action: 'delete', confirmation: payload.confirmation });

    const deleted = await db.transact((currentDb) => {
      const index = currentDb.provider_keys.findIndex((item) => item.id === providerKeyParams.id);
      if (index === -1) return null;
      const [removed] = currentDb.provider_keys.splice(index, 1);
      currentDb.deleted_provider_key_ids = currentDb.deleted_provider_key_ids || [];
      if (!currentDb.deleted_provider_key_ids.includes(removed.id)) {
        currentDb.deleted_provider_key_ids.push(removed.id);
      }
      return publicProviderKeyRecord({ ...removed, health_status: 'deleted', routing_available: false });
    });

    if (!deleted) {
      sendJson(request, response, 404, { detail: 'Provider key not found.' });
      return;
    }

    sendJson(request, response, 200, { providerKey: deleted });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/admin/provider-usage-sync') {
    requireOwnerAdmin(user, config);
    const job = await db.transact((currentDb) => {
      const createdAt = new Date().toISOString();
      const record = {
        id: createId('job'),
        type: 'provider_usage_sync',
        status: 'pending',
        payload_json: { requestedByUserId: user.id },
        created_at: createdAt,
        started_at: null,
        completed_at: null,
        expires_at: null,
        error_message: '',
      };
      currentDb.jobs.push(record);
      return record;
    });
    sendJson(request, response, 202, { jobId: job.id, status: job.status });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/generate/stream') {
    try {
      const payload = await readJson(request);
      const mainJson = payload.mainJson == null ? null : assertMainJson(payload.mainJson);
      if (mainJson && !isAdvancedGenerationUser(user)) {
        sendJson(request, response, 403, { detail: 'Direct JSON generation is limited to admin and demo accounts.' });
        return;
      }
      const targetService = String(payload.targetService || '').toUpperCase();
      if (!['LT', 'EA'].includes(targetService)) {
        sendJson(request, response, 400, { detail: 'The executable progress stream is available for LTspice and EasyEDA.' });
        return;
      }
      const prompt = assertSafePrompt(payload.prompt || promptForMainJson(mainJson));
      const routingMode = routingModeForService(targetService, payload.routingMode);
      const animationBudgetSeconds = animationBudgetFromPayload(payload.animationBudgetSeconds);
      startNdjson(request, response);
      writeNdjson(response, {
        event: 'accepted',
        service: targetService,
        routingMode,
        animationBudgetSeconds,
      });
      const result = await circuitService.generateCircuit({
        prompt,
        service: targetService,
        user,
        reuseOptOut: Boolean(payload.reuseOptOut),
        mainJson,
        routingMode,
        animationBudgetSeconds,
        onProgress: (event) => writeNdjson(response, event),
      });
      writeNdjson(response, { event: 'result', result });
      response.end();
    } catch (error) {
      if (response.headersSent) {
        writeNdjson(response, {
          event: 'error',
          detail: error instanceof Error ? error.message : 'Executable progress stream failed.',
        });
        response.end();
      } else {
        throw error;
      }
    }
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/generate') {
    const payload = await readJson(request);
    const mainJson = payload.mainJson == null ? null : assertMainJson(payload.mainJson);
    if (mainJson && !isAdvancedGenerationUser(user)) {
      sendJson(request, response, 403, { detail: 'Direct JSON generation is limited to admin and demo accounts.' });
      return;
    }
    const prompt = assertSafePrompt(payload.prompt || promptForMainJson(mainJson));
    const targetService = String(payload.targetService || 'PR').toUpperCase();
    const service = ['PR', 'PS', 'KC', 'LT', 'EA', 'AL'].includes(targetService) ? targetService : 'PR';
    const result = await circuitService.generateCircuit({
      prompt,
      service,
      user,
      reuseOptOut: Boolean(payload.reuseOptOut),
      mainJson,
      routingMode: routingModeForService(service, payload.routingMode),
    });

    sendJson(request, response, result.status === 'success' ? 200 : 422, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/generate/batch') {
    if (!isAdvancedGenerationUser(user)) {
      sendJson(request, response, 403, { detail: 'Multiple-circuit generation is limited to admin and demo accounts.' });
      return;
    }

    const payload = await readJson(request, 24 * 1024 * 1024);
    const items = Array.isArray(payload.items) ? payload.items : [];
    if (items.length < 1 || items.length > 50) {
      sendJson(request, response, 400, { detail: 'A batch must contain between 1 and 50 JSON circuits.' });
      return;
    }

    const targetService = String(payload.targetService || 'KC').toUpperCase();
    const service = ['PR', 'KC', 'LT', 'EA'].includes(targetService) ? targetService : 'KC';
    const routingMode = routingModeForService(service, payload.routingMode);
    const manifest = [];
    const entries = [];

    const processBatchItem = async (item, index) => {
      const label = String(item?.name || `circuit-${String(index + 1).padStart(2, '0')}.json`);
      try {
        const mainJson = assertMainJson(item?.mainJson ?? item);
        const prompt = assertSafePrompt(item?.prompt || promptForMainJson(mainJson, label));
        const result = await circuitService.generateCircuit({ prompt, service, user, mainJson, routingMode });
        let entry = null;

        if (result.status === 'success' && result.serial) {
          const lookup = await circuitService.exportArtifactForSerial(result.serial);
          if (lookup) {
            entry = {
              name: `${String(index + 1).padStart(2, '0')}-${result.serial}/${lookup.artifact.file_name}`,
              content: await storage.getExportArtifact(lookup.artifact.path),
            };
          }
        }

        return {
          entry,
          manifestItem: {
            index,
            inputName: label,
            status: result.status,
            serial: result.serial || null,
            fileName: result.fileName || null,
            errorMessage: result.errorMessage || null,
          },
        };
      } catch (error) {
        return {
          entry: null,
          manifestItem: {
            index,
            inputName: label,
            status: 'failed',
            serial: null,
            fileName: null,
            errorMessage: error instanceof Error ? error.message : 'Batch item failed.',
          },
        };
      }
    };

    const concurrency = Math.min(4, items.length);
    for (let offset = 0; offset < items.length; offset += concurrency) {
      const chunk = items.slice(offset, offset + concurrency);
      const results = await Promise.all(chunk.map((item, chunkIndex) => processBatchItem(item, offset + chunkIndex)));
      for (const result of results) {
        manifest.push(result.manifestItem);
        if (result.entry) entries.push(result.entry);
      }
    }

    entries.push({ name: 'batch-manifest.json', content: JSON.stringify({ service, routingMode, items: manifest }, null, 2) });
    const successful = manifest.filter((item) => item.status === 'success').length;
    if (successful === 0) {
      sendJson(request, response, 422, { detail: 'Every circuit in the batch failed generation.', items: manifest });
      return;
    }

    const batchFileName = buildBatchFileName({ service, itemCount: items.length });
    const buffer = createStoredZip(entries);
    send(response, 200, buffer, {
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename="${batchFileName}"`,
      'X-ProGenEDA-Batch-Succeeded': String(successful),
      'X-ProGenEDA-Batch-Total': String(items.length),
      'Access-Control-Allow-Origin': corsOrigin(request),
      'Access-Control-Expose-Headers': 'Content-Disposition,X-ProGenEDA-Batch-Succeeded,X-ProGenEDA-Batch-Total',
    });
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/history') {
    const result = await circuitService.history({
      userId: user.id,
      status: url.searchParams.get('status') || 'all',
      service: url.searchParams.get('service') || 'all',
      cursor: url.searchParams.get('cursor') || '0',
      limit: url.searchParams.get('limit') || '10',
    });
    sendJson(request, response, 200, result);
    return;
  }

  const historyItemParams = routeMatch(url.pathname, '/api/history/:id');
  if (request.method === 'DELETE' && historyItemParams) {
    const card = await circuitService.softDeleteById({ id: historyItemParams.id, user });
    if (!card) {
      sendJson(request, response, 404, { detail: 'Circuit not found.' });
      return;
    }
    sendJson(request, response, 200, { historyCard: card });
    return;
  }

  const editorParams = routeMatch(url.pathname, '/api/circuits/:serial/editor');
  if (request.method === 'GET' && editorParams) {
    const source = await circuitService.editorSourceForSerial({ serial: editorParams.serial, user });
    const adapter = editorAdapterForService(source.circuit.service);
    const canUseAdvanced = user.role === 'admin' || user.role === 'demo';
    const document = adapter.build(source.mainJson, {
      includeRawJson: canUseAdvanced,
      sourceMainJson: source.mainJson,
      mode: 'guided',
    });
    sendJson(request, response, 200, {
      serial: source.circuit.serial,
      title: source.circuit.title,
      service: source.circuit.service,
      editorLabel: adapter.label,
      canUseAdvanced,
      ...document,
    });
    return;
  }

  const editorValidateParams = routeMatch(url.pathname, '/api/circuits/:serial/editor/validate');
  if (request.method === 'POST' && editorValidateParams) {
    const payload = await readJson(request, 6 * 1024 * 1024);
    const source = await circuitService.editorSourceForSerial({ serial: editorValidateParams.serial, user });
    const adapter = editorAdapterForService(source.circuit.service);
    const isAdvanced = payload.mode === 'advanced';
    let mainJson;
    let validation;
    let guidedAudit = null;

    if (isAdvanced) {
      assertAdvancedEditorAccess(user);
      mainJson = assertMainJson(payload.mainJson);
      validation = adapter.validate(mainJson);
    } else {
      const result = adapter.apply(source.mainJson, payload.changes);
      mainJson = result.mainJson;
      validation = result.validation;
      guidedAudit = result.audit || null;
    }

    const document = adapter.build(mainJson, {
      includeRawJson: isAdvanced,
      sourceMainJson: source.mainJson,
      mode: isAdvanced ? 'advanced' : 'guided',
      audit: guidedAudit,
    });
    await db.transact((currentDb) => {
      currentDb.editor_audit.push({
        id: createId('editor_audit'),
        circuit_id: source.circuit.id,
        serial: source.circuit.serial,
        user_id: user.id,
        mode: isAdvanced ? 'advanced' : 'guided',
        source_digest: document.evidence?.sourceDigest || null,
        candidate_topology_digest: document.evidence?.candidateTopologyDigest || null,
        topology_preserved: Boolean(document.evidence?.topologyPreserved),
        changed_field_ids: guidedAudit?.changedFieldIds || [],
        validation_status: validation.valid ? 'passed' : 'failed',
        created_at: new Date().toISOString(),
      });
      return null;
    });

    sendJson(request, response, 200, {
      serial: source.circuit.serial,
      canUseAdvanced: user.role === 'admin' || user.role === 'demo',
      editorLabel: adapter.label,
      ...document,
      validation,
    });
    return;
  }

  const editorRegenerateParams = routeMatch(url.pathname, '/api/circuits/:serial/editor/regenerate');
  if (request.method === 'POST' && editorRegenerateParams) {
    const payload = await readJson(request, 6 * 1024 * 1024);
    const source = await circuitService.editorSourceForSerial({ serial: editorRegenerateParams.serial, user });
    const adapter = editorAdapterForService(source.circuit.service);
    const isAdvanced = payload.mode === 'advanced';
    let mainJson;

    if (isAdvanced) {
      assertAdvancedEditorAccess(user);
      mainJson = assertMainJson(payload.mainJson);
      const validation = adapter.validate(mainJson);
      if (!validation.valid) {
        const error = new Error(`The advanced JSON does not pass ${adapter.label} validation.`);
        error.statusCode = 422;
        error.issues = validation.issues;
        throw error;
      }
    } else {
      mainJson = adapter.apply(source.mainJson, payload.changes).mainJson;
    }

    const result = await circuitService.regenerateEditedCircuit({
      serial: editorRegenerateParams.serial,
      user,
      mainJson,
      routingMode: routingModeForService(source.circuit.service, payload.routingMode),
    });
    sendJson(request, response, result.status === 'success' ? 200 : 422, result);
    return;
  }

  const circuitParams = routeMatch(url.pathname, '/api/circuits/:serial');
  if (request.method === 'GET' && circuitParams) {
    try {
      parseSerial(circuitParams.serial);
    } catch (error) {
      sendJson(request, response, 400, { detail: error.message });
      return;
    }

    const circuit = await circuitService.getCircuitBySerial(circuitParams.serial);
    if (!circuit) {
      sendJson(request, response, 404, { detail: 'Circuit not found.' });
      return;
    }

    sendJson(request, response, 200, publicCircuit(circuit));
    return;
  }

  const copyParams = routeMatch(url.pathname, '/api/circuits/:serial/copy-serial');
  if (request.method === 'POST' && copyParams) {
    const card = await circuitService.copySerial({ serial: copyParams.serial, userId: user.id });
    if (!card) {
      sendJson(request, response, 404, { detail: 'Circuit not found.' });
      return;
    }
    sendJson(request, response, 200, { ok: true, historyCard: card });
    return;
  }

  const downloadPostParams = routeMatch(url.pathname, '/api/circuits/:serial/download');
  if (request.method === 'POST' && downloadPostParams) {
    const circuit = await circuitService.recordDownload({
      serial: downloadPostParams.serial,
      userId: user.id,
      source: 'owner_history',
    });
    if (!circuit) {
      sendJson(request, response, 404, { detail: 'Download unavailable.' });
      return;
    }
    sendJson(request, response, 200, {
      downloadUrl: storage.createDownloadHandle(downloadPostParams.serial),
      fileName: (await circuitService.exportArtifactForSerial(downloadPostParams.serial))?.artifact?.file_name || 'project.bin',
    });
    return;
  }

  const downloadParams = routeMatch(url.pathname, '/api/download/export/:serial');
  if (request.method === 'GET' && downloadParams) {
    const lookup = await circuitService.exportArtifactForSerial(downloadParams.serial);
    if (!lookup) {
      sendJson(request, response, 404, { detail: 'Download unavailable.' });
      return;
    }

    await circuitService.recordDownload({
      serial: downloadParams.serial,
      userId: user.id,
      source: url.searchParams.get('source') || 'direct_share_link',
    });

    const buffer = await storage.getExportArtifact(lookup.artifact.path);
    send(response, 200, buffer, {
      'Content-Type': lookup.artifact.mime_type,
      'Content-Disposition': `attachment; filename="${lookup.artifact.file_name}"`,
      'Access-Control-Allow-Origin': corsOrigin(request),
    });
    return;
  }

  const rehydrateParams = routeMatch(url.pathname, '/api/circuits/:serial/rehydrate');
  if (request.method === 'POST' && rehydrateParams) {
    const job = await db.transact((currentDb) => {
      const createdAt = new Date().toISOString();
      const record = {
        id: createId('job'),
        type: 'rehydrate_export',
        status: 'pending',
        payload_json: { serial: rehydrateParams.serial },
        created_at: createdAt,
        started_at: null,
        completed_at: null,
        expires_at: null,
        error_message: '',
      };
      currentDb.jobs.push(record);
      return record;
    });
    sendJson(request, response, 202, { jobId: job.id, status: job.status });
    return;
  }

  const jobParams = routeMatch(url.pathname, '/api/jobs/:jobId');
  if (request.method === 'GET' && jobParams) {
    const currentDb = await db.read();
    const job = currentDb.jobs.find((item) => item.id === jobParams.jobId);
    if (!job) {
      sendJson(request, response, 404, { detail: 'Job not found.' });
      return;
    }
    sendJson(request, response, 200, job);
    return;
  }

  const reuseParams = routeMatch(url.pathname, '/api/circuits/:serial/reuse-eligibility');
  if (request.method === 'PATCH' && reuseParams) {
    const payload = await readJson(request);
    const reuseEligibility = payload.reuseEligibility === 'not_eligible' ? 'not_eligible' : 'eligible';
    const card = await circuitService.setReuseEligibility({
      serial: reuseParams.serial,
      user,
      reuseEligibility,
    });
    if (!card) {
      sendJson(request, response, 403, { detail: 'Reuse eligibility can only be changed by premium owners.' });
      return;
    }
    sendJson(request, response, 200, { historyCard: card });
    return;
  }

  if (request.method === 'DELETE' && circuitParams) {
    const card = await circuitService.softDelete({ serial: circuitParams.serial, user });
    if (!card) {
      sendJson(request, response, 404, { detail: 'Circuit not found.' });
      return;
    }
    sendJson(request, response, 200, { historyCard: card });
    return;
  }

  sendJson(request, response, 404, { detail: 'Not found.' });
}

async function main() {
  await mkdir(config.localDataDir, { recursive: true });
  await storage.ensureBaseContainers();
  await systemConfigService.ensureDefaults();

  const server = createServer((request, response) => {
    handleApi(request, response).catch((error) => {
      const statusCode = error.statusCode || 500;
      sendJson(request, response, statusCode, {
        detail: statusCode >= 500 ? 'Local API failed unexpectedly.' : error.message,
        ...(Array.isArray(error.issues) ? { issues: error.issues } : {}),
      });
      if (statusCode >= 500) console.error(error);
    });
  });

  server.listen(config.port, '127.0.0.1', () => {
    console.log(`[api] ProGenEDA local API listening on http://127.0.0.1:${config.port}`);
  });
}

main();
