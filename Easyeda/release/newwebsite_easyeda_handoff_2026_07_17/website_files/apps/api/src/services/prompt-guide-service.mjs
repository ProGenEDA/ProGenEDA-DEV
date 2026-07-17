import {
  componentMetadataForName,
  listVisibleComponents,
  loadComponentRegistry,
} from '../../../../packages/component-registry/index.mjs';

const PROMPT_FIELDS = [
  {
    id: 'purpose',
    label: 'Purpose',
    description: 'What the circuit must do.',
    pattern: /\b(design|build|create|convert|drive|filter|amplif|regulat|measure|detect|control)\b/i,
  },
  {
    id: 'input',
    label: 'Input',
    description: 'Voltage, current, signal source, or supply.',
    pattern: /\b\d+(?:\.\d+)?\s*(?:v|mv|kv|a|ma|hz|khz|mhz)\b/i,
  },
  {
    id: 'output',
    label: 'Output or load',
    description: 'Required output, load, gain, frequency, or behavior.',
    pattern: /\b(output|load|gain|drive|supply|voltage|current|frequency|led|motor)\b/i,
  },
  {
    id: 'constraints',
    label: 'Constraints',
    description: 'Topology, protection, size, parts, safety, or simulation constraints.',
    pattern: /\b(isolat|protect|fuse|topology|buck|boost|flyback|filter|efficient|low[- ]?noise|simulate|layout|footprint)\b/i,
  },
  {
    id: 'target',
    label: 'Target',
    description: 'Target EDA tool if it matters for the result.',
    pattern: /\b(kicad|proteus|ltspice|pspice|altium|\.kicad|\.pdsprj|\.asc)\b/i,
  },
];

const TARGET_SERVICE = {
  PR: 'Proteus',
  KC: 'KiCad',
  LT: 'LTspice',
  EA: 'EasyEDA Pro',
};

function normalizeTarget(targetService) {
  const target = String(targetService || 'KC').toUpperCase();
  return ['PR', 'KC', 'LT', 'EA'].includes(target) ? target : 'KC';
}

function componentMentions(prompt, service) {
  const lower = String(prompt || '').toLowerCase();
  const registry = loadComponentRegistry(service, 'A');
  return listVisibleComponents(registry)
    .filter((component) => component.displayName && lower.includes(component.displayName.toLowerCase()))
    .slice(0, 12)
    .map((component) => ({
      name: component.displayName,
      code: component.code,
      limitPerCircuit: component.maxPerCircuit || null,
    }));
}

export function analyzeCircuitPrompt({ prompt, targetService = 'KC' }) {
  const service = normalizeTarget(targetService);
  const text = String(prompt || '').trim();
  const present = PROMPT_FIELDS.filter((field) => field.pattern.test(text));
  const missing = PROMPT_FIELDS.filter((field) => !field.pattern.test(text));
  const recognizedComponents = componentMentions(text, service);

  const recommendations = [];
  if (missing.some((field) => field.id === 'input')) recommendations.push('Specify the input source and its voltage, current, or signal range.');
  if (missing.some((field) => field.id === 'output')) recommendations.push('State the output, load, gain, or expected behavior.');
  if (missing.some((field) => field.id === 'constraints')) recommendations.push('Add topology, protection, component, simulation, or layout constraints.');
  if (!recognizedComponents.length) recommendations.push('Name required components when a particular part family matters.');
  if (service === 'PR') recommendations.push('The visible Proteus registry is a compatibility target; confirm exporter support before relying on a specific component or IC-count limit.');
  if (service === 'LT') recommendations.push('LTspice currently accepts the donor-native ground, resistor, capacitor, inductor, voltage/current source, and signal-source families with physical-wire routing only.');
  if (service === 'EA') recommendations.push('EasyEDA Pro accepts 59 donor-native logical families, up to 80 schematic components and 32 physical PCB components, with combination routing by default.');

  return {
    targetService: service,
    targetName: TARGET_SERVICE[service],
    score: Math.min(100, 30 + present.length * 14 + Math.min(12, recognizedComponents.length * 2)),
    readyForModel: missing.length <= 1 && text.length >= 24,
    present: present.map(({ id, label, description }) => ({ id, label, description })),
    missing: missing.map(({ id, label, description }) => ({ id, label, description })),
    recognizedComponents,
    recommendations,
    template: `Design a [purpose] for ${TARGET_SERVICE[service]}. Input: [source and range]. Output/load: [requirements]. Topology/components: [required parts]. Constraints: [protection, simulation, layout, or limits].`,
    deterministic: true,
  };
}

export function proteusComponentGuide() {
  const registry = loadComponentRegistry('PR', 'A');
  return listVisibleComponents(registry).map((component) => ({
    name: component.displayName,
    code: component.code,
    isIntegratedCircuit: Boolean(component.isIntegratedCircuit),
    maxPerCircuit: component.maxPerCircuit || null,
    aliases: component.aliases || [],
  }));
}

export function validateKnownProteusComponentName(name) {
  const metadata = componentMetadataForName(name, loadComponentRegistry('PR', 'A'));
  return metadata ? { supported: true, component: metadata.displayName, maxPerCircuit: metadata.maxPerCircuit || null } : { supported: false };
}
