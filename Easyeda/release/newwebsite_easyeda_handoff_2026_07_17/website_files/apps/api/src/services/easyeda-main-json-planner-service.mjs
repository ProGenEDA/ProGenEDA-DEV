import { readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { validateEasyedaMainJson } from './easyeda-json-editor-service.mjs';

const registry = JSON.parse(
  readFileSync(new URL('../../../../packages/component-registry/registries/EA-A.json', import.meta.url), 'utf8'),
);
const MAX_RESPONSE_CHARS = 1_500_000;
const SUPPORTED_KINDS = Object.values(registry.components).sort();

function plannerError(message, statusCode = 502) {
  const error = new Error(message);
  error.statusCode = statusCode;
  return error;
}

function extractObject(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value;
  const text = String(value || '').trim();
  if (!text) throw plannerError('EasyEDA planner returned an empty response.');
  if (text.length > MAX_RESPONSE_CHARS) throw plannerError('EasyEDA planner response exceeded the safe JSON limit.');
  try {
    return JSON.parse(text);
  } catch {
    const match = text.match(/\{[\s\S]*\}/);
    if (!match) throw plannerError('EasyEDA planner returned no JSON object.');
    return JSON.parse(match[0]);
  }
}

function checked(mainJson) {
  const validation = validateEasyedaMainJson(mainJson);
  if (!validation.valid) {
    const detail = validation.issues.slice(0, 5).map((issue) => `${issue.path}: ${issue.message}`).join(' ');
    throw plannerError(`EasyEDA planner output failed deterministic validation. ${detail}`);
  }
  return { mainJson, validation };
}

function instructions() {
  return [
    'You are the ProGenEDA EasyEDA Pro circuit planning boundary.',
    'Return a wrapper with exactly one mainJson string containing one JSON object and no markdown.',
    'Use schema_version progen-easyeda-circuit-ir/v1.',
    'Include project {name,title,target:"easyeda_pro"}, routing {mode:"combination"}, purpose, components, nets, and expected_netlist.',
    'Each component needs id, ref, kind, value, role, block, and a pins object mapping known source pin numbers to named nets.',
    'Every top-level net and expected_netlist member must exactly match the supplied REF.PIN bindings.',
    'Pins not supplied are completed by the deterministic donor-aware input fixer as explicit GUESS_* terminal nets; never invent a pin number.',
    'Use no more than 80 input components and no more than 32 physical components when a PCB is expected.',
    `Supported canonical kinds are: ${SUPPORTED_KINDS.join(', ')}.`,
    'Prefer exact named power nets GND, +5V, +3V3, or VCC.',
    'Do not return commands, URLs, files, prose, or claims of electrical correctness.',
    'The donor resolver, input fixer, native generator, netlist comparator, geometry validator, and bounded PCB validator are final authority.',
  ].join(' ');
}

function responseText(payload) {
  if (typeof payload?.output_text === 'string') return payload.output_text;
  const parts = [];
  for (const output of Array.isArray(payload?.output) ? payload.output : []) {
    for (const content of Array.isArray(output?.content) ? output.content : []) {
      if (typeof content?.text === 'string') parts.push(content.text);
    }
  }
  return parts.join('\n');
}

async function fixture(config) {
  const root = resolve(config.easyedaExampleLibraryDir);
  const candidates = [
    'q26_regulated_5v_supply_education_v01',
    'q01_esp32_environment_logger_education_v01',
  ];
  for (const name of candidates) {
    for (const sourcePath of [join(root, name, 'circuit.json'), join(root, `${name}.json`)]) {
      try {
        return checked(JSON.parse(await readFile(sourcePath, 'utf8')));
      } catch (error) {
        if (error?.code !== 'ENOENT') throw error;
      }
    }
  }
  throw plannerError('EasyEDA fixture planner could not load its verified example JSON.', 503);
}

async function openAi({ prompt, config, model = null }) {
  if (!config.openAiApiKey) throw plannerError('PROGEN_OPENAI_API_KEY is not configured.', 503);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.openAiTimeoutMs);
  try {
    const selectedModel = model || config.openAiModel;
    const response = await fetch(`${config.openAiBaseUrl}/responses`, {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${config.openAiApiKey}` },
      body: JSON.stringify({
        model: selectedModel,
        store: false,
        max_output_tokens: config.openAiMaxOutputTokens,
        input: [
          { role: 'system', content: [{ type: 'input_text', text: instructions() }] },
          { role: 'user', content: [{ type: 'input_text', text: `UNTRUSTED_CIRCUIT_REQUEST_BEGIN\n${prompt}\nUNTRUSTED_CIRCUIT_REQUEST_END` }] },
        ],
        text: {
          format: {
            type: 'json_schema',
            name: 'progeneda_easyeda_main_json',
            strict: true,
            schema: {
              type: 'object',
              additionalProperties: false,
              required: ['mainJson'],
              properties: { mainJson: { type: 'string' } },
            },
          },
        },
      }),
    });
    if (!response.ok) {
      const detail = (await response.text()).slice(0, 1_000);
      throw plannerError(detail || `OpenAI planning failed with HTTP ${response.status}.`, response.status >= 500 ? 502 : response.status);
    }
    const payload = await response.json();
    const wrapper = extractObject(responseText(payload));
    const result = checked(extractObject(wrapper.mainJson));
    const usage = payload.usage || {};
    return {
      ...result,
      providerUsage: {
        inputTokens: usage.input_tokens ?? null,
        outputTokens: usage.output_tokens ?? null,
        totalTokens: usage.total_tokens ?? null,
        source: 'openai-responses-provider-response',
      },
      provider: 'openai',
      model: payload.model || selectedModel,
      adapter: 'openai-easyeda-structured-planner',
    };
  } catch (error) {
    if (error?.name === 'AbortError') throw plannerError('EasyEDA planning timed out.', 504);
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function planEasyedaMainJson({ prompt, config, model = null }) {
  if (config.aiProvider === 'fixture') {
    return {
      ...(await fixture(config)),
      providerUsage: { inputTokens: 0, outputTokens: 0, totalTokens: 0, source: 'verified-fixture-no-model-call' },
      provider: 'fixture',
      model: 'verified-easyeda-example',
      adapter: 'fixture-easyeda-main-json-planner',
    };
  }
  if (config.aiProvider === 'openai') return openAi({ prompt, config, model });
  throw plannerError('EasyEDA AI planning is disabled. Direct JSON and the 300 verified examples remain available.', 503);
}
