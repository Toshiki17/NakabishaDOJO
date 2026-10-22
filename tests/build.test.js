// web/nakabisha.html を直したのに ios/www/ を作り直し忘れていないか。
const test = require('node:test');
const assert = require('node:assert');
const { spawnSync } = require('child_process');
const path = require('path');

test('ios/www/index.html が web/nakabisha.html から作り直してある', () => {
  const r = spawnSync('python3', [path.join(__dirname, '../scripts/build_web.py'), '--check'], { encoding: 'utf8' });
  assert.strictEqual(r.status, 0, r.stderr || r.stdout);
});
