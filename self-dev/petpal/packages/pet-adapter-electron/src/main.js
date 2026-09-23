// pet-adapter-electron —— petpal 一键唤醒 DSH 工作台的 Electron 薄壳
// 核心能力：全局快捷键唤起 + 让 DSH Web (127.0.0.1:3080) 在一个独立桌面包里打开
"use strict";

const { app, BrowserWindow, globalShortcut, Tray, Menu, shell, nativeImage, session } = require("electron");
const path = require("path");
const dshAuth = require("./dsh-auth");

// 无 GPU/虚拟显示环境兼容：禁用 GPU 硬件加速（避免 GPU 进程崩溃退出）
app.disableHardwareAcceleration();

// --no-sandbox：部分受限容器/root 环境需要（如 CI、docker、无特权沙箱）
if (process.env.PETPAL_NO_SANDBOX === "1") {
  app.commandLine.appendSwitch("no-sandbox");
}

// 受限容器/无 /dev/shm 环境：让 Chromium 走磁盘临时目录，避免崩溃
if (process.env.PETPAL_SHM_FIX === "1") {
  app.commandLine.appendSwitch("disable-dev-shm-usage");
}

// ---- 配置（可后续迁移到 pet-core，这里先内联）----
const CONFIG = {
  // DSH Web 地址（当前会话实例已验证在跑）
  dshUrl: process.env.DSH_URL || "http://127.0.0.1:3080",
  // 默认全局快捷键；Linux 下 Cmd+Space 常被 IME 占用，故 Linux 用 Ctrl+Alt+P，其他平台 CmdOrCtrl+Shift+A
  hotkey: process.env.PETPAL_HOTKEY
    || (process.platform === "linux" ? "Control+Alt+P" : "CommandOrControl+Shift+A"),
  // 是否启用托盘常驻（false 时关窗即退出，更简单）
  tray: process.env.PETPAL_TRAY !== "0",
  // 窗口尺寸
  width: 1280,
  height: 820,
};

let mainWindow = null;
let tray = null;

// ---- DSH 认证：用固定 secret 签发持久 cookie，注入 Electron session ----
// 这样"一键唤起"加载 / 时自动带上认证，直达已认证工作台（30 天内有效）。
async function ensureAuthCookie() {
  try {
    const { secret } = dshAuth.readStoredSecret();
    if (!secret) {
      console.warn("[petpal] 未在 ~/.dsh/.credentials.yaml 找到 browser-session secret，可能无法直达已认证 DSH");
      return;
    }
    const cookies = session.defaultSession.cookies;
    const existing = await cookies.get({ url: CONFIG.dshUrl });
    const ck = dshAuth.buildAuthCookie(CONFIG.dshUrl, secret, 30);

    // healthcheck 模式：监听响应状态码，验证是否仍出现 401
    if (process.env.PETPAL_HEALTHCHECK === "1") {
      session.defaultSession.webRequest.onCompleted((details) => {
        if (details.statusCode !== 200 && details.statusCode !== 204) {
          console.log(`[healthcheck] 非200响应: ${details.statusCode} ${details.url}`);
        }
      });
    }

    // 若已有同名 cookie 且未过期则跳过（避免每次重建）
    const already = existing.find((c) => c.name === ck.name && c.expirationDate * 1000 > Date.now());
    if (already) {
      console.log("[petpal] 已存在有效的 DSH 认证 cookie");
      return;
    }
    await cookies.set({
      url: CONFIG.dshUrl,
      name: ck.name,
      value: ck.value,
      path: "/",
      expirationDate: Math.floor(ck.expires.getTime() / 1000),
      httpOnly: true,
      sameSite: "strict",
    });
    console.log("[petpal] 已注入 DSH 认证 cookie (固定 secret 签发)");
  } catch (e) {
    console.warn("[petpal] 注入 DSH 认证 cookie 失败: " + e.message);
  }
}

