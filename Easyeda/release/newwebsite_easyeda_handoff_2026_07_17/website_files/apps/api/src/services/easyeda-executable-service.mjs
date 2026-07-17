import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { deriveComponentSummaryFromMainJson } from './component-summary.mjs';

const PIPELINE_SCHEMA = 'progen-easyeda-pipeline/v1';

function commandFor(executablePath) {
  return executablePath.endsWith('.py') ? (process.env.PYTHON || 'python3') : executablePath;
}

function argsFor(executablePath, args) {
  return executablePath.endsWith('.py') ? [executablePath, ...args] : args;
}

function runProcess(command, args, { onEvent = null } = {}) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(command, args, {
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let remainder = '';
    let summary = null;

    const consume = (line) => {
      const text = line.trim();
      if (!text) return;
      try {
        const event = JSON.parse(text);
        if (event?.event === 'complete' && event.summary) summary = event.summary;
        else if (event?.event === 'stage') onEvent?.(event);
      } catch {
        // Preserve non-JSON output for diagnostics. Only the complete event is
        // accepted as the executable result.
      }
    };

    child.stdout.on('data', (chunk) => {
      const text = chunk.toString();
      stdout += text;
      remainder += text;
      const lines = remainder.split(/\r?\n/);
      remainder = lines.pop() || '';
      lines.forEach(consume);
    });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', (code) => {
      consume(remainder);
      if (code !== 0) {
        const error = new Error(stderr.trim() || `EasyEDA executable exited ${code}.`);
        error.statusCode = 422;
        error.stdout = stdout;
        error.stderr = stderr;
        reject(error);
        return;
      }
      if (!summary || summary.schema !== PIPELINE_SCHEMA || summary.passed !== true) {
        const error = new Error('EasyEDA executable did not return a validated pipeline summary.');
        error.statusCode = 422;
        reject(error);
        return;
      }
      resolveRun({ summary, stderr });
    });
  });
}

export async function generateWithEasyedaExecutable({
  mainJson,
  prompt = '',
  config,
  routingMode = 'combination',
  onEvent = null,
}) {
  if (!mainJson || typeof mainJson !== 'object' || Array.isArray(mainJson)) {
    const error = new Error('EasyEDA generation requires one canonical mainJson object.');
    error.statusCode = 400;
    throw error;
  }

  const executablePath = config.easyedaExecutablePath || process.env.PROGEN_EASYEDA_EXECUTABLE_PATH;
  if (!executablePath) {
    const error = new Error('PROGEN_EASYEDA_EXECUTABLE_PATH is not configured.');
    error.statusCode = 500;
    throw error;
  }

  const workRoot = resolve(
    config.easyedaWorkDir
      || process.env.PROGEN_EASYEDA_WORK_DIR
      || join(tmpdir(), 'progen-easyeda-website-runs'),
  );
  const tempDir = await mkdtemp(join(tmpdir(), 'progen-easyeda-input-'));
  const inputPath = join(tempDir, 'main.json');
  await writeFile(inputPath, JSON.stringify(mainJson, null, 2), 'utf8');

  try {
    const args = [
      'run',
      inputPath,
      '--output-root',
      workRoot,
      '--routing-mode',
      routingMode,
      '--events',
      'ndjson',
    ];
    const { summary, stderr } = await runProcess(
      commandFor(executablePath),
      argsFor(executablePath, args),
      { onEvent },
    );
    const [projectBuffer, internalBuffer, validation, pcb] = await Promise.all([
      readFile(resolve(summary.project_path)),
      readFile(resolve(summary.internal_zip)),
      readFile(resolve(summary.validation_report), 'utf8').then(JSON.parse),
      readFile(resolve(summary.pcb_report), 'utf8').then(JSON.parse),
    ]);
    if (validation.passed !== true || validation.errors?.length) {
      const error = new Error('EasyEDA native validation did not pass.');
      error.statusCode = 422;
      error.issues = validation.errors || [];
      throw error;
    }

    return {
      exportBuffer: projectBuffer,
      fileName: basename(summary.project_path),
      componentSummary: deriveComponentSummaryFromMainJson(mainJson),
      sourceMainJson: mainJson,
      internalCircuit: {
        schemaVersion: 'progen-easyeda-website-adapter/v1',
        service: 'EA',
        prompt,
        mainJson,
        executableSummary: summary,
        internalBundleBase64: internalBuffer.toString('base64'),
        exportFileName: basename(summary.project_path),
      },
      validationReport: {
        status: 'passed',
        checks: [
          'easyeda_input_fixed_and_validated',
          'easyeda_donor_payload_hashes_verified',
          'easyeda_complete_source_pin_coverage',
          'easyeda_expected_netlist_matched',
          'easyeda_compact_geometry_validated',
          pcb.ready ? 'easyeda_bounded_pcb_validated' : 'easyeda_pcb_withheld_with_reason',
        ],
        nativeValidation: validation,
        pcbReport: pcb,
        executableRunDir: summary.run_directory,
        stderr,
      },
      modelRouting: {
        provider: 'progen-easyeda',
        model: 'deterministic-donor-native-executable',
        adapter: 'progen-easyeda-executable',
      },
      generationMetadata: {
        temporary: false,
        routingMode,
        pcbReady: Boolean(summary.pcb_ready),
        pcbReason: summary.pcb_reason,
        generatedAt: new Date().toISOString(),
        executableRunDir: summary.run_directory,
      },
      providerUsage: {
        inputTokens: null,
        outputTokens: null,
        totalTokens: null,
        source: 'deterministic-executable',
      },
    };
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}
