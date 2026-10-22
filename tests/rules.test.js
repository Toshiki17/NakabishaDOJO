// 盤面ルール（legality・play・notate）と簡易エンジン（E）の基本動作。
const test = require('node:test');
const assert = require('node:assert');
const { openApp } = require('./helpers');

let app;
test.before(async () => { app = await openApp(); });
test.after(async () => { await app.browser.close(); });

// 初期局面から手順 moves を進めた局面で、side が mv を指したときの legality の結果
const legalAfter = (moves, mv, side) => app.page.evaluate(([moves, mv, side]) => {
  let p = initial();
  moves.forEach((m, i) => { p = play(p, m, i % 2); });
  return legality(p, mv, side);
}, [moves, mv, side]);

test('初期局面の合法手は30手', async () => {
  const n = await app.page.evaluate(() => E.legalMoves(E.fromMap(initial()), 0).length);
  assert.strictEqual(n, 30);
});

test('ふつうの手は指せる', async () => {
  assert.strictEqual(await legalAfter([], '7776', 0), null);
  assert.strictEqual(await legalAfter(['7776'], '3334', 1), null);
});

test('動けないマスへの移動・相手の駒の移動は反則', async () => {
  assert.match(await legalAfter([], '7775', 0), /動けません/);
  assert.match(await legalAfter([], '3334', 0), /自分の駒/);
});

test('角交換のあと、持ち駒の角を打てる／駒のいるマスには打てない', async () => {
  const moves = ['7776', '3334', '8822+', '3122'];
  assert.strictEqual(await legalAfter(moves, 'B*55', 0), null);
  assert.match(await legalAfter(moves, 'B*76', 0), /駒がいる/);
  assert.match(await legalAfter(moves, 'R*55', 0), /持ち駒にない/);
});

test('二歩は反則', async () => {
  // 先手が歩を取ったあと、歩のある筋に打つ
  const moves = ['7776', '3334', '7675', '3435', '7574', '3536', '7473+', '3637+'];
  assert.match(await legalAfter(moves, 'P*55', 0), /二歩/);
  assert.strictEqual(await legalAfter(moves, 'P*75', 0), null);
});

test('王手を放置する手は反則', async () => {
  const r = await app.page.evaluate(() => {
    // 先手玉5九・金6九、後手玉5一・飛車5五。先手は王手されている
    const p = { b: { '59': { t: 'K', s: 0 }, '69': { t: 'G', s: 0 }, '51': { t: 'K', s: 1 }, '55': { t: 'R', s: 1 } }, h: [{}, {}] };
    return { ignore: legality(p, '6978', 0), block: legality(p, '6958', 0), escape: legality(p, '5948', 0) };
  });
  assert.match(r.ignore, /王手放置/);
  assert.strictEqual(r.block, null);
  assert.strictEqual(r.escape, null);
});

test('棋譜の表記（▲△・同・成）', async () => {
  const r = await app.page.evaluate(() => {
    let p = initial();
    const a = notate(p, '7776', 0, p.to); p = play(p, '7776', 0);
    const b = notate(p, '3334', 1, p.to); p = play(p, '3334', 1);
    const c = notate(p, '8822+', 0, p.to); p = play(p, '8822+', 0);
    const d = notate(p, '3122', 1, p.to);
    return [a, b, c, d];
  });
  assert.deepStrictEqual(r, ['▲７六歩', '△３四歩', '▲２二角成', '△同銀']);
});

test('簡易エンジンはただで取れる駒を取る', async () => {
  const best = await app.page.evaluate(() => {
    const p = initial();
    p.b['56'] = { t: 'R', s: 1 }; // 先手の5筋の歩の前に後手の飛車を置く
    return E.bestMoves(p, 0, 2)[0].m;
  });
  assert.strictEqual(best, '5756');
});
