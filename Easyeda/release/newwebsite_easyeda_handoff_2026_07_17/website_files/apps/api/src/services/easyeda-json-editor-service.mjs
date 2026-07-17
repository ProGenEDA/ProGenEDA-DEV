import { createHash } from 'node:crypto';
import {
  codeForComponent,
  componentForCode,
  componentMetadataForCode,
  loadComponentRegistry,
} from '../../../../packages/component-registry/index.mjs';

const MAX_COMPONENTS = 80;
const MAX_TEXT = 160;
const REFERENCE_PATTERN = /^[A-Za-z#][A-Za-z0-9_:+.-]{0,95}$/;
const VALUE_PATTERN = /^[\p{L}\p{N}\s._:+\-*/()=,%Ωµ#@]+$/u;

function isRecord(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function editorError(message, statusCode = 400, issues = []) {
  const error = new Error(message);
  error.statusCode = statusCode;
  error.issues = issues;
  return error;
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (!isRecord(value)) return JSON.stringify(value);
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
}

function digest(value) {
  return createHash('sha256').update(stableJson(value)).digest('hex');
}

function canonicalKind(value) {
  const registry = loadComponentRegistry('EA', 'A');
  const code = codeForComponent(value, registry);
  return code ? componentForCode(code, registry) : null;
}

function declaredNets(value) {
  const result = new Map();
  if (Array.isArray(value)) {
    for (const item of value) {
      if (isRecord(item) && item.name) result.set(String(item.name), [...(item.members || [])].map(String).sort());
    }
  } else if (isRecord(value)) {
    for (const [name, members] of Object.entries(value)) {
      result.set(name, (Array.isArray(members) ? members : []).map(String).sort());
    }
  }
  return Object.fromEntries([...result.entries()].sort(([left], [right]) => left.localeCompare(right)));
}

function derivedNets(components) {
  const result = new Map();
  for (const component of components) {
    const reference = String(component.ref || component.id || '');
    for (const [pin, net] of Object.entries(isRecord(component.pins) ? component.pins : {})) {
      const name = String(net);
      if (!result.has(name)) result.set(name, []);
      result.get(name).push(`${reference}.${pin}`);
    }
  }
  return Object.fromEntries(
    [...result.entries()]
      .map(([name, members]) => [name, members.sort()])
      .sort(([left], [right]) => left.localeCompare(right)),
  );
}

function topologyNets(components) {
  const referenceToId = new Map(
    components.map((component) => [
      String(component.ref || component.id || ''),
      String(component.id || component.ref || ''),
    ]),
  );
  return Object.fromEntries(
    Object.entries(derivedNets(components)).map(([name, members]) => [
      name,
      members.map((endpoint) => {
        const separator = endpoint.lastIndexOf('.');
        const reference = endpoint.slice(0, separator);
        return `${referenceToId.get(reference) || reference}${endpoint.slice(separator)}`;
      }).sort(),
    ]),
  );
}

function topology(mainJson) {
  const components = Array.isArray(mainJson?.components) ? mainJson.components : [];
  return {
    components: components.map((component) => ({
      id: component.id,
      kind: canonicalKind(component.kind || component.type),
      pins: Object.keys(isRecord(component.pins) ? component.pins : {}).sort(),
    })),
    nets: topologyNets(components),
  };
}

function evidence(mainJson, sourceMainJson = mainJson, mode = 'guided') {
  const sourceTopologyDigest = digest(topology(sourceMainJson));
  const candidateTopologyDigest = digest(topology(mainJson));
  return {
    sourceDigest: digest(sourceMainJson),
    sourceTopologyDigest,
    candidateTopologyDigest,
    topologyPreserved: sourceTopologyDigest === candidateTopologyDigest,
    mode,
    sources: [
      { id: 'easyeda-circuit-ir', label: 'EasyEDA CircuitIR contract', source: 'progen-easyeda-circuit-ir/v1' },
      { id: 'easyeda-registry', label: 'EasyEDA donor catalogue', source: 'packages/component-registry/registries/EA-A.json' },
      { id: 'easyeda-runtime', label: 'Deterministic native validator', source: 'vendor/easyeda/progen-easyeda' },
    ],
    locks: mode === 'guided'
      ? ['Component family', 'Pin map', 'Net membership', 'Routing mode', 'Native source payloads']
      : ['Deterministic structural validation', 'EasyEDA executable validation'],
  };
}

export function validateEasyedaMainJson(mainJson) {
  const issues = [];
  const warnings = [];
  const push = (path, message, level = 'error') => (level === 'error' ? issues : warnings).push({ path, message, level });
  if (!isRecord(mainJson)) return { valid: false, issues: [{ path: '$', message: 'Circuit JSON must be an object.', level: 'error' }], warnings };
  if (mainJson.schema_version !== 'progen-easyeda-circuit-ir/v1') push('schema_version', 'Expected progen-easyeda-circuit-ir/v1.');
  if (!isRecord(mainJson.project) || !String(mainJson.project.name || '').trim() || !String(mainJson.project.title || '').trim()) {
    push('project', 'Project name and title are required.');
  }
  if (mainJson.project?.target && mainJson.project.target !== 'easyeda_pro') push('project.target', 'EasyEDA target must be easyeda_pro.');
  const mode = String(mainJson.routing?.mode || 'combination').toLowerCase();
  if (!['wire', 'terminal', 'combination'].includes(mode)) push('routing.mode', 'Routing mode must be wire, terminal, or combination.');
  const components = Array.isArray(mainJson.components) ? mainJson.components : [];
  if (!components.length || components.length > MAX_COMPONENTS) push('components', `EasyEDA supports 1-${MAX_COMPONENTS} input components.`);
  const refs = new Set();
  const ids = new Set();
  components.forEach((component, index) => {
    const path = `components[${index}]`;
    if (!isRecord(component)) {
      push(path, 'Each component must be an object.');
      return;
    }
    const id = String(component.id || '').trim();
    const ref = String(component.ref || '').trim();
    if (!id || ids.has(id)) push(`${path}.id`, 'Component id is required and must be unique.');
    if (!REFERENCE_PATTERN.test(ref) || refs.has(ref)) push(`${path}.ref`, 'Reference is invalid or duplicated.');
    ids.add(id);
    refs.add(ref);
    const kind = canonicalKind(component.kind || component.type);
    if (!kind) push(`${path}.kind`, `${component.kind || component.type || 'Component'} is not in the EasyEDA donor catalogue.`);
    if (!isRecord(component.pins) || !Object.keys(component.pins).length) {
      push(`${path}.pins`, 'A non-empty pin-to-net map is required. Missing donor pins may only be repaired before the JSON is locked.');
    }
    if (component.value !== undefined && (!String(component.value).trim() || String(component.value).length > MAX_TEXT || !VALUE_PATTERN.test(String(component.value)))) {
      push(`${path}.value`, 'Value must use safe one-line engineering notation.');
    }
  });
  const derived = derivedNets(components);
  const declared = declaredNets(mainJson.nets);
  if (!Object.keys(declared).length) push('nets', 'At least one explicit net is required.');
  if (stableJson(derived) !== stableJson(declared)) push('nets', 'Top-level nets must exactly match component pin bindings.');
  if (mainJson.expected_netlist && stableJson(derived) !== stableJson(declaredNets(mainJson.expected_netlist))) {
    push('expected_netlist', 'Expected netlist must exactly match component pin bindings.');
  }
  return { valid: issues.length === 0, issues, warnings };
}

export function listEasyedaEditableFields(mainJson) {
  if (!isRecord(mainJson) || !Array.isArray(mainJson.components)) return [];
  const fields = [];
  for (const field of ['name', 'title']) {
    if (typeof mainJson.project?.[field] === 'string') {
      fields.push({
        id: `project:${field}`,
        group: 'Project',
        label: field === 'name' ? 'Project name' : 'Project title',
        value: mainJson.project[field],
        maxLength: MAX_TEXT,
        kind: 'project-title',
      });
    }
  }
  mainJson.components.forEach((component, index) => {
    if (!isRecord(component)) return;
    const canonical = canonicalKind(component.kind || component.type);
    const registry = loadComponentRegistry('EA', 'A');
    const code = codeForComponent(canonical, registry);
    const metadata = code ? componentMetadataForCode(code, registry) : null;
    const reference = String(component.ref || component.id || `Component ${index + 1}`);
    fields.push({
      id: `component:${index}:ref`, group: canonical || 'Component', componentIndex: index,
      componentRef: reference, label: 'Reference', value: reference, maxLength: 96, kind: 'reference',
      constraint: 'Reference changes are propagated through netlist metadata.',
    });
    if (metadata?.valueRule !== 'fixed_terminal') {
      fields.push({
        id: `component:${index}:value`, group: canonical || 'Component', componentIndex: index,
        componentRef: reference, label: 'Value', value: String(component.value || metadata?.defaultValue || ''),
        maxLength: MAX_TEXT, kind: 'value', constraint: `Catalogue rule: ${metadata?.valueRule || 'display_text'}.`,
      });
    }
  });
  return fields;
}

function rewriteReferences(value, referenceMap) {
  if (typeof value === 'string') {
    for (const [from, to] of referenceMap) {
      if (value === from) return to;
      if (value.startsWith(`${from}.`)) return `${to}${value.slice(from.length)}`;
    }
    return value;
  }
  if (Array.isArray(value)) return value.map((item) => rewriteReferences(item, referenceMap));
  if (!isRecord(value)) return value;
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, rewriteReferences(item, referenceMap)]));
}

