// 画面の操作：ページが開く・盤をタップして指す・定跡を最後まで進める・腕試し・棋譜の読み込み。
const test = require('node:test');
const assert = require('node:assert');
const { openApp } = require('./helpers');

let app;
test.beforeEach(async () => { app = await openApp(); });
test.afterEach(async () => {
  await app.browser.close();
  assert.deepStrictEqual(app.errors, [], 'ページでエラーが出ました');
});

const tap = k => app.page.click(`#board .cell[data-k="${k}"]`);
const state = () => app.page.evaluate(() => ({
  path: S.path.map(n => n.m), mistakes: S.mistakes, lock: S.lock, finished: !!S.finished,
  cards: S.cards.map(c => c.tag),
}));
const idle = () => app.page.waitForFunction(() => !S.lock);

test('ページが開き、盤と操作バーが出る', async () => {
  const { page } = app;
  assert.strictEqual(await page.title(), '中飛車道場');
  assert.strictEqual(await page.locator('#board .cell').count(), 81);
  assert.ok(await page.locator('#toolbar [data-act="answer"]').isVisible());
});

test('盤をタップして定跡どおりに指すと「正解」になり、相手の応手を選べる', async () => {
  await tap('57'); await tap('56');
  await idle();
  const s = await state();
  assert.deepStrictEqual(s.path, ['5756']);
  assert.strictEqual(s.mistakes, 0);
  assert.ok(s.cards.includes('正解'));
  // 相手の手が分岐するので、どれを指させるか選ぶボタンが出る
  await app.page.locator('#msg [data-kid]').first().click();
  await app.page.waitForFunction(() => S.path.length === 2);
});

test('反則の手は指せず、定跡と違う手はミスとして数える', async () => {
  await tap('57'); await tap('55');
  let s = await state();
  assert.deepStrictEqual(s.path, []);
  assert.ok(s.cards.includes('指せない手'));

  // ▲8六歩はAIの評価が大きく下がる手
  await tap('87'); await tap('86');
  await idle();
  s = await state();
  assert.deepStrictEqual(s.path, []);
  assert.strictEqual(s.mistakes, 1);
});

test('「答え」と分岐の選択だけで、定跡を最後まで進めて記録が残る', async () => {
  const { page } = app;
  for (let i = 0; i < 200 && !(await state()).finished; i++) {
    await idle();
    const choice = page.locator('#msg [data-kid]');
    if (await choice.count()) await choice.first().click();
    else if (await page.evaluate(() => isUserTurn() && cur().kids.length)) await page.click('#toolbar [data-act="answer"]');
  }
  assert.ok((await state()).finished, '最後まで進みませんでした');
  const rec = await page.evaluate(() => JSON.parse(localStorage.getItem('nakabisha-dojo3')));
  assert.strictEqual(rec.sente.cleared.length, 1);
});

// 腕試しを始めて、自分の手を1手指し、相手が応じるまで進める
async function startTestAndPlay(page) {
  await page.click('[data-mode="test"]');
  await page.waitForFunction(() => isTest() && !S.lock);
  if (await page.evaluate(() => isUserTurn())) await page.click('#toolbar [data-act="answer"]');
  await page.waitForFunction(() => S.path.length >= 2 && !S.lock);
}

test('腕試しが始まり、相手が指す', async () => {
  await startTestAndPlay(app.page);
});

test('シート（解説・設定）が開いて閉じる', async () => {
  const { page } = app;
  await page.click('#toolbar [data-act="detail"]');
  await page.waitForFunction(() => UI.sheet);
  await page.click('#scrim');
  await page.waitForFunction(() => !UI.sheet);
  await page.click('#menuBtn');
  await page.waitForFunction(() => UI.sheet);
});

test('KIFを読み込める（消費時間の列がなくても）', async () => {
  const r = await app.page.evaluate(() => [
    parseKif('手合割：平手\n手数----指手---------消費時間--\n   1 ５六歩(57)   ( 0:01/00:00:01)\n   2 ８四歩(83)   ( 0:01/00:00:01)\n   3 ７六歩(77)   ( 0:01/00:00:02)\n'),
    parseKif('手合割：平手\n1 ５六歩(57)\n2 ３四歩(33)\n3 ７六歩(77)\n4 ８八角成(22)\n5 同　銀(79)\n'),
  ]);
  assert.deepStrictEqual(r[0].moves, ['5756', '8384', '7776']);
  assert.deepStrictEqual(r[1].moves, ['5756', '3334', '7776', '2288+', '7988']);
  assert.ok(r.every(x => !x.err));
});

test('ダークモードでもエラーなく開く', async () => {
  await app.browser.close();
  app = await openApp({ colorScheme: 'dark' });
  await startTestAndPlay(app.page);
});
