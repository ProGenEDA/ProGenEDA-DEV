import { createHash } from 'node:crypto';
import { buildSerialParts, randomBase62Suffix } from '../../../../packages/serial-system/index.mjs';
import {
  componentSummaryToCodeCounts,
  loadComponentRegistry,
  normalizeComponentSummary,
  validateComponentSummary,
} from '../../../../packages/component-registry/index.mjs';
import {
  createId,
  timestamps,
  toHistoryCard,
  touch,
  upsertUser,
} from '../../../../packages/db-adapter/local-json-db.mjs';
import { readStoredZipEntry } from '../../../../packages/storage-adapter/zip-writer.mjs';
import {
  descriptionFromPrompt,
  titleFromPrompt,
} from './component-summary.mjs';
import {
  finalizeModelCall,
  planModelCall,
} from './cost-router-service.mjs';
import { generateCircuitArtifact } from './circuit-generation-service.mjs';
import { buildExportFileName } from './artifact-naming.mjs';
import {
  assertKiCadEditorSource,
  sourceMainJsonFromInternalCircuit,
} from './kicad-json-editor-service.mjs';
import { assertLtspiceEditorSource } from './ltspice-json-editor-service.mjs';
import { assertEasyedaEditorSource } from './easyeda-json-editor-service.mjs';
import { selectDeterministicExampleCircuit } from './example-circuit-library-service.mjs';

const SERVICE_NAMES = {
  PR: 'Proteus',
  PS: 'PSpice',
  KC: 'KiCad',
  LT: 'LTspice',
  EA: 'EasyEDA Pro',
  AL: 'Altium',
};

function sha256Text(value) {
  return createHash('sha256').update(String(value)).digest('hex');
}

function nowIso() {
  return new Date().toISOString();
}

function safeTokenCount(value) {
  return Number.isFinite(value) && value >= 0 ? Number(value) : null;
}

function estimateActualCostUsd({
  pricing,
  model,
  inputTokens,
  outputTokens,
  usageBufferPercent = 0,
}) {
  if (!model || inputTokens === null || outputTokens === null) return null;
  const modelPricing = pricing?.[model];
  if (!modelPricing) return null;
  const multiplier = 1 + Math.max(0, Number(usageBufferPercent || 0)) / 100;
  const inputCost = (inputTokens / 1_000_000) * Number(modelPricing.inputPer1M || 0);
  const outputCost = (outputTokens / 1_000_000) * Number(modelPricing.outputPer1M || 0);
  return Number(((inputCost + outputCost) * multiplier).toFixed(8));
}

function reuseEligibilityForUser(user, requestedOptOut = false) {
  const isPrivileged = user.plan === 'premium' || user.role === 'admin';

  if (isPrivileged && requestedOptOut) {
    return {
      reuseEligibility: 'not_eligible',
      reuseEligibilityReason: user.role === 'admin' ? 'admin_opt_out' : 'premium_opt_out',
    };
  }

  if (isPrivileged) {
    return {
      reuseEligibility: 'eligible',
      reuseEligibilityReason: user.role === 'admin' ? 'admin_allowed' : 'premium_allowed',
    };
  }

  return {
    reuseEligibility: 'eligible',
    reuseEligibilityReason: 'free_default',
  };
}

function artifactScopeForUser(user) {
  if (user.plan === 'premium' || user.role === 'admin') {
    return {
      storageScope: 'user_private',
      reason: user.role === 'admin' ? 'admin_private' : 'premium_private',
    };
  }

  return {
    storageScope: 'shared_global',
    reason: 'free_shared_pool',
  };
}

function createSerialWithoutCollision(db, componentSummary, service, tableVersion) {
  for (let attempt = 0; attempt < 25; attempt += 1) {
    const serialParts = buildSerialParts({
      componentSummary,
      service,
      tableVersion,
      suffix: randomBase62Suffix(),
    });

    if (!db.serial_registry.some((entry) => entry.serial === serialParts.serial)) {
      return serialParts;
    }
  }

  throw new Error('Could not create a unique serial.');
}

function artifactRecord({ serial, circuitId, version, artifactType, storageVisibility, storageScope, storageArtifact }) {
  return {
    id: createId('artifact'),
    serial,
    circuit_id: circuitId,
    version,
    artifact_type: artifactType,
    storage_visibility: storageVisibility,
    storage_scope: storageScope,
    path: storageArtifact.path,
    file_name: storageArtifact.fileName,
    mime_type: storageArtifact.mimeType,
    size_bytes: storageArtifact.sizeBytes,
    sha256: storageArtifact.sha256,
    created_at: nowIso(),
  };
}

