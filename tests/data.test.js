// 定跡データと事前計算データの指し手が、すべて将棋のルール上指せる手かを確かめる。
// 打ち込み間違い（駒の位置・筋の数字の取り違えなど）はここで見つかる。
const test = require('node:test');
const assert = require('node:assert');
const { openApp } = require('./helpers');

let app;
test.before(async () => { app = await openApp(); });
test.after(async () => { await app.browser.close(); });

// ページ内で実行する検査。問題のあった手を文字列の配列で返す。
// check(pos, m, side, where) … pos の局面で side が m を指せるか（成り・不成の条件も含む）
const SETUP = () => {
  window.__problems = [];
  window.__check = (p, m, side, where) => {
    const why = legality(p, m, side) || promotionProblem(p, m, side);
    if (why) { __problems.push(`${where}: ${m} … ${why}`); return false; }
    return true;
  };
  function promotionProblem(p, m, side) {
    if (m[1] === '*') return m.length > 4 ? '打った駒は成れません。' : null;
    const from = m.slice(0, 2), to = m.slice(2, 4), pc = p.b[from];
    const zone = r => (side === 0 ? r <= 3 : r >= 7);
    const promo = m[4] === '+';
    if (promo) {
      if (pc.p || pc.t === 'K' || pc.t === 'G') return '成れない駒です。';
      if (!zone(+from[1]) && !zone(+to[1])) return '敵陣に入らないので成れません。';
      return null;
    }
    if (pc.p) return null;
    const r = +to[1], last = side ? 9 : 1, next = side ? 8 : 2;
    if ((pc.t === 'P' || pc.t === 'L') && r === last) return '行き所のない不成です。';
    if (pc.t === 'N' && (r === last || r === next)) return '行き所のない不成です。';
    return null;
  }
  window.__replay = path => {
    let p = initial();
    const ms = path ? path.split(' ') : [];
    for (let i = 0; i < ms.length; i++) {
      if (!__check(p, ms[i], i % 2, `「${path}」の${i + 1}手目`)) return null;
      p = play(p, ms[i], i % 2);
    }
    return p;
  };
  window.__plies = path => (path ? path.split(' ').length : 0);
  window.__checkPV = (p, side, pv, where) => {
    for (let i = 0; i < pv.length; i++) {
      const s = (side + i) % 2;
      if (!__check(p, pv[i], s, `${where} 読み筋${i + 1}手目`)) return;
      p = play(p, pv[i], s);
    }
  };
};

test('定跡ツリー：すべての手と、「よくある別の手」「同じくらい有力な手」が指せる', async () => {
  const problems = await app.page.evaluate(SETUP => {
    eval(`(${SETUP})()`);
    let nodes = 0;
    for (const l of LINES) {
      (function walk(n) {
        for (const k of n.kids) {
          nodes++;
          const where = `${l.title}「${pathOf(k)}」`;
          __check(n.pos, k.m, k.side, where);
          if (k.side !== (n.depth % 2)) __problems.push(`${where}: 手番が合いません`);
          for (const alt of [...Object.keys(k.w || {}), ...Object.keys(k.ok || {})]) {
            __check(n.pos, alt, k.side, `${where} の別の手`);
          }
          walk(k);
        }
      })(l.root);
    }
    if (nodes < 100) __problems.push(`定跡の手が少なすぎます（${nodes}手）`);
    return __problems;
  }, SETUP.toString());
  assert.deepStrictEqual(problems, []);
});

test('事前計算データ（EV・AUTO・OPPDEV）の手と読み筋が指せる', async () => {
  const problems = await app.page.evaluate(SETUP => {
    eval(`(${SETUP})()`);
    for (const [path, rec] of Object.entries(EV)) {
      const p = __replay(path);
      if (!p) continue;
      const side = __plies(path) % 2;
      for (const [m, , pv] of rec.top) {
        if (__check(p, m, side, `EV「${path}」`)) __checkPV(play(p, m, side), 1 - side, pv || [], `EV「${path}」${m}`);
      }
      for (const m of Object.keys(rec.all || {})) __check(p, m, side, `EV「${path}」の候補`);
    }
    for (const [path, list] of Object.entries(AUTO)) {
      const p = __replay(path);
      if (!p) continue;
      for (const a of list) __checkPV(p, __plies(path) % 2, a.chain, `AUTO「${path}」`);
    }
    for (const [path, devs] of Object.entries(OPPDEV)) {
      const p = __replay(path);
      if (!p) continue;
      const side = __plies(path) % 2;
      for (const [m, [best, , pv]] of Object.entries(devs)) {
        if (!__check(p, m, side, `OPPDEV「${path}」相手の手`)) continue;
        __checkPV(play(p, m, side), 1 - side, [best, ...(pv || [])], `OPPDEV「${path}」${m}のあと`);
      }
    }
    return __problems;
  }, SETUP.toString());
  assert.deepStrictEqual(problems, []);
});

test('定跡の各局面に評価値（EV）が付いている', async () => {
  const missing = await app.page.evaluate(() => {
    const out = [];
    for (const l of LINES.filter(l => l.root && l.root.kids.length)) {
      (function walk(n) {
        if (n.kids.length && n.depth % 2 === l.side && !EV[pathOf(n)]) out.push(`${l.title}「${pathOf(n)}」`);
        n.kids.forEach(walk);
      })(l.root);
    }
    return [...new Set(out)];
  });
  assert.deepStrictEqual(missing, []);
});
