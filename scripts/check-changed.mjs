import {execFileSync} from 'node:child_process';
import {appendFileSync, readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {browserSuites} from './check-browser-suite.mjs';
import {hasGitSourceTransformAttributes, hasHiddenIndexEntries, startCheckRun} from './check-evidence.mjs';

// Unknown inputs deliberately select the comprehensive gate.
export function selectChecks(files, full = false) {
  const selected = new Set(full ? ['full'] : []);
  for (const file of files) {
    if (['scripts/check-changed.mjs','scripts/check-evidence.mjs','scripts/check-browser-suite.mjs','scripts/python-runtime.mjs','scripts/e2e-preview.mjs','scripts/build-identity.mjs','scripts/check-ci-gate.mjs'].includes(file)) { selected.add('full'); continue; }
    if (['scripts/dev-doctor.mjs','tests/check-selection.test.mjs','tests/check-evidence.test.mjs','tests/dev-doctor.test.mjs','tests/python-runtime.test.mjs','tests/e2e-preview.test.mjs','tests/build-identity.test.mjs','tests/ci-gate.test.mjs'].includes(file)) { selected.add('selector'); continue; }
    if (['.github/workflows/mobile-preview.yml','tests/fixtures/mobile-native-chinese.png'].includes(file)) { selected.add('mobile'); continue; }
    if (file === 'tests/fixtures/mobile-native-chinese.md') { selected.add('docs'); continue; }
    if (['scripts/language-account-e2e.mjs','scripts/browser-e2e.mjs'].includes(file)) { selected.add('desktop'); continue; }
    if (file === 'scripts/python-tests.mjs') { selected.add('python'); continue; }
    if (['backend/api.py','backend/state_version.py','app/companion.tsx','app/language-setup.tsx','app/state-sync.ts','scripts/ui-state-e2e.mjs','scripts/ui-state-react-e2e.mjs','scripts/ui-state-browser-server.py','tests/state-sync.test.mjs'].includes(file)) { selected.add('python'); selected.add('desktop'); continue; }
    if (['scripts/update-companion.ps1','scripts/companion-runtime.ps1'].includes(file)) { selected.add('python'); selected.add('windows'); continue; }
    if (/^scripts\/(start-companion|companion-process-identity-e2e).*\.ps1$/.test(file)) { selected.add('windows'); continue; }
    if(file==='lib/interface-language.tsx'){selected.add('desktop');selected.add('mobile');continue;}
    if(file==='public/mobile-capture/games-data.json'){selected.add('mobile');selected.add('python');selected.add('docs');continue;}
    if(['scripts/generate-language-docs.mjs','scripts/check-docs.mjs'].includes(file)){selected.add('docs');continue;}
    if (/^(docs\/.*|[^/]+)\.(md|html)$/.test(file) || /^\.github\/(ISSUE_TEMPLATE\/|dependabot\.yml)/.test(file)) selected.add('docs');
    else if (/^backend\/|^tests\/.*\.py$/.test(file)) selected.add('python');
    else if (/^(app|components|hooks|lib|styles)\//.test(file)) selected.add('desktop');
    else if (/^(mobile|public\/mobile-capture|services)\//.test(file) || /^scripts\/(ocr-|mobile-|companion-e2e|build-mobile|build-browser|prepare-mobile|serve-mobile|webrtc)/.test(file) || /^tests\/mobile-/.test(file)) selected.add('mobile');
    else selected.add('full');
  }
  return selected.has('full') ? ['full'] : [...selected].sort();
}
export function changedFiles(base, {cwd = process.cwd()} = {}) {
  const files = new Set();
  const readGit = (...args) => execFileSync('git', args, {cwd, encoding: 'utf8', stdio: ['ignore','pipe','pipe']});
  try { if (hasHiddenIndexEntries(cwd)) files.add('__hidden_index_entries__'); }
  catch { files.add('__unknown_index__'); }
  // Do not execute a clean filter merely to discover a scope it may conceal.
  try { if (hasGitSourceTransformAttributes(cwd)) return [...files, '__git_source_transforms__']; }
  catch { return [...files, '__unknown_source_attributes__']; }
  // Treat renames as deletion + addition so both source and destination gates
  // survive moves across categories or special scenario dependency paths.
  if (base !== undefined) {
    try {
      if (typeof base !== 'string' || !base) throw new Error('Missing base');
      const resolved = readGit('rev-parse','--verify','--end-of-options',`${base}^{commit}`).trim();
      for (const file of readGit('diff','--no-renames','--name-only','-z',resolved,'HEAD','--').split('\0')) if (file) files.add(file);
    } catch { files.add('__unknown_base__'); }
  }
  for (const args of [['diff','--no-renames','--name-only','-z','HEAD','--'],['ls-files','--others','--exclude-standard','-z']])
    for (const file of readGit(...args).split('\0')) if (file) files.add(file);
  return [...files];
}
const run = (command,args) => execFileSync(command,args,{stdio:'inherit',shell:process.platform==='win32'&&command==='npm'});
// These are executable scenarios, not just categories. Source dependencies below
// augment the normal consumer gates; unknown files still require the full gate.
export function scenarioPlan(files, checks = selectChecks(files)) {
  if (checks.includes('full')) return {browser: Object.values(browserSuites).flat(), windows: ['companion-process-identity-e2e', 'setup-e2e', 'update-companion-e2e']};
  const browser = new Set(), windows = new Set();
  if (checks.includes('desktop')) browser.add('language-account-e2e');
  if (files.includes('scripts/browser-e2e.mjs')) browser.add('browser-e2e');
  if (checks.includes('mobile')) for (const name of ['companion-e2e','mobile-reader-layout-e2e','mobile-games-e2e','ocr-packs-e2e']) browser.add(name);
  // A source change must exercise actual frames through the receiver as well as
  // the retained QR/PC transport; selecting only layout checks misses lifecycle bugs.
  const frameInputs = /^(public\/mobile-capture\/(frame-source|vdo-source|receiver-source|mobile-ui|ocr-pipeline|capture|index|style)\.|tests\/mobile-(frame-source|vdo-source|receiver-source|source)|scripts\/mobile-(vdo-source|source)-e2e\.mjs$)/;
  const publicationInputs = ['scripts/build-mobile-preview.mjs','scripts/mobile-publication.mjs','tests/mobile-publication.test.mjs','.github/workflows/mobile-preview.yml'];
  if (files.some(file => frameInputs.test(file) || file === 'tests/fixtures/mobile-native-chinese.png' || publicationInputs.includes(file))) {
    for (const name of ['mobile-vdo-source-e2e','mobile-source-e2e','mobile-capture-e2e','mobile-recovery-e2e','mobile-layout-e2e']) browser.add(name);
  }
  if (files.some(file => publicationInputs.includes(file) || ['mobile/companion.jsx','scripts/mobile-update-e2e.mjs'].includes(file))) browser.add('mobile-update-e2e');
  if(files.some(file=>/^(public\/mobile-capture\/library(?:-worker)?\.mjs|backend\/mobile_(?:library|bundle|export_layout)\.py|scripts\/(?:bundle|export)-mobile-library\.py|tests\/mobile-library\.test\.mjs)$/.test(file)))browser.add('mobile-library-e2e');
  if (files.some(file => ['backend/api.py','backend/state_version.py'].includes(file))) for (const name of ['setup-e2e','local-access-e2e']) browser.add(name);
  if (files.some(file => ['backend/api.py','backend/state_version.py','scripts/update-companion.ps1','scripts/companion-runtime.ps1'].includes(file))) windows.add('update-companion-e2e');
  if (files.some(file => ['backend/api.py','backend/state_version.py','app/companion.tsx','app/language-setup.tsx','app/state-sync.ts','scripts/ui-state-e2e.mjs','scripts/ui-state-react-e2e.mjs','scripts/ui-state-browser-server.py','tests/state-sync.test.mjs'].includes(file))) for (const name of ['ui-state-e2e','ui-state-react-e2e']) browser.add(name);
  if (checks.includes('windows')) windows.add('companion-process-identity-e2e');
  return {browser: [...browser].sort(), windows: [...windows].sort()};
}
// This is a plan of real child processes. npm run check remains one aggregate;
// its inner scripts are not inferred as passing if the aggregate fails.
export function commandPlan(checks, {scenarios = scenarioPlan([], checks), platform = process.platform,
  splitBrowsers = process.env.CHECK_SPLIT_BROWSER_TESTS === 'true', environment = process.env, releaseDelegated = false} = {}) {
  const commands = [];
  const npm = script => commands.push({id: `npm:${script}`, command: 'npm', args: script === 'test' ? ['test'] : ['run', script]});
  if (checks.includes('full')) npm('check');
  else {
    if (checks.includes('python')) npm('test:python');
    if (checks.includes('desktop')) npm('typecheck');
    if (checks.some(x => ['desktop','mobile'].includes(x))) npm('lint');
    if (checks.some(x => ['desktop','mobile','selector'].includes(x))) npm('test');
    if (checks.includes('desktop')) npm('build');
    if (checks.includes('mobile')) npm('mobile:build');
  }
  if (releaseDelegated) commands.push({id: 'npm:check', status: 'delegated', reason: 'release-tag'});
  for (const script of scenarios.browser) commands.push({id: `browser:${script}`, command: process.execPath, args: [`scripts/${script}.mjs`], ...(splitBrowsers ? {status: 'delegated', reason: 'split-browser-job'} : {})});
  for (const script of scenarios.windows) commands.push({id: `windows:${script}`, ...(platform !== 'win32' ? {status: 'unavailable', reason: 'requires-windows'} : script === 'update-companion-e2e' ? {command: process.execPath, args: [`scripts/${script}.mjs`]} : {command: 'powershell.exe', args: ['-NoProfile','-ExecutionPolicy','Bypass','-File',`scripts/${script}.ps1`,'-VerifyBaseline']})});
  commands.push({id: 'docs:check', command: process.execPath, args: ['scripts/check-docs.mjs']});
  const skipAudit = environment.CHECK_SKIP_PUBLIC_AUDIT === 'true' && environment.GITHUB_ACTIONS === 'true' && environment.GITHUB_EVENT_NAME === 'pull_request';
  commands.push({id: 'audit:public', command: 'npm', args: ['run','audit:public'], ...(skipAudit ? {status: 'delegated', reason: 'ci-head-audit'} : {})});
  return commands;
}

export function executeChecks(checks, options = {}) {
  const {runCommand = run, evidence} = options;
  const commands = commandPlan(checks, options), unavailable = [], delegated = [];
  evidence?.setPlan(checks, commands);
  for (const {id, command, args, status, reason} of commands) {
    if (status) {
      evidence?.markCommand(id, status, reason);
      if (status === 'unavailable') {
        unavailable.push(id.slice('windows:'.length));
        console.log('Requires hosted Windows validation: ' + id);
      } else delegated.push(id);
      continue;
    }
    evidence?.startCommand(id);
    try { runCommand(command, args); evidence?.finishCommand(id); }
    catch (error) { evidence?.finishCommand(id, error); throw error; }
  }
  return {unavailable, delegated};
}

function isReleaseDelegated(cwd, environment) {
  if (environment.GITHUB_EVENT_NAME !== 'push' || environment.GITHUB_REF !== 'refs/heads/main') return false;
  const releaseTag = 'v' + JSON.parse(readFileSync(`${cwd}/package.json`, 'utf8')).version;
  return execFileSync('git', ['tag','--points-at','HEAD'], {cwd, encoding: 'utf8'}).trim().split('\n').includes(releaseTag);
}

export function runChangedChecks({base, full = false, cwd = process.cwd(), environment = process.env,
  runCommand = (command, args) => execFileSync(command, args, {cwd, stdio: 'inherit', shell: process.platform === 'win32' && command === 'npm'}),
  platform = process.platform, releaseDelegated} = {}) {
  const evidence = startCheckRun({cwd, base, environment});
  let failed = false;
  try {
    releaseDelegated ??= isReleaseDelegated(cwd, environment);
    const files = changedFiles(base, {cwd});
    const checks = releaseDelegated ? [] : selectChecks(files, full);
    const scenarios = releaseDelegated ? {browser: [], windows: []} : scenarioPlan(files, checks);
    console.log('Selected checks: ' + (checks.join(', ') || 'publication only'));
    console.log('Required scenarios: ' + JSON.stringify(scenarios));
    const options = {scenarios, platform, environment, releaseDelegated, splitBrowsers: environment.CHECK_SPLIT_BROWSER_TESTS === 'true', runCommand, evidence};
    evidence.setPlan(checks, commandPlan(checks, options));
    if (evidence.record.sourceBefore.base.status === 'unavailable' || evidence.record.sourceBefore.sourceStatus !== 'available') {
      console.error(evidence.record.sourceBefore.sourceIssue === 'hidden-index-entries'
        ? 'Git assume-unchanged or skip-worktree flags hide source changes; no checks ran and no valid evidence can be produced.'
        : evidence.record.sourceBefore.sourceIssue === 'git-source-transforms'
          ? 'Applied Git source transform attributes can hide source changes; no filters or checks ran and no valid evidence can be produced.'
          : 'Check source or requested base is unavailable; no valid check evidence can be produced.');
    } else executeChecks(checks, options);
  } catch (error) { console.error(error); failed = true; }
  return evidence.finish({failed});
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const baseIndex = process.argv.indexOf('--base');
  const base = baseIndex >= 0 ? (process.argv[baseIndex + 1] ?? '') : (process.env.CHECK_BASE || undefined);
  const full = process.argv.includes('--full');
  if (!process.argv.includes('--plan')) process.exitCode = runChangedChecks({base, full}).exitCode;
  else {
    const delegated = isReleaseDelegated(process.cwd(), process.env);
    const files = changedFiles(base), checks = delegated ? [] : selectChecks(files, full);
    const scenarios = delegated ? {browser: [], windows: []} : scenarioPlan(files, checks);
    console.log('Required scenarios: ' + JSON.stringify(scenarios));
    if (delegated) console.log('Comprehensive checks are delegated to the release tag workflow.');
    console.log('Selected checks: ' + (checks.join(', ') || 'publication only'));
    if (process.env.GITHUB_OUTPUT) for (const [key,value] of Object.entries({
      checks: JSON.stringify(checks), dependencies: checks.some(x => x !== 'docs'),
      python: checks.some(x => x === 'full' || x === 'python'), browsers: scenarios.browser.length > 0,
      full: checks.includes('full')
    })) appendFileSync(process.env.GITHUB_OUTPUT, `${key}=${value}\n`);
  }
}