export class CircuitService {
  constructor({ db, storage, config, systemConfigService }) {
    this.db = db;
    this.storage = storage;
    this.config = config;
    this.systemConfigService = systemConfigService;
  }

  async generateCircuit({
    prompt,
    service = 'PR',
    user,
    reuseOptOut = false,
    mainJson = null,
    routingMode = 'combination',
    animationBudgetSeconds = null,
    onProgress = null,
  }) {
    const tableVersion = 'A';
    const normalizedPrompt = prompt.trim();
    const generationRunId = createId('run');
    const requestStartedAt = nowIso();
    const promptHash = sha256Text(normalizedPrompt);
    const persistedUser = await this.db.transact((db) => upsertUser(db, user));
    let routingPlan = null;
    let deterministicExample = null;
    let resolvedMainJson = mainJson;

    try {
      // Library examples run before any model router. Their canonical JSON
      // stays server-side and is still passed through the native validator.
      if (!resolvedMainJson) {
        deterministicExample = await selectDeterministicExampleCircuit({
          service,
          prompt: normalizedPrompt,
          config: this.config,
        });
        if (deterministicExample) {
          resolvedMainJson = deterministicExample.mainJson;
          onProgress?.({
            event: 'stage',
            stage: 'select_verified_example',
            message: `Retrieving verified example: ${deterministicExample.title}`,
          });
        }
      }

      // Direct JSON and deterministic example matches never call a model.
      // Only an explicitly configured OpenAI KiCad planner is model-backed
      // in the active local workspace.
      const requiresRoutedModelCall = !resolvedMainJson
        && ['KC', 'EA'].includes(service)
        && this.config.aiProvider === 'openai';
      if (requiresRoutedModelCall) {
        routingPlan = await planModelCall({
          db: this.db,
          systemConfigService: this.systemConfigService,
          user: persistedUser,
          prompt: normalizedPrompt,
          service,
          route: 'json_generate',
          validationFailures: 0,
          generationRunId,
          promptHash,
        });
      }

      const generated = await generateCircuitArtifact({
        prompt: normalizedPrompt,
        service,
        config: this.config,
        routingPlan,
        mainJson: resolvedMainJson,
        routingMode,
        animationBudgetSeconds,
        onProgress,
      });
      const circuitTitle = deterministicExample?.title || titleFromPrompt(normalizedPrompt);
      const exportFileName = buildExportFileName({
        service,
        title: circuitTitle,
        sourceFileName: generated.fileName,
      });
      const sourceMainJson = generated.sourceMainJson
        || generated.internalCircuit?.mainJson
        || resolvedMainJson
        || null;
      generated.internalCircuit = {
        ...(generated.internalCircuit || {}),
        mainJson: sourceMainJson,
        exportFileName,
        exampleLibrary: deterministicExample
          ? {
              id: deterministicExample.id,
              title: deterministicExample.title,
              service: deterministicExample.service,
              matchType: deterministicExample.matchType,
            }
          : null,
      };
      generated.generationMetadata = {
        ...(generated.generationMetadata || {}),
        exportFileName,
        deterministicExample: deterministicExample
          ? {
              id: deterministicExample.id,
              title: deterministicExample.title,
              matchType: deterministicExample.matchType,
            }
          : null,
      };
      const actualInputTokens = safeTokenCount(generated.providerUsage?.inputTokens);
      const actualOutputTokens = safeTokenCount(generated.providerUsage?.outputTokens);
      const activeConfigs = await this.systemConfigService.activeConfigMap();
      const actualCostEstimateUsd = estimateActualCostUsd({
        pricing: activeConfigs.model_pricing,
        model: generated.modelRouting?.model,
        inputTokens: actualInputTokens,
        outputTokens: actualOutputTokens,
        usageBufferPercent: activeConfigs.key_safety_limits?.usageAccountingBufferPercent ?? 5,
      });
      const registry = loadComponentRegistry(service, tableVersion);
      // Proteus has an explicitly bounded production catalogue. KiCad and
      // LTspice and EasyEDA retain their own deterministic runtime/catalogue validation.
      const componentValidation = service === 'PR'
        ? validateComponentSummary(generated.componentSummary, registry)
        : { valid: true, normalized: normalizeComponentSummary(generated.componentSummary, registry), issues: [] };
      if (!componentValidation.valid) {
        const error = new Error(componentValidation.issues.map((issue) => issue.message).join(' '));
        error.statusCode = 422;
        error.issues = componentValidation.issues;
        throw error;
      }
      const normalizedSummary = componentValidation.normalized;
      const codeCounts = componentSummaryToCodeCounts(normalizedSummary, registry);
      const componentCount = codeCounts.reduce((total, item) => total + item.count, 0);
      const serialParts = await this.db.transact((db) => createSerialWithoutCollision(db, normalizedSummary, service, tableVersion));
      const serial = serialParts.serial;
      const circuitId = createId('circuit');
      const version = 1;
      const artifactScope = artifactScopeForUser(persistedUser);
      const exportArtifact = await this.storage.saveExportArtifact({
        service,
        serial,
        version,
        fileName: exportFileName,
        buffer: generated.exportBuffer,
      });
      const internalBundle = await this.storage.saveInternalBundle({
        userId: persistedUser.id,
        service,
        serial,
        version,
        storageScope: artifactScope.storageScope,
        circuit: generated.internalCircuit,
        originalPrompt: prompt,
        normalizedPrompt,
        validationReport: generated.validationReport,
        modelRouting: generated.modelRouting,
        generationMetadata: generated.generationMetadata,
        routerPlan: routingPlan,
        componentSummary: normalizedSummary,
        sourceMainJson,
        exportFileName,
        exportBuffer: generated.exportBuffer,
      });
      const reuse = reuseEligibilityForUser(persistedUser, reuseOptOut);

      const result = await this.db.transact((db) => {
        const created = timestamps();
        const circuit = {
          id: circuitId,
          owner_user_id: persistedUser.id,
          serial,
          service,
          service_name: SERVICE_NAMES[service] || service,
          table_version: tableVersion,
          title: circuitTitle,
          description: descriptionFromPrompt(normalizedPrompt),
          status: 'success',
          sharing_visibility: 'shareable_by_serial',
          reuse_eligibility: reuse.reuseEligibility,
          reuse_eligibility_reason: reuse.reuseEligibilityReason,
          artifact_storage_scope: artifactScope.storageScope,
          artifact_storage_reason: artifactScope.reason,
          component_summary_json: normalizedSummary,
          compressed_bom_code: serialParts.compressedBomCode,
          canonical_bom_code: serialParts.canonicalBomCode,
          component_count: componentCount,
          component_type_count: codeCounts.length,
          latest_version: version,
          total_downloads: 0,
          unique_user_downloads: 0,
          shared_reuse_count: 0,
          copy_serial_count: 0,
          export_status: 'ready',
          thumbnail_path: '',
          error_message: '',
          ...created,
        };

        db.circuits.push(circuit);
        db.serial_registry.push({
          serial,
          circuit_id: circuitId,
          owner_user_id: persistedUser.id,
          service,
          table_version: tableVersion,
          compressed_bom_code: serialParts.compressedBomCode,
          canonical_bom_code: serialParts.canonicalBomCode,
          suffix: serialParts.suffix,
          status: 'active',
          created_at: created.created_at,
        });
        db.circuit_versions.push({
          id: createId('version'),
          circuit_id: circuitId,
          serial,
          version,
          change_type: 'initial_generation',
          internal_bundle_path: internalBundle.path,
          export_artifact_path: exportArtifact.path,
          created_at: created.created_at,
          sha256: exportArtifact.sha256,
        });
        db.artifacts.push(
          artifactRecord({
            serial,
            circuitId,
            version,
            artifactType: 'internal_bundle',
            storageVisibility: 'internal_only',
            storageScope: artifactScope.storageScope,
            storageArtifact: internalBundle,
          }),
          artifactRecord({
            serial,
            circuitId,
            version,
            artifactType: 'export_project_file',
            storageVisibility: 'user_downloadable',
            storageScope: 'serial_shareable_export',
            storageArtifact: exportArtifact,
          }),
        );
        db.generation_runs.push({
          id: generationRunId,
          user_id: persistedUser.id,
          circuit_id: circuitId,
          status: 'success',
          input_prompt_hash: promptHash,
          model_call_id: routingPlan?.modelCallId || null,
          provider_key_id: routingPlan?.providerKeyId || null,
          model_used: generated.modelRouting?.model || routingPlan?.selectedModel || 'none',
          model_tier: resolvedMainJson ? 'none' : routingPlan?.selectedTier || 'external-planner',
          model_route: deterministicExample
            ? 'deterministic_example_library'
            : resolvedMainJson
              ? 'direct_json'
              : routingPlan?.route || 'kicad_json_plan',
          key_role: routingPlan?.keyRole || 'server_configured',
          validation_retry_count: 0,
          estimated_cost: routingPlan?.estimatedCostUsd || null,
          estimated_input_tokens: routingPlan?.inputTokens || null,
          estimated_output_tokens: routingPlan?.estimatedOutputTokens || null,
          actual_input_tokens: actualInputTokens,
          actual_output_tokens: actualOutputTokens,
          created_at: requestStartedAt,
          completed_at: nowIso(),
        });

        if (circuit.reuse_eligibility === 'eligible') {
          db.reuse_candidates.push({
            id: createId('reuse'),
            source_circuit_id: circuitId,
            serial,
            service,
            component_summary_json: normalizedSummary,
            tags_json: [],
            quality_score: 0.72,
            approved_status: 'pending_review',
            created_at: created.created_at,
          });
        }

        return {
          serial,
          status: 'success',
          historyCard: toHistoryCard(circuit),
          downloadUrl: this.storage.createDownloadHandle(serial),
          fileName: exportFileName,
        };
      });

      if (routingPlan) {
        await finalizeModelCall({
          db: this.db,
          modelCallId: routingPlan.modelCallId,
          reservationId: routingPlan.reservationId,
          status: 'success',
          actualInputTokens,
          actualOutputTokens,
          actualCostEstimateUsd,
          actualProviderModel: generated.modelRouting?.model || null,
          providerUsageSource: generated.providerUsage?.source || '',
        });
      }

      return result;
    } catch (error) {
      if (routingPlan) {
        await finalizeModelCall({
          db: this.db,
          modelCallId: routingPlan.modelCallId,
          reservationId: routingPlan.reservationId,
          status: 'failed',
          errorMessage: error instanceof Error ? error.message : 'Generation failed.',
        });
      }
      return this.recordFailedGeneration({
        user: persistedUser,
        prompt: normalizedPrompt,
        service,
        generationRunId,
        requestStartedAt,
        error,
        promptHash,
        routingPlan,
      });
    }
  }

