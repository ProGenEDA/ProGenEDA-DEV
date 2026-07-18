import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { generateWithEasyedaExecutable } from '../apps/api/src/services/easyeda-executable-service.mjs';
import {
  applyEasyedaNormalChanges,
  validateEasyedaMainJson,
} from '../apps/api/src/services/easyeda-json-editor-service.mjs';
import { planEasyedaMainJson } from '../apps/api/src/services/easyeda-main-json-planner-service.mjs';

const config = {
  aiProvider: 'fixture',
  easyedaExecutablePath: resolve('vendor/easyeda/progen-easyeda'),
  easyedaExampleLibraryDir: resolve('vendor/easyeda/examples-300'),
  easyedaWorkDir: await mkdtemp(join(tmpdir(), 'progen-easyeda-website-test-')),
};
const planned = await planEasyedaMainJson({ prompt: 'verified fixture', config });
const validation = validateEasyedaMainJson(planned.mainJson);
if (!validation.valid) throw new Error(JSON.stringify(validation.issues));

const originalReference = planned.mainJson.components[0].ref;
const edited = applyEasyedaNormalChanges(planned.mainJson, [
  { id: 'component:0:ref', value: `${originalReference}_EDIT` },
]);
if (!edited.evidence.topologyPreserved) throw new Error('Guided edit changed topology.');

const stages = [];
const generated = await generateWithEasyedaExecutable({
  mainJson: planned.mainJson,
  prompt: 'EasyEDA packaged integration test',
  config,
  onEvent: (event) => stages.push(event.stage),
});
const expectedStages = [
  'fix_and_validate_input',
  'normalize_values',
  'resolve_donor_catalogue',
  'place_components',
  'route_schematic',
  'write_native_eprj',
  'validate_native_eprj',
  'package_artifacts',
];
if (JSON.stringify(stages) !== JSON.stringify(expectedStages)) {
  throw new Error(`Unexpected EasyEDA stages: ${stages.join(', ')}`);
}
if (generated.validationReport.status !== 'passed' || !generated.fileName.endsWith('.eprj')) {
  throw new Error('Packaged EasyEDA generation did not pass.');
}
console.log(JSON.stringify({
  passed: true,
  fixture: planned.mainJson.project.name,
  stages,
  fileName: generated.fileName,
  topologyPreserved: edited.evidence.topologyPreserved,
}));
