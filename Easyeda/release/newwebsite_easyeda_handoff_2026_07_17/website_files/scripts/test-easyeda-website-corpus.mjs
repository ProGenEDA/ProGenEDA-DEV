import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';

const corpusDir = resolve(
  process.argv[2]
    || process.env.PROGEN_EASYEDA_CORPUS_DIR
    || 'vendor/easyeda/corpus-300',
);
const apiBaseUrl = String(process.env.PROGEN_API_URL || 'http://127.0.0.1:3000').replace(/\/$/, '');
const batchSize = Math.min(50, Math.max(1, Number(process.env.PROGEN_EASYEDA_BATCH_SIZE || 50)));
const limit = Math.max(0, Number(process.env.PROGEN_EASYEDA_TEST_LIMIT || 0));
const outputDir = resolve(process.env.PROGEN_EASYEDA_TEST_OUTPUT || 'local-data/test-reports/easyeda-website-corpus');
const fileNames = (await readdir(corpusDir))
  .filter((name) => name.endsWith('.json') && name !== 'manifest.json')
  .sort()
  .slice(0, limit || undefined);

if (!fileNames.length) throw new Error(`No EasyEDA circuit JSONs found in ${corpusDir}.`);
await mkdir(outputDir, { recursive: true });

const report = {
  schemaVersion: 'progeneda-easyeda-website-corpus-report/v1',
  corpusDir,
  totalInputs: fileNames.length,
  batchSize,
  startedAt: new Date().toISOString(),
  completedAt: null,
  successfulBatches: 0,
  failedBatches: 0,
  reportedSuccessfulCircuits: 0,
  batches: [],
};

for (let offset = 0; offset < fileNames.length; offset += batchSize) {
  const names = fileNames.slice(offset, offset + batchSize);
  const batchNumber = Math.floor(offset / batchSize) + 1;
  const items = await Promise.all(names.map(async (name) => ({
    name,
    mainJson: JSON.parse(await readFile(join(corpusDir, name), 'utf8')),
  })));
  const startedAt = Date.now();
  const response = await fetch(`${apiBaseUrl}/api/generate/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-ProGenEDA-User-Id': 'user_local_tahabinzaeem0',
      'X-ProGenEDA-User-Email': 'tahabinzaeem0@progeneda.local',
      'X-ProGenEDA-Display-Name': 'EasyEDA Corpus Test',
      'X-ProGenEDA-Role': 'admin',
    },
    body: JSON.stringify({ targetService: 'EA', routingMode: 'combination', items }),
  });
  const durationMs = Date.now() - startedAt;
  if (!response.ok) {
    const detail = await response.text();
    report.failedBatches += 1;
    report.batches.push({ batchNumber, inputCount: names.length, status: 'failed', durationMs, detail });
    console.error(`[easyeda-corpus] batch ${batchNumber} failed (${response.status}) after ${durationMs}ms`);
    continue;
  }
  const buffer = Buffer.from(await response.arrayBuffer());
  if (buffer.length < 4 || buffer.readUInt32LE(0) !== 0x04034b50) {
    throw new Error(`Batch ${batchNumber} did not return a valid ZIP signature.`);
  }
  const successfulCircuits = Number(response.headers.get('x-progeneda-batch-succeeded') || 0);
  const zipName = `batch-${String(batchNumber).padStart(2, '0')}-${basename(corpusDir)}.zip`;
  await writeFile(join(outputDir, zipName), buffer);
  report.successfulBatches += 1;
  report.reportedSuccessfulCircuits += successfulCircuits;
  report.batches.push({ batchNumber, inputCount: names.length, successfulCircuits, status: 'success', durationMs, zipName, zipBytes: buffer.length });
  console.log(`[easyeda-corpus] batch ${batchNumber}: ${successfulCircuits}/${names.length} circuits, ${durationMs}ms`);
}

report.completedAt = new Date().toISOString();
const reportPath = join(outputDir, 'report.json');
await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
console.log(`[easyeda-corpus] complete: ${report.reportedSuccessfulCircuits}/${report.totalInputs}; report ${reportPath}`);
if (report.failedBatches || report.reportedSuccessfulCircuits !== report.totalInputs) process.exitCode = 1;
