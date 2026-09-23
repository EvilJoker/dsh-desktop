// dsh-auth —— 复刻 DSH dsh-client-connection 的浏览器 cookie 签发算法
// 让 petpal 用 ~/.dsh/.credentials.yaml 里的固定 secret 离线签发持久 cookie，
// 从而"一键打开就是已认证的 DSH 工作台"，不依赖每次随机 launch token。
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const COOKIE_PREFIX = "dsh-auth-";
const COOKIE_PAYLOAD_VERSION = 1;
const STORED_SECRET_VERSION = 1;
const SECRET_BYTES = 32;
const AUTH_RECORD_KEY = "client-connection/browser-session";

// ---- base64url 编解码（与 DSH 完全一致）----
function encodeBase64Url(buf) {
  return Buffer.from(buf).toString("base64").replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}
function decodeBase64Url(s) {
  if (typeof s !== "string" || !/^[A-Za-z0-9_-]*$/.test(s) || s.length % 4 === 1) return undefined;
  const padding = "=".repeat((4 - (s.length % 4)) % 4);
  const decoded = Buffer.from(s.replaceAll("-", "+").replaceAll("_", "/") + padding, "base64");
  return encodeBase64Url(decoded) === s ? decoded : undefined;
}

// ---- 读 ~/.dsh/.credentials.yaml 里的固定 secret ----
function readStoredSecret(dshHome) {
  const credFile = path.join(dshHome || process.env.DSH_HOME || path.join(os.homedir(), ".dsh"), ".credentials.yaml");
  if (!fs.existsSync(credFile)) return { secret: undefined, path: credFile };
  try {
    const lines = fs.readFileSync(credFile, "utf8").split("\n");
    let inSection = false;
    let secretRaw;
    for (const line of lines) {
      if (!inSection && line.trimStart().startsWith(AUTH_RECORD_KEY + ":")) { inSection = true; continue; }
      // 遇到下一个二级 key（缩进归零）则退出该 section
      if (inSection && /^[^\s#]/.test(line) && !line.trimStart().startsWith(AUTH_RECORD_KEY)) break;
      if (inSection) {
        const sm = line.match(/^\s*secret:\s*([A-Za-z0-9_\-]+)\s*$/);
        if (sm) secretRaw = sm[1].trim();
      }
    }
    if (!secretRaw) return { secret: undefined, path: credFile, reason: "no secret field" };
    const decoded = decodeBase64Url(secretRaw);
    if (!decoded || decoded.byteLength !== SECRET_BYTES) return { secret: undefined, path: credFile, reason: "bad secret" };
    return { secret: decoded, raw: secretRaw, path: credFile };
  } catch (e) {
    return { secret: undefined, path: credFile, error: e.message };
  }
}

// ---- cookie 构造（与 DSH 同构）----
function cookieName(authority) {
  return COOKIE_PREFIX + encodeBase64Url(crypto.createHash("sha256").update(authority).digest());
}
function signature(secret, body) {
  return crypto.createHmac("sha256", secret).update(body).digest();
}
function buildAuthCookie(dshUrl, secret, maxAgeDays) {
  const u = new URL(dshUrl);
  const authority = `${u.hostname}:${u.port}`; // 如 127.0.0.1:3080
  const now = Date.now();
  const maxAgeMs = (maxAgeDays || 30) * 24 * 3600 * 1000;
  const body = encodeBase64Url(
    Buffer.from(
      JSON.stringify({
        version: COOKIE_PAYLOAD_VERSION,
        authority,
        issuedAt: now,
        expiresAt: now + maxAgeMs,
      }),
      "utf8"
    )
  );
  const value = `v1.${body}.${encodeBase64Url(signature(secret, body))}`;
  return {
    name: cookieName(authority),
    value,
    domain: u.hostname,
    path: "/",
    url: dshUrl,
    expires: new Date(now + maxAgeMs),
  };
}

module.exports = { readStoredSecret, buildAuthCookie, encodeBase64Url, decodeBase64Url };