  async recordFailedGeneration({ user, prompt, service, generationRunId, requestStartedAt, error, promptHash, routingPlan }) {
    return this.db.transact((db) => {
      const circuitId = createId('circuit');
      const created = timestamps();
      const message = error instanceof Error && error.message ? error.message : 'Generation failed.';
      const circuit = {
        id: circuitId,
        owner_user_id: user.id,
        serial: null,
        service,
        service_name: SERVICE_NAMES[service] || service,
        table_version: 'A',
        title: titleFromPrompt(prompt),
        description: descriptionFromPrompt(prompt),
        status: 'failed',
        sharing_visibility: 'shareable_by_serial',
        reuse_eligibility: 'not_eligible',
        reuse_eligibility_reason: 'generation_failed',
        component_summary_json: {},
        compressed_bom_code: '',
        canonical_bom_code: '',
        component_count: 0,
        component_type_count: 0,
        latest_version: 0,
        total_downloads: 0,
        unique_user_downloads: 0,
        shared_reuse_count: 0,
        copy_serial_count: 0,
        export_status: 'failed',
        thumbnail_path: '',
        error_message: message,
        ...created,
      };

      db.circuits.push(circuit);
      db.generation_runs.push({
        id: generationRunId,
        user_id: user.id,
        circuit_id: circuitId,
        status: 'failed',
        input_prompt_hash: promptHash || sha256Text(prompt),
        model_call_id: routingPlan?.modelCallId || null,
        provider_key_id: routingPlan?.providerKeyId || null,
        model_used: routingPlan?.selectedModel || 'none',
        model_tier: routingPlan?.selectedTier || 'none',
        model_route: routingPlan?.route || 'none',
        key_role: routingPlan?.keyRole || 'none',
        validation_retry_count: 0,
        estimated_cost: routingPlan?.estimatedCostUsd || null,
        estimated_input_tokens: routingPlan?.inputTokens || null,
        estimated_output_tokens: routingPlan?.estimatedOutputTokens || null,
        actual_input_tokens: null,
        actual_output_tokens: null,
        created_at: requestStartedAt,
        completed_at: nowIso(),
        error_message: message,
      });

      return {
        serial: null,
        status: 'failed',
        errorMessage: message,
        historyCard: toHistoryCard(circuit),
      };
    });
  }