// ---- 创建主窗口：加载 DSH Web ----
function createWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
    return mainWindow;
  }

  mainWindow = new BrowserWindow({
    width: CONFIG.width,
    height: CONFIG.height,
    title: "petpal · DSH",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  // 加载 DSH Web 工作台
  mainWindow.loadURL(CONFIG.dshUrl).catch((err) => {
    // DSH 服务未启动时给出提示，而不是白屏
    mainWindow.loadURL(
      "data:text/html;charset=utf-8," +
        encodeURIComponent(
          `<h2>无法连接 DSH 服务</h2><p>请先运行 <code>dsh web</code>，或设置 <code>DSH_URL</code>。</p><p>尝试连接：${CONFIG.dshUrl}</p>`
        )
    ).catch(() => {});
  });

  // 健康检查模式：加载完成后打印状态并退出（用于验证 Electron 内嵌加载 DSH 是否成功）
  mainWindow.webContents.on("did-finish-load", () => {
    if (process.env.PETPAL_HEALTHCHECK === "1") {
      const title = mainWindow.getTitle();
      const url = mainWindow.webContents.getURL();
      console.log("[healthcheck] did-finish-load ok");
      console.log("[healthcheck] url = " + url);
      console.log("[healthcheck] title = " + title);
      mainWindow.webContents.executeJavaScript("document.body ? document.body.innerText.slice(0,200) : '(no body)'")
        .then((text) => {
          console.log("[healthcheck] body = " + text);
          setTimeout(() => { app.quit(); }, 500);
        })
        .catch((e) => console.log("[healthcheck] body read failed: " + e.message));
    }
  });

  // 点击链接用系统浏览器打开（外部 http/https 不在 DSH 域内时）
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(CONFIG.dshUrl)) shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // 关窗时：若启用托盘则隐藏而非退出，否则销毁
  mainWindow.on("close", (e) => {
    if (CONFIG.tray && !app.isQuiting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  return mainWindow;
}

// ---- 全局快捷键：唤起/聚焦 DSH 工作台 ----
function registerHotkey() {
  const ok = globalShortcut.register(CONFIG.hotkey, () => {
    const win = createWindow();
    if (win && win.isMinimized()) win.restore();
    win.show();
    win.focus();
  });

  if (!ok) {
    console.warn(`[petpal] 全局快捷键注册失败: ${CONFIG.hotkey}（可能被占用）`);
  } else {
    console.log(`[petpal] 全局快捷键已注册: ${CONFIG.hotkey}`);
  }
}

// ---- 系统托盘（可选）----
function createTray() {
  // 生成一个最小图标（1x1 透明 PNG 兜底，避免缺资源报错）
  const image = nativeImage.createFromDataURL(
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
  );
  tray = new Tray(image);
  tray.setToolTip("petpal · 一键唤起 DSH");
  const menu = Menu.buildFromTemplate([
    { label: "打开 DSH 工作台", click: () => { const w = createWindow(); w.show(); w.focus(); } },
    { type: "separator" },
    { label: "退出", click: () => { app.isQuiting = true; app.quit(); } },
  ]);
  tray.setContextMenu(menu);
  tray.on("click", () => { const w = createWindow(); w.show(); w.focus(); });
}

// ---- 应用生命周期 ----
app.whenReady().then(async () => {
  console.log(`[petpal] 启动，DSH URL = ${CONFIG.dshUrl}`);
  // 先注入认证 cookie，再开窗，保证首屏就是已认证工作台
  await ensureAuthCookie();
  registerHotkey();
  if (CONFIG.tray) createTray();

  // 启动后默认打开一次（也可用 --hidden 只常驻托盘）
  if (!process.argv.includes("--hidden")) createWindow();

  app.on("activate", () => {
    // macOS 点击 Dock 图标时重新建窗
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else createWindow();
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("window-all-closed", () => {
  // 托盘模式下不退出；非托盘模式保持常规行为
  if (!CONFIG.tray || app.isQuiting) app.quit();
});
