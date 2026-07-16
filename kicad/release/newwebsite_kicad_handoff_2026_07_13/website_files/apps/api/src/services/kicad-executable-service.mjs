import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

function runProcess(command, args, options = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: { ...process.env, ...(options.env || {}) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code === 0) {
        resolveRun({ stdout, stderr });
        return;
      }
      const error = new Error(stderr || stdout || `KiCad executable exited ${code}.`);
      error.statusCode = 422;
      error.stdout = stdout;
      error.stderr = stderr;
      reject(error);
    });
  });
}

function parseLastJson(stdout) {
  const text = String(stdout || '').trim();
  const start = text.lastIndexOf('\n{');
  const jsonText = start >= 0 ? text.slice(start + 1) : text;
  return JSON.parse(jsonText);
}

function firstGeneratedProject(summary) {
  const generation = summary?.generation;
  const results = generation?.results || [];
  const first = results.find((item) => item?.output_artifacts?.user_project);
  if (!first) throw new Error('KiCad executable did not return a user project artifact.');
  return {
    generationRunDir: generation.run_dir,
    result: first,
    userProject: first.output_artifacts.user_project,
    internalBundle: first.output_artifacts.internal_bundle,
    serial: first.output_artifacts.serial,
  };
}

function firstGeneratedPcb(summary) {
  const result = (summary?.pcb_exports || []).find(
    (item) => item?.ready_for_output && item?.pcb_file,
  );
  if (!result) throw new Error('KiCad PCB-only command did not return an accepted native board.');
  return {
    result,
    pcbPath: result.pcb_file,
  };
}

export async function generateWithKiCadExecutable({
  mainJson,
  prompt = '',
  config,
  routingMode = 'combination',
  terminalSmoke = false,
}) {
  if (!mainJson || typeof mainJson !== 'object') {
    const error = new Error('KiCad generation requires canonical mainJson.');
    error.statusCode = 400;
    throw error;
  }

  const executablePath = config.kicadExecutablePath || process.env.PROGEN_KICAD_EXECUTABLE_PATH;
  if (!executablePath) {
    const error = new Error('PROGEN_KICAD_EXECUTABLE_PATH is not configured.');
    error.statusCode = 500;
    throw error;
  }

  const workRoot = resolve(config.kicadWorkDir || process.env.PROGEN_KICAD_WORK_DIR || join(tmpdir(), 'progen-kicad-website-runs'));
  const tempDir = await mkdtemp(join(tmpdir(), 'progen-kicad-input-'));
  const inputPath = join(tempDir, 'main.json');
  await writeFile(inputPath, JSON.stringify(mainJson, null, 2), 'utf8');

  const args = [
    'run',
    inputPath,
    '--output-root',
    workRoot,
    '--label',
    'website_kicad',
    '--routing-mode',
    routingMode,
  ];
  if (terminalSmoke) args.push('--terminal-smoke');

  const command = executablePath.endsWith('.py') ? (process.env.PYTHON || 'python3') : executablePath;
  const commandArgs = executablePath.endsWith('.py') ? [executablePath, ...args] : args;
  const { stdout, stderr } = await runProcess(command, commandArgs);
  const summary = parseLastJson(stdout);
  const project = firstGeneratedProject(summary);
  const exportPath = resolve(project.generationRunDir, project.userProject.path);
  const internalPath = resolve(project.generationRunDir, project.internalBundle.path);
  const exportBuffer = await readFile(exportPath);
  const internalBuffer = await readFile(internalPath);

  return {
    exportBuffer,
    fileName: project.userProject.file_name,
    componentSummary: summary.generation.output_artifacts?.[0]?.serial_info?.component_summary
      || project.result.component_summary
      || {},
    serialInfo: summary.generation.output_artifacts?.[0]?.serial_info || null,
    internalCircuit: {
      schemaVersion: 'progen-kicad-executable-adapter/v0.1',
      service: 'KC',
      prompt,
      executableSummary: summary,
      internalBundleBase64: internalBuffer.toString('base64'),
      exportFileName: project.userProject.file_name,
    },
    validationReport: {
      status: 'passed',
      checks: [
        'kicad_input_json_fixed',
        'kicad_generation_completed',
        'kicad_local_netlist_passed',
        'kicad_final_validation_passed',
      ],
      executableRunDir: summary.run_dir,
      stderr,
    },
    modelRouting: {
      provider: 'progen-kicad',
      model: 'deterministic-executable',
      adapter: 'progen-kicad-executable',
    },
    generationMetadata: {
      temporary: false,
      routingMode,
      generatedAt: new Date().toISOString(),
      executableRunDir: summary.run_dir,
    },
    providerUsage: {
      inputTokens: null,
      outputTokens: null,
      totalTokens: null,
      source: 'deterministic-executable',
    },
  };
}

export async function generatePcbOnlyWithKiCadExecutable({
  mainJson,
  prompt = '',
  config,
  routingMode = 'combination',
}) {
  if (!mainJson || typeof mainJson !== 'object') {
    const error = new Error('KiCad PCB generation requires canonical mainJson.');
    error.statusCode = 400;
    throw error;
  }

  const executablePath = config.kicadExecutablePath || process.env.PROGEN_KICAD_EXECUTABLE_PATH;
  if (!executablePath) {
    const error = new Error('PROGEN_KICAD_EXECUTABLE_PATH is not configured.');
    error.statusCode = 500;
    throw error;
  }

  const workRoot = resolve(config.kicadWorkDir || process.env.PROGEN_KICAD_WORK_DIR || join(tmpdir(), 'progen-kicad-website-runs'));
  const tempDir = await mkdtemp(join(tmpdir(), 'progen-kicad-pcb-input-'));
  const inputPath = join(tempDir, 'main.json');
  await writeFile(inputPath, JSON.stringify(mainJson, null, 2), 'utf8');
  const args = [
    'run-pcb',
    inputPath,
    '--output-root',
    workRoot,
    '--label',
    'website_kicad_pcb',
    '--routing-mode',
    routingMode,
  ];
  const command = executablePath.endsWith('.py') ? (process.env.PYTHON || 'python3') : executablePath;
  const commandArgs = executablePath.endsWith('.py') ? [executablePath, ...args] : args;
  const { stdout, stderr } = await runProcess(command, commandArgs);
  const summary = parseLastJson(stdout);
  const pcb = firstGeneratedPcb(summary);
  const pcbPath = resolve(summary.run_dir, pcb.pcbPath);
  const exportBuffer = await readFile(pcbPath);

  return {
    exportBuffer,
    fileName: pcb.result.artifact.file_name,
    internalCircuit: {
      schemaVersion: 'progen-kicad-pcb-only-adapter/v0.1',
      service: 'KC',
      prompt,
      executableSummary: summary,
      exportFileName: pcb.result.artifact.file_name,
    },
    validationReport: {
      status: 'passed',
      checks: [
        'kicad_input_json_fixed',
        'kicad_schematic_contract_passed',
        'kicad_pcb_hosted_validation_passed',
      ],
      executableRunDir: summary.run_dir,
      stderr,
    },
    modelRouting: {
      provider: 'progen-kicad',
      model: 'deterministic-executable',
      adapter: 'progen-kicad-pcb-only',
    },
    generationMetadata: {
      temporary: false,
      routingMode,
      pcbOnly: true,
      generatedAt: new Date().toISOString(),
      executableRunDir: summary.run_dir,
    },
  };
}
