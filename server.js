const http = require("http");
const fs = require("fs");
const path = require("path");
const { logEvent } = require("./lib/logger");

const PORT = 8080;
const HOST = "127.0.0.1"; // Bound exclusively to localhost
const PUBLIC_DIR = path.join(__dirname, "public");

const MIME_TYPES = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".mp4": "video/mp4",
  ".svg": "image/svg+xml"
};

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  const pathname = url.pathname;

  // Set CORS headers for local origin operations
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // System status API endpoint
  if (pathname === "/api/status" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: "online",
      binding: `${HOST}:${PORT}`,
      timestamp: new Date().toISOString()
    }));
    return;
  }

  // Micro-service endpoint scaffold for AI micro-tasks
  if (pathname === "/api/microtask" && req.method === "POST") {
    let body = "";
    req.on("data", chunk => body += chunk.toString());
    req.on("end", () => {
      try {
        const payload = JSON.parse(body);
        logEvent("MICROSERVICE", "INFO", "Received microtask request", { task: payload.task });
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, result: "Micro-task endpoint ready", payload }));
      } catch (err) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // API endpoint to save services
  if (pathname === "/api/save-services" && req.method === "POST") {
    let body = "";
    req.on("data", chunk => body += chunk.toString());
    req.on("end", () => {
      try {
        const services = JSON.parse(body);
        const filePath = path.join(PUBLIC_DIR, "services.json");
        fs.writeFileSync(filePath, JSON.stringify(services, null, 2), "utf8");
        logEvent("SYSTEM", "INFO", "Services config updated.");
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, message: "Services saved successfully!" }));
      } catch (err) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // Static file server
  let safePath = path.normalize(pathname).replace(/^(\.\.[\/\\])+/, "");
  if (safePath === "/" || safePath === "\\") {
    safePath = "/index.html";
  }

  const filePath = path.join(PUBLIC_DIR, safePath);

  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403, { "Content-Type": "text/plain" });
    res.end("Forbidden");
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("Not Found");
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";

    res.writeHead(200, {
      "Content-Type": contentType,
      "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=86400"
    });

    const stream = fs.createReadStream(filePath);
    stream.pipe(res);
  });
});

// Explicitly bind server ONLY to 127.0.0.1:8080
server.listen(PORT, HOST, () => {
  logEvent("SYSTEM", "INFO", `Unified origin server listening exclusively on http://${HOST}:${PORT}`);
  console.log(`[+] Unified Origin Server active on http://${HOST}:${PORT}`);
});
