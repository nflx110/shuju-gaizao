#!/usr/bin/env node
/**
 * 本机小服务：把瀑布流截图交给 Cursor Agent（和 Cursor 对话同一套接口）识图下结论。
 * 用法：在本目录执行  npm install && node shot_ai_server.mjs
 * 浏览器打开 http://127.0.0.1:8788/瀑布流广告位置解析.html
 */
import { createServer } from "http";
import { readFileSync, existsSync, statSync } from "fs";
import { extname, join, dirname, normalize } from "path";
import { fileURLToPath } from "url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const HOST = "127.0.0.1";
const PORT = Number(process.env.SHOT_AI_PORT || 8788);
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
};

function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, x-cursor-api-key");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
}

function send(res, code, body, type = "application/json; charset=utf-8") {
  cors(res);
  res.writeHead(code, { "Content-Type": type });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
}

function readBody(req, limit = 40 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let n = 0;
    req.on("data", (c) => {
      n += c.length;
      if (n > limit) {
        reject(new Error("请求过大"));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function extractJson(text) {
  const raw = String(text || "").trim();
  const fence = raw.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const s = fence ? fence[1].trim() : raw;
  const start = s.indexOf("{");
  const end = s.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("模型没有返回 JSON");
  return JSON.parse(s.slice(start, end + 1));
}

function buildPrompt(ctx) {
  const group = ctx.group === "A" ? "对照组：第1、4、6行尾帧，第6行后每3行" : "实验组：第1、2、4行尾帧，第4行后每3行";
  return [
    "你是爱奇艺瀑布流广告插位核查助手。用户按从上到下、从左到右的阅读顺序上传了多张前端页面截图（可能是翻页或滚动）。",
    "请自己判断截图顺序（文件名顺序已排好，一般就是页面顺序），在脑中拼接成连续瀑布流。",
    "当前规则：一行 " + ctx.cols + " 格；" + group + "。尾帧=该行最后一格，格号=行号×" + ctx.cols + "。",
    "截图第一格对应 order " + ctx.startOrder + "。",
    ctx.expectOrders && ctx.expectOrders.length
      ? "实验组预期尾帧格号：" + ctx.expectOrders.join("、")
      : "",
    ctx.backendAds && ctx.backendAds.length
      ? "后端接口已解析出的广告格：" + ctx.backendAds.join("、")
      : "没有后端列表时，只对照实验组规则。",
    "请看图找出带「广告」角标/水印的卡片，给出它们在拼接后瀑布流里的格号（从1计，按一行" + ctx.cols + "格）。",
    "只输出一个 JSON，不要 Markdown 解释。字段：",
    '{"ok":true或false,"summary":"一句话结论","shotAds":[格号],"leaks":[{"row":行,"order":格,"reason":"漏插说明"}],"extras":[{"row":行,"col":列,"order":格,"reason":"插错说明"}],"details":["补充"],"pageOrder":["文件名顺序"]}',
    "ok=true 仅当截图广告格与预期尾帧一致（允许截图未覆盖到的更后面预期格不算漏插）。",
    "files=" + JSON.stringify(ctx.filenames || []),
  ]
    .filter(Boolean)
    .join("\n");
}

async function runCursorVision(apiKey, modelId, ctx, images) {
  const { Agent } = await import("@cursor/sdk");
  const agent = await Agent.create({
    apiKey,
    model: { id: modelId || "auto" },
    local: { cwd: ROOT },
  });
  try {
    const run = await agent.send({
      text: buildPrompt(ctx),
      images: images.map((img) => ({
        data: img.data,
        mimeType: img.mimeType || "image/jpeg",
      })),
    });
    const result = await run.wait();
    if (result.status === "error") {
      throw new Error((result.error && result.error.message) || "Agent 运行失败");
    }
    const text = result.result || "";
    const parsed = extractJson(text);
    parsed.raw = text;
    return parsed;
  } finally {
    if (agent && typeof agent[Symbol.asyncDispose] === "function") {
      await agent[Symbol.asyncDispose]();
    } else if (agent && typeof agent.close === "function") {
      await agent.close();
    }
  }
}

const server = createServer(async (req, res) => {
  cors(res);
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }
  const url = new URL(req.url || "/", "http://" + HOST);
  if (req.method === "GET" && url.pathname === "/api/health") {
    let sdk = false;
    try {
      await import("@cursor/sdk");
      sdk = true;
    } catch (_) {}
    send(res, 200, {
      ok: true,
      sdk,
      hasEnvKey: Boolean(process.env.CURSOR_API_KEY),
      port: PORT,
    });
    return;
  }
  if (req.method === "POST" && url.pathname === "/api/ai-vision") {
    try {
      const payload = JSON.parse(await readBody(req));
      const apiKey = String(req.headers["x-cursor-api-key"] || process.env.CURSOR_API_KEY || "").trim();
      if (!apiKey) {
        send(res, 401, {
          error: "缺少 CURSOR_API_KEY。在页面里填写，或启动服务前 export CURSOR_API_KEY=...",
        });
        return;
      }
      const images = Array.isArray(payload.images) ? payload.images : [];
      if (!images.length) {
        send(res, 400, { error: "没有图片" });
        return;
      }
      const ctx = payload.context || {};
      const modelId = payload.model || "auto";
      setShotLog("识别中，图片 " + images.length + " 张，模型 " + modelId);
      const result = await runCursorVision(apiKey, modelId, ctx, images);
      send(res, 200, { ok: true, result });
    } catch (e) {
      send(res, 500, { error: e.message || String(e) });
    }
    return;
  }
  if (req.method === "GET") {
    let rel = decodeURIComponent(url.pathname);
    if (rel === "/") rel = "/瀑布流广告位置解析.html";
    const fp = normalize(join(ROOT, rel.replace(/^\/+/, "")));
    if (!fp.startsWith(ROOT)) {
      send(res, 403, { error: "forbidden" });
      return;
    }
    if (!existsSync(fp) || !statSync(fp).isFile()) {
      send(res, 404, { error: "not found" });
      return;
    }
    const type = MIME[extname(fp).toLowerCase()] || "application/octet-stream";
    cors(res);
    res.writeHead(200, { "Content-Type": type });
    res.end(readFileSync(fp));
    return;
  }
  send(res, 404, { error: "not found" });
});

function setShotLog(msg) {
  console.log("[shot-ai]", msg);
}

server.listen(PORT, HOST, () => {
  console.log("瀑布流 AI 识图服务 http://" + HOST + ":" + PORT + "/瀑布流广告位置解析.html");
  if (!process.env.CURSOR_API_KEY) {
    console.log("未检测到 CURSOR_API_KEY。可在页面填写，或先执行：export CURSOR_API_KEY=你的密钥");
    console.log("密钥在 Cursor Dashboard → Integrations");
  }
});
