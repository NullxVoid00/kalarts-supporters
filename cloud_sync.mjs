import { readFile, writeFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { seal, unseal } from './state.mjs';

const local = process.argv.includes('--local');
const key = process.env.KALARTS_STATE_KEY;
const encryptedPath = '.state/patreon.enc';
const directory = await mkdtemp(path.join(process.env.RUNNER_TEMP || tmpdir(), 'kalarts-'));
const privatePath = path.join(directory, 'session.json');
let syncStatus = 1;
let stateSaved = false;

function mask(state) {
  if (process.env.GITHUB_ACTIONS !== 'true') return;
  for (const name of ['client_secret', 'access_token', 'refresh_token']) {
    const value = state[name];
    if (value) console.log('::add-mask::' + value.replaceAll('%', '%25').replaceAll('\r', '%0D').replaceAll('\n', '%0A'));
  }
}
function git(...args) {
  const result = spawnSync('git', args, {encoding: 'utf8'});
  if (result.status !== 0) throw new Error('Could not persist encrypted session; see the encrypted-session recovery artifact.');
}

try {
  const original = unseal(await readFile(encryptedPath, 'utf8'), key);
  mask(JSON.parse(original));
  await writeFile(privatePath, original, {mode: 0o600});
  await mkdir('public', {recursive: true});
  const result = spawnSync(process.env.PYTHON || 'python3', ['cloud_sync.py', privatePath, 'public/supporters.json'], {encoding: 'utf8', timeout: 180000});
  syncStatus = result.status ?? 1;
  const updated = await readFile(privatePath, 'utf8');
  mask(JSON.parse(updated));
  // Preserve rotated refresh tokens before publishing, even when the member API failed.
  if (updated !== original) {
    await writeFile(encryptedPath, seal(updated, key));
    if (!local) {
      git('config', 'user.name', 'KalArts Supporter Sync');
      git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com');
      git('add', '--', encryptedPath);
      git('commit', '-m', 'Maintain encrypted Patreon session');
      let pushed = false;
      for (let attempt = 0; attempt < 3; attempt++) {
        const pushedResult = spawnSync('git', ['push', 'origin', 'HEAD:main'], {encoding: 'utf8', timeout: 60000});
        if (pushedResult.status === 0) { pushed = true; break; }
        if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 3000));
      }
      if (!pushed) throw new Error('Encrypted session push failed; retain the recovery artifact before retrying.');
    }
  }
  stateSaved = true;
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (syncStatus === 0) {
    await writeFile('public/index.html', '<!doctype html><meta charset="utf-8"><title>KalArts Supporter Feed</title><h1>KalArts Supporter Feed</h1><p>Public recognition names and tiers for KalArts VRChat worlds.</p><p><a href="supporters.json">Supporter feed</a> · <a href="https://www.patreon.com/c/KalArts">KalArts on Patreon</a></p>');
    await writeFile('public/.nojekyll', '');
  }
} catch (error) {
  console.error('Sync could not complete safely. The existing public feed has not been replaced.');
  if (!stateSaved) console.error('If credentials rotated, recover .state/patreon.enc from the encrypted-session artifact.');
  syncStatus = 1;
} finally {
  await rm(directory, {recursive: true, force: true});
}
process.exitCode = syncStatus;