  async history({ userId, status = 'all', service = 'all', cursor = 0, limit = 10 }) {
    const db = await this.db.read();
    const offset = Math.max(0, Number(cursor) || 0);
    const pageSize = Math.min(50, Math.max(1, Number(limit) || 10));
    const filtered = db.circuits
      .filter((circuit) => circuit.owner_user_id === userId)
      .filter((circuit) => !['deleted', 'disabled'].includes(circuit.status))
      .filter((circuit) => status === 'all' || circuit.status === status)
      .filter((circuit) => service === 'all' || circuit.service === service)
      .sort((left, right) => right.created_at.localeCompare(left.created_at));
    const items = filtered.slice(offset, offset + pageSize).map(toHistoryCard);
    const nextCursor = offset + pageSize < filtered.length ? String(offset + pageSize) : null;

    return { items, nextCursor, total: filtered.length };
  }

  async getCircuitBySerial(serial) {
    const db = await this.db.read();
    const circuit = db.circuits.find((item) => item.serial === serial);
    if (!circuit || ['deleted', 'disabled'].includes(circuit.status)) return null;
    return circuit;
  }

  async editorSourceForSerial({ serial, user }) {
    const db = await this.db.read();
    const circuit = db.circuits.find((item) => item.serial === serial);
    if (circuit?.service === 'KC') assertKiCadEditorSource(circuit, user);
    else if (circuit?.service === 'LT') assertLtspiceEditorSource(circuit, user);
    else if (circuit?.service === 'EA') assertEasyedaEditorSource(circuit, user);
    else {
      const error = new Error('JSON editing is unavailable for this generator until its deterministic runtime is integrated.');
      error.statusCode = 409;
      throw error;
    }

    const artifact = db.artifacts.find((item) => (
      item.serial === serial
      && item.artifact_type === 'internal_bundle'
      && item.storage_visibility === 'internal_only'
    ));
    if (!artifact) {
      const error = new Error('The internal CircuitIR bundle is unavailable for this circuit.');
      error.statusCode = 404;
      throw error;
    }

    const bundle = await this.storage.getInternalArtifact(artifact.path);
    const sourceEntry = readStoredZipEntry(bundle, 'internal/source-main.json');
    const circuitEntry = readStoredZipEntry(bundle, 'internal/circuit.json');
    let storedSource = null;
    let internalCircuit = null;

    try {
      storedSource = sourceEntry ? JSON.parse(sourceEntry.toString('utf8')) : null;
      internalCircuit = circuitEntry ? JSON.parse(circuitEntry.toString('utf8')) : null;
    } catch {
      const error = new Error('The stored CircuitIR bundle is malformed.');
      error.statusCode = 422;
      throw error;
    }

    const mainJson = sourceMainJsonFromInternalCircuit(internalCircuit, storedSource);
    if (!mainJson) {
      const error = new Error('This earlier export did not retain its editable source JSON. Generate it again to enable JSON Lab.');
      error.statusCode = 409;
      throw error;
    }

    return { circuit, mainJson };
  }

