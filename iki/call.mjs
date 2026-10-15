// iki の MCP ツールをコマンドラインから呼ぶ小さなクライアント。
// 使い方: node iki/call.mjs <ツール名> '<JSON 引数>'   （リポジトリのルートで実行）
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const [tool, argJson = "{}"] = process.argv.slice(2);
if (!tool) {
  console.error("usage: node iki/call.mjs <tool> '<json args>'");
  process.exit(2);
}

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [path.join(here, "node_modules/@ikijs/mcp/dist/cli.js")],
  cwd: process.cwd(),
  env: { ...process.env, CHROME_PATH: process.env.CHROME_PATH ?? "" },
});
const client = new Client({ name: "v-call", version: "0.1.0" });
await client.connect(transport);
try {
  const res = await client.callTool({ name: tool, arguments: JSON.parse(argJson) }, undefined, { timeout: 600000 });
  for (const c of res.content ?? []) if (c.type === "text") console.log(c.text);
  if (res.isError) process.exitCode = 1;
} finally {
  await client.close();
}
