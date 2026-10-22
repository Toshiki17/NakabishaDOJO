// テスト共通：アプリに同梱するページ（ios/www/index.html）をスマホ相当の画面で開く。
const { chromium } = require('playwright');
const path = require('path');

const PAGE_URL = 'file://' + path.resolve(__dirname, '../ios/www/index.html');

async function openApp({ colorScheme = 'light' } = {}) {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, colorScheme,
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  // 読み込み中にエラーが出たら（定跡データの打ち間違いで盤が作れないなど）、待たずにすぐ失敗させる
  const crashed = new Promise((_, reject) => page.once('pageerror', e => reject(new Error('ページの読み込みでエラー（定跡データの打ち間違いなど）: ' + e.message))));
  crashed.catch(() => {});
  try {
    await page.goto(PAGE_URL);
    await Promise.race([
      page.waitForFunction(() => typeof LINES !== 'undefined' && document.querySelector('#board .cell')),
      crashed,
    ]);
  } catch (e) {
    await browser.close();
    throw e;
  }
  return { browser, page, errors };
}

module.exports = { openApp };