export function applyEasyedaNormalChanges(mainJson, changes) {
  if (!Array.isArray(changes) || !changes.length) throw editorError('Provide at least one editable field change.');
  const next = cloneJson(mainJson);
  const editable = new Map(listEasyedaEditableFields(next).map((field) => [field.id, field]));
  const changed = new Set();
  const referenceMap = new Map();
  for (const change of changes) {
    const id = String(change?.id || '');
    const field = editable.get(id);
    const value = String(change?.value || '').trim();
    if (!field || changed.has(id)) throw editorError('One or more submitted fields are not editable.');
    if (!value || value.length > field.maxLength) throw editorError('Edited text is empty or too long.');
    changed.add(id);
    if (field.kind === 'project-title') {
      next.project[id.split(':')[1]] = value;
    } else if (field.kind === 'reference') {
      if (!REFERENCE_PATTERN.test(value)) throw editorError('Reference contains unsupported characters.');
      const component = next.components[field.componentIndex];
      referenceMap.set(String(component.ref), value);
      component.ref = value;
    } else if (field.kind === 'value') {
      if (!VALUE_PATTERN.test(value)) throw editorError('Value contains unsupported characters.');
      next.components[field.componentIndex].value = value;
    }
  }
  if (referenceMap.size) {
    next.nets = rewriteReferences(next.nets, referenceMap);
    next.expected_netlist = rewriteReferences(next.expected_netlist, referenceMap);
  }
  const validation = validateEasyedaMainJson(next);
  if (!validation.valid) throw editorError('The proposed edits do not pass EasyEDA JSON validation.', 422, validation.issues);
  const proof = evidence(next, mainJson, 'guided');
  if (!proof.topologyPreserved) throw editorError('Guided editing may not alter circuit topology.', 422);
  return {
    mainJson: next,
    validation,
    evidence: proof,
    audit: { changedFieldIds: [...changed], changedFieldCount: changed.size, topologyPreserved: true },
  };
}

export function buildEasyedaEditorDocument(mainJson, { includeRawJson = false, sourceMainJson = mainJson, mode = 'guided', audit = null } = {}) {
  return {
    validation: validateEasyedaMainJson(mainJson),
    fields: listEasyedaEditableFields(mainJson),
    componentCount: Array.isArray(mainJson.components) ? mainJson.components.length : 0,
    evidence: evidence(mainJson, sourceMainJson, mode),
    audit,
    rawMainJson: includeRawJson ? mainJson : undefined,
    editorLabel: 'EasyEDA JSON Lab',
    editorDescription: 'Guided edits preserve donor component families, pin maps, net membership, routing mode, and native payloads.',
  };
}

export function assertEasyedaEditorSource(circuit, user) {
  if (!circuit || circuit.status !== 'success') throw editorError('A successful circuit is required for editing.', 404);
  if (circuit.service !== 'EA') throw editorError('This JSON Lab adapter only accepts EasyEDA circuits.', 409);
  if (circuit.owner_user_id !== user.id && user.role !== 'admin') throw editorError('Only the circuit owner can open this JSON Lab.', 403);
}
