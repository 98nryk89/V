import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createBridge, loadConfig } from './bridge.js';

const configFile = process.argv[2] || fileURLToPath(new URL('../config.json', import.meta.url));
let bridge;
try {
  const config = await loadConfig(configFile);
  bridge = createBridge(config);
  await bridge.start();
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.once(signal, async () => {
      console.log('\nKamikanBridgeを終了します。');
      await bridge.stop();
    });
  }
} catch (error) {
  const hint = error.code === 'EADDRINUSE'
    ? 'UDP 11125 / TCP 8765 が使用中です。別の中継プロセスなどを終了してください。'
    : 'config.json のiPhone IPとHTMLフォルダ、Node.jsのバージョンを確認してください。';
  console.error(`起動できません: ${error.code || ''} ${error.message}\n${hint}\n設定: ${path.resolve(configFile)}`);
  process.exitCode = 1;
}