  async regenerateEditedCircuit({ serial, user, mainJson, routingMode = 'combination' }) {
    const source = await this.editorSourceForSerial({ serial, user });
    const prompt = String(
      mainJson?.project?.title
      || mainJson?.project?.name
      || source.circuit.title
      || `Edited ${source.circuit.service_name || source.circuit.service} circuit`,
    ).trim();

    return this.generateCircuit({
      prompt,
      service: source.circuit.service,
      user,
      mainJson,
      routingMode: source.circuit.service === 'LT' ? 'wire' : routingMode,
    });
  }

  async regenerateEditedKiCad({ serial, user, mainJson, routingMode = 'combination' }) {
    return this.regenerateEditedCircuit({ serial, user, mainJson, routingMode });
  }

  async copySerial({ serial, userId }) {
    return this.db.transact((db) => {
      const circuit = db.circuits.find((item) => item.serial === serial);
      if (!circuit) return null;
      circuit.copy_serial_count += 1;
      touch(circuit);
      db.download_events.push({
        id: createId('copy'),
        serial,
        circuit_id: circuit.id,
        owner_user_id: circuit.owner_user_id,
        downloader_user_id: userId,
        source: 'copy_serial',
        service: circuit.service,
        created_at: nowIso(),
      });
      return toHistoryCard(circuit);
    });
  }

