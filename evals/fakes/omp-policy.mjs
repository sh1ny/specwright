import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';

const [modulePath, casesPath] = process.argv.slice(2);
const spec = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
const report = {loaded: false, results: []};
let callback;
let exitCode = 0;
if (modulePath !== '-') {
  try {
    const bytes = fs.readFileSync(modulePath);
    report.sha256 = createHash('sha256').update(bytes).digest('hex');
    report.module_source = bytes.toString('utf8');
    if (spec.mode === 'load-failure') fs.writeFileSync(modulePath, 'export default function (\n');
    const {default: register} = await import(pathToFileURL(modulePath).href);
    await register({on(name, fn) {
      if (name !== 'tool_call' || callback) throw new Error('unexpected policy registration');
      callback = fn;
    }});
    if (!callback) throw new Error('missing tool_call hook');
    report.loaded = true;
  } catch (error) {
    report.load_error = String(error);
    exitCode = 1;
  }
}

if (!exitCode) {
  for (let i = 0; i < spec.cases.length; i++) {
    const item = spec.cases[i];
    let decision;
    try {
      // Fault injection in the trusted host, matching the native throwing-hook
      // control: a callback fault cannot become an unguarded native call.
      if (callback && spec.mode === 'callback-failure') throw new Error('fixture callback failure');
      decision = callback ? await callback({type: 'tool_call', toolCallId: String(i), toolName: item.tool, input: item.input}, {cwd: spec.cwd}) : undefined;
    } catch (error) {
      report.results.push({tool: item.tool, blocked: true, isError: true, error: String(error)});
      exitCode = 17;
      continue;
    }
    if (decision?.block) {
      report.results.push({tool: item.tool, blocked: true, isError: true, error: decision.reason});
      continue;
    }
    const args = decision?.input ?? item.input;
    let output;
    if (item.remote) {
      // This is a controlled fake backend, not a second URI classifier: test
      // records specify whether dispatch would contact the loopback fixture.
      output = await (await fetch(`http://${spec.host}:${spec.port}/fixture`)).text();
    } else if (item.tool === 'read') {
      output = fs.readFileSync(path.resolve(spec.cwd, args.path), 'utf8');
    } else if (item.tool === 'lsp') {
      output = fs.readFileSync(path.resolve(spec.cwd, args.file), 'utf8').split('\n')[0];
    } else {
      const target = path.resolve(spec.cwd, args.path ?? '.');
      output = fs.statSync(target).isDirectory() ? fs.readdirSync(target) : fs.readFileSync(target, 'utf8');
    }
    report.results.push({tool: item.tool, blocked: false, isError: false, output});
  }
}
process.stdout.write(JSON.stringify(report));
process.exitCode = exitCode;
