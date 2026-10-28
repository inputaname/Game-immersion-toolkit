import {test} from 'node:test';import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {readFileSync} from 'node:fs';
test('installer contains contribution instructions and separate per-PC game picker',()=>{
 for(const file of ['INSTALL.md','INSTALL.html','CONTRIBUTING.md','scripts/install.ps1'])assert(readFileSync(file,'utf8').includes('AGENTS.md'));
 assert(readFileSync('Choose Game Folders.cmd','utf8').includes('select-game-folders.ps1'));
});
test('Windows installer scripts parse and instructions-only mode does not open dialogs',{skip:process.platform!=='win32'},()=>{
 const command="$ErrorActionPreference='Stop'; foreach ($file in @('scripts/install.ps1','scripts/select-game-folders.ps1','scripts/setup.ps1','scripts/companion-runtime.ps1','scripts/update-companion.ps1','scripts/retire-companion.ps1','scripts/start-companion.ps1','scripts/stop-companion.ps1')) { $tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) $file),[ref]$tokens,[ref]$errors) | Out-Null; if ($errors) { throw ($errors -join '; ') } }; & scripts/install.ps1 -InstructionsOnly; & scripts/select-game-folders.ps1 -InstructionsOnly";
 const output=execFileSync('powershell.exe',['-NoProfile','-Command',command],{encoding:'utf8'});assert(output.includes('CONTRIBUTING.md'));assert(output.includes('Cancel keeps existing settings'));
});
test('game folder picker builds one row per catalog game in Windows PowerShell 5.1',()=>{
 const source=readFileSync('scripts/select-game-folders.ps1','utf8');
 // $input is an automatic variable; the picker must never assign it.
 assert.doesNotMatch(source,/\$input\s*=/);
 const line=source.split('\n').find(text=>text.includes('--catalog'));
 assert.match(line,/ConvertFrom-Json \| ForEach-Object \{ \$_ \}/,'5.1 returns a JSON array as one object unless it is unrolled');
});
test('unrolled game catalog yields separate games in Windows PowerShell',{skip:process.platform!=='win32'},()=>{
 const line=readFileSync('scripts/select-game-folders.ps1','utf8').split('\n').find(text=>text.includes('--catalog')).trim();
 // Run the script's own expression with a synthetic catalog in place of Python.
 const expression=line.replace(/& \$python -m scripts\.configure_game_paths --catalog/,"'[{\"id\":\"zzz\",\"name\":\"A\"},{\"id\":\"witcher3\",\"name\":\"B\"}]'");
 const command=expression+"; if ($games.Count -ne 2 -or $games[1].id -ne 'witcher3') { throw 'catalog not unrolled' }; 'ok'";
 const output=execFileSync('powershell.exe',['-NoProfile','-EncodedCommand',Buffer.from(command,'utf16le').toString('base64')],{encoding:'utf8'});
 assert.equal(output.trim(),'ok');
});
test('source installer uses the canonical frontend build with generated mobile assets',()=>{
 const setup=readFileSync('scripts/setup.ps1','utf8');
 assert.match(setup,/& npm run build\b/,'Setup must run the same asset preparation and frontend build as releases');
 assert.doesNotMatch(setup,/& node \$vinext build/);
});
test('persisted process IDs cannot bypass process identity checks',()=>{
 for(const name of ['start','stop','retire','update']){
  const source=readFileSync('scripts/'+name+'-companion.ps1','utf8');
  assert.doesNotMatch(source,/& taskkill\.exe/,'Persisted process termination must use the identity helper: '+name);
 }
 assert.match(readFileSync('scripts/start-companion.ps1','utf8'),/Read-CompanionProcesses/);
 assert.match(readFileSync('scripts/stop-companion.ps1','utf8'),/Read-CompanionProcesses/);
});