  async recordDownload({ serial, userId, source = 'shared_serial' }) {
    return this.db.transact((db) => {
      const circuit = db.circuits.find((item) => item.serial === serial);
      if (!circuit || circuit.status !== 'success' || circuit.export_status !== 'ready') return null;

      const uniqueId = `${circuit.id}:${userId}`;
      const existingUnique = db.unique_downloads.find((item) => item.id === uniqueId);
      const timestamp = nowIso();

      db.download_events.push({
        id: createId('download'),
        serial,
        circuit_id: circuit.id,
        owner_user_id: circuit.owner_user_id,
        downloader_user_id: userId,
        source,
        service: circuit.service,
        created_at: timestamp,
      });

      if (existingUnique) {
        existingUnique.last_downloaded_at = timestamp;
        existingUnique.download_count += 1;
      } else {
        db.unique_downloads.push({
          id: uniqueId,
          circuit_id: circuit.id,
          serial,
          owner_user_id: circuit.owner_user_id,
          downloader_user_id: userId,
          first_downloaded_at: timestamp,
          last_downloaded_at: timestamp,
          download_count: 1,
        });
        circuit.unique_user_downloads += 1;
      }

      circuit.total_downloads += 1;

      if (userId !== circuit.owner_user_id) {
        circuit.shared_reuse_count += 1;
        db.admin_counters.model_calls_avoided += 1;
      }

      touch(circuit);
      return circuit;
    });
  }

  async exportArtifactForSerial(serial) {
    const db = await this.db.read();
    const circuit = db.circuits.find((item) => item.serial === serial);
    if (!circuit || circuit.status !== 'success' || circuit.export_status !== 'ready') return null;
    const artifact = db.artifacts.find((item) => (
      item.serial === serial
      && item.artifact_type === 'export_project_file'
      && item.storage_visibility === 'user_downloadable'
    ));
    if (!artifact) return null;
    return { circuit, artifact };
  }

  async setReuseEligibility({ serial, user, reuseEligibility }) {
    return this.db.transact((db) => {
      const circuit = db.circuits.find((item) => item.serial === serial);
      if (!circuit || circuit.owner_user_id !== user.id || (user.plan !== 'premium' && user.role !== 'admin')) return null;

      circuit.reuse_eligibility = reuseEligibility;
      circuit.reuse_eligibility_reason = reuseEligibility === 'eligible'
        ? (user.role === 'admin' ? 'admin_allowed' : 'premium_allowed')
        : (user.role === 'admin' ? 'admin_opt_out' : 'premium_opt_out');
      touch(circuit);

      if (reuseEligibility === 'not_eligible') {
        db.reuse_candidates
          .filter((candidate) => candidate.source_circuit_id === circuit.id)
          .forEach((candidate) => {
            candidate.approved_status = 'removed_by_owner_opt_out';
          });
      }

      return toHistoryCard(circuit);
    });
  }

  async softDelete({ serial, user }) {
    return this.db.transact((db) => {
      const circuit = db.circuits.find((item) => item.serial === serial);
      if (!circuit || circuit.owner_user_id !== user.id) return null;

      circuit.status = 'deleted';
      touch(circuit);
      const registry = db.serial_registry.find((item) => item.serial === serial);
      if (registry) registry.status = 'deleted';
      return toHistoryCard(circuit);
    });
  }

  async softDeleteById({ id, user }) {
    return this.db.transact((db) => {
      const circuit = db.circuits.find((item) => item.id === id);
      if (!circuit || circuit.owner_user_id !== user.id) return null;

      circuit.status = 'deleted';
      touch(circuit);
      if (circuit.serial) {
        const registry = db.serial_registry.find((item) => item.serial === circuit.serial);
        if (registry) registry.status = 'deleted';
      }
      return toHistoryCard(circuit);
    });
  }
}
