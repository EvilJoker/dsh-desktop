# DSH Desktop 在中兴云桌面 (NewStartOS) 上开发 — 环境与依赖清单

> 适用: 在中兴内网 NewStartOS Linux 云桌面上,把
> [DSH Desktop](https://github.com/anywhere-labs/deepseek-harness-desktop)
> 项目从源码跑起来(目前官方仅发布 Windows / macOS 安装包)。
> 文档记录 2026-09-23 时的实测环境与关键依赖版本。

---

## 1. 运行环境

| 项目 | 值 |
|---|---|
| 主机 | `LIN-F57BA0762A6.zte.intra`(用户 10312862@zte.intra) |
| 操作系统 | **NewStartOS V4.4.2-ZTE**(基于 el8 的国产化发行版) |
| 内核 | `4.19.112-2.el8.x86_64` |
| 架构 | x86_64 |
| 包管理 | RPM(el8),但本项目用 Node 工具链 |
| 显示 | `DISPLAY=:0`(X11,Xorg 已就位) |
| 网络 | 公司代理 `http://proxyhk.zte.com.cn:80`(已写入 `~/.npmrc`) |
| DNS / 防火墙 | 国内,直连 `npmmirror.com` 正常;`registry.npmjs.org` 走代理 |

## 2. 网络拓扑

| 项 | 值 |
|---|---|
| 公司代理 | `http://proxyhk.zte.com.cn:80`(已在 `~/.npmrc` 中配置) |
| DNS 出口 | 国内,可直连 `npmmirror.com`、`registry.npmjs.org`(经代理) |
| 上游 GitHub | `https://github.com/` 走代理 HTTPS |
| Submodule 源 | `https://github.com/deepseek-ai/deepseek-harness.git` |
| Sandbox 模式 | 已坑,早期 `workspace-write`(只读),后续切到 `danger-full-access`(可写) |

## 3. 关键工具链版本(2026-09-23 实测)

| 工具 | 版本 | 安装位置 | 说明 |
|---|---|---|---|
| Node.js | **v24.13.1** | `/home/10312862@zte.intra/.local/node_coclaw/bin/node` | 项目要求 `^22.19.0 \|\| >=24.0.0` |
| corepack | 0.34.6 | `.local/node_coclaw/bin/corepack` | 启用 Yarn 4 |
| Yarn | **4.18.0**(由 package.json 锁定 `packageManager: yarn@4.18.0`) | `~/.config/nvm/versions/node/v24.6.0/bin/yarn` | 项目唯一受支持的包管理器 |
| npm | 11.8.0 | 同上 Node 内置 | 仅作 fallback |
| pnpm | — | — | upstream 子模块内使用,根项目禁 |
| git | 2.27.0 | `/usr/bin/git` | 含 submodule 支持 |
| Google Chrome | **149.0.7827.102** | `/usr/bin/google-chrome` | 兜底用,Electron 自带 Chromium |
| Electron | **43.3.0**(项目锁定,见 §4) | `node_modules/electron/dist/electron` | DSH Desktop 桌面壳 |

> 注意: Node 与 Yarn 不在同一棵树下,均通过 `node_coclaw` 与 `nvm` 两套机制分别安装。
> 调用时建议用 `corepack yarn ...` 或把 `.local/node_coclaw/bin/` 放 PATH 前。

## 4. 项目核心依赖与下载路径

### 4.1 根 package.json(`packageManager` 锁定)

| 字段 | 值 |
|---|---|
| packageManager | `yarn@4.18.0` |
| engines.node | `^22.19.0 \|\| >=24.0.0` |
| workspaces | `dsh-plugin-desktop`, `dsh-plugin-desktop-beta`, `dsh-community-fabric`, `dsh-community-market`, `dsh-desktop-next` |

### 4.2 Electron 二进制

- 来源仓库: `https://github.com/electron/electron`
- **镜像**: `https://npmmirror.com/mirrors/electron/v43.3.0/electron-v43.3.0-linux-x64.zip`
- 备用: `https://github.com/electron/electron/releases/download/v43.3.0/electron-v43.3.0-linux-x64.zip`
- 大小: ~125 MB
- 解压路径: `<repo>/dsh-plugin-desktop/node_modules/electron/dist/`
- `path.txt`(无 trailing newline):
  ```bash
  printf 'electron' > dsh-plugin-desktop/node_modules/electron/path.txt
  ```
- ⚠️ **不要把 v33 当 v43 用**: v33 内嵌 Node 22.x 不导出 `findPackageJSON`,会导致 `package-overlay-Bh02i6tG.js` 报 `SyntaxError`。

### 4.3 DSH Web(基线)

- 包名: `@deepseek-ai/dsh`(`/usr/local/bin/dsh` → `~/.local/node_coclaw/bin/dsh`)
- 版本: **0.1.5-rc.1**(用户当前在 3080 上跑的就是这个)
- 安装: `npm i -g @deepseek-ai/dsh`(默认走 `~/.npmrc` 的 npmmirror 镜像)

### 4.4 deepseek-harness 子模块

- 位置: `deepseek-harness/`(Git submodule)
- 远程: `https://github.com/deepseek-ai/deepseek-harness.git`
- 当前 pin: `00102833df Merge pull request #4978 from deepseek-ai/worktree/release-dsh-0.1.7-alpha.2`
- 自带 pnpm workspace,**不要**用根 Yarn 安装它,用 `corepack yarn upstream:install/build:` 走 shell 透传

### 4.5 Cordis / 关键上游(`.yarnrc.yml` `npmPreapprovedPackages`)

| 包 | 版本 |
|---|---|
| `@deepseek-ai/cosmokit` | 1.8.3 / 1.8.5 |
| `@deepseek-ai/cordis` | 4.0.2 / 4.0.4 |
| `@deepseek-ai/cordis-plugin-group` | 1.0.2 / 1.0.4 |
| `@deepseek-ai/cordis-plugin-hmr` | 1.0.17 |
| `@deepseek-ai/cordis-plugin-include` | 1.0.7 / 1.0.9 |
| `@deepseek-ai/cordis-plugin-loader` | 1.0.3 / 1.0.5 |
| `@deepseek-ai/cordis-plugin-timer` | 1.1.4 |
| `@deepseek-ai/schemastery` | 3.18.2 |

### 4.6 DSH Profile 默认 bundles(`dsh-app-boot` 内置 web 模板)

```
@deepseek-ai/dsh-base
@deepseek-ai/dsh-web-app
```

用户装的扩展(在 `web` profile,desktop profile 需重装):

```
dshmarket@1.54.0
@linxin666/dsh-client-ui-skill-explorer@^0.3.24
dsh-codex-sync@1.6.1
@goodandready/dsh-usage-guard@0.1.14
dsh-plugin-context-manager  (github:luxiwusuobuneng/dsh-plugin-context-manager)
```

## 5. 网络与镜像

`~/.npmrc`(全局):

```ini
registry=https://registry.npmmirror.com
progress=true
proxy=http://proxyhk.zte.com.cn:80
https-proxy=http://proxyhk.zte.com.cn:80
```

| 资源 | 源 |
|---|---|
| npm 包 | `registry.npmmirror.com` |
| Electron binary | `npmmirror.com/mirrors/electron/` |
| GitHub raw / release | 走代理 `proxyhk.zte.com.cn:80`(HTTPS) |

## 6. DSH Desktop 启动路径(2026-09-23 实测)

### 6.1 一键命令(理论路径)

```bash
# 0. 一次性(项目 clone 后)
git submodule update --init --recursive
corepack yarn install --immutable    # 会触发 electron postinstall
corepack yarn workspace dsh-plugin-desktop build

# 1. 启动(可选开 CDP 给 chrome-devtools-mcp 用)
cd dsh-plugin-desktop
ELECTRON_REMOTE_DEBUGGING=1 node lib/bin.js
```

> 上面是官方 README 的标准 3 步走。**但是在中兴云桌面上,这三步并不能一次走通**,
> 实际启动需要按 §6.2 的"七步绕坑"手动处理若干环境问题。

### 6.2 实际启动七步走(2026-09-23 中兴云桌面实录)

下面按时间顺序记录我从零跑到 DSH Desktop 完整 Electron 进程树的全过程。
每步都标了**实际做了什么 + 为什么这么做 + 遇到什么错**。


**Step 1 — 评估技术栈与启动链路**

先读 `dsh-plugin-desktop/README.md` 和 `package.json`,
摸清启动方式不是普通 Node 应用,而是:

```bash
yarn dev  →  node lib/bin.js  →  spawn(electron, [lib/main.js])
                                       │
                                       └─ Electron 主进程
                                            ├─ Cordis Host :3350
                                            └─ BrowserWindow (加载 127.0.0.1:3350)
```

`bin.js` 第 204 行确认是 `spawn(electronPath, [mainPath], { stdio: 'inherit' })`。
意味着 Electron 启动失败时,所有 stderr 会直接透传到我们的终端,
非常便于排错。


**Step 2 — headless launcher 验证(electron 完全不需要)```bash cd dsh-plugin-desktop node lib/bin.js --version # 输出: 2.0.14 ✓ node lib/bin.js --help # 输出标准 CLI 帮助 ✓ ```这两个命令不调 Electron,直接打印 launcher 自己的逻辑,用来隔离"launcher 本身挂了"和"Electron 挂了"。


**Step 3 — 发现 Electron 二进制缺失**

```bash
ls dsh-plugin-desktop/node_modules/electron/dist/
# 目录不存在!
ls dsh-plugin-desktop/node_modules/electron/path.txt
# 也没有 path.txt
```

意味着 `yarn install` 时 electron postinstall 没成功下到 dist。
查 `~/.cache/electron/` 发现了一个 106 MB 的 `electron-v33.4.11-linux-x64.zip`
(被 dsh-app-boot 早期试装残留),但 package.json 锁定的是 `electron@43.3.0`。

**Step 4 — 手动下载 + 解压 v43**

从 npmmirror 镜像直接拉(走代理 HTTPS,~1.2 MB/s,125 MB 约 2 分钟):

```bash
curl -sSL -m 600 -o ~/.cache/electron-v43.3.0-linux-x64.zip \
  https://npmmirror.com/mirrors/electron/v43.3.0/electron-v43.3.0-linux-x64.zip

cd dsh-plugin-desktop/node_modules/electron
rm -rf dist && mkdir dist && cd dist
unzip -q ~/.cache/electron-v43.3.0-linux-x64.zip
```

解压后目录结构:
```
chrome_100_percent.pak  chrome-sandbox   icudtl.dat     libEGL.so   ...
chrome_200_percent.pak  electron         LICENSE        libffmpeg.so
chrome_crashpad_handler  resources        LICENSES.chromium.html  libGLESv2.so
```

**Step 5 — 修 path.txt trailing newline**

```bash
cd dsh-plugin-desktop/node_modules/electron
printf 'electron' > path.txt     # 注意: 不能 echo >,会带 \n
```

如果不修,`require('electron')` 走 index.js 时:
```js
executablePath = fs.readFileSync(pathFile, 'utf-8');   // "electron\n"
fullPath = path.join(__dirname, 'dist', executablePath); // dist/electron\n
fs.existsSync(fullPath);  // false → 触发重新下载
```


**Step 6 — 验证路径解析**

```bash
cd dsh-plugin-desktop
node -e "console.log(require('electron'))"
# 输出: /home/.../electron/dist/electron
```

v43 内嵌 Node 23.x,导出 `findPackageJSON`(Node 23+ 的 API)。

**Step 7 — 第一次 spawn Electron → 报 findPackageJSON 错?**

最初只解压了 v33(临时用),报:
```
SyntaxError: The requested module 'node:module' does not provide an export named 'findPackageJSON'
  at ModuleJob._instantiate (...)
  at async loadApplicationPackage (default_app.asar/main.js:129:9)
```

`package-overlay-Bh02i6tG.js` 是 tsdown 编译产物,使用了 Node 23+ 的
`findPackageJSON`。v33 内嵌 Node 22.16 没有这个 export。
**结论: 必须用 v43+(Node 23+)**,不能用 v33(虽然能下载下来但跑不起来)。


**Step 8 — 准备 desktop profile 目录**

`bin.js` 启动 main.js 后,会在 `~/.dsh/profiles/<name>/` 找 profile。
默认 profile 名是 `desktop`,首次启动时由 `createDesktopWebProfile()`
用 `dsh-app-boot` 内置 web template 自动初始化。

手动建空目录,让 Electron 启动时能填:

```bash
mkdir -p ~/.dsh/profiles/desktop
```

> 注意: 早期 sandbox=workspace-write 时,`.dsh/profiles/` 是只读的,
> `mkdir` 会 EROFS。后来切到 `danger-full-access`,写权限正常。

**Step 9 — 实际启动(后台 detach)```bash cd dsh-plugin-desktop setsid nohup node lib/bin.js > /tmp/dsh-desktop.log 2>&1 < /dev/null & disown ```**关键**:`setsid + disown` 把 Electron 主进程从 sandbox bash 树分离,
否则 sandbox 在我退出时会把 node + electron 全家 kill 掉。
启动后约 5 秒,主进程稳定下来。


**Step 10 — 验证进程树、生命周期、Cordis Host**

```bash
# 主进程活着
ps -p <main_pid> -o etime,stat,rss   # etime=01:40, stat=Sl, rss=227MB

# 完整 Electron 进程树
pstree -p <main_pid>
# electron─┬─zygote─┬─renderer (BrowserWindow 的渲染进程)
#          │        └─{19 threads}
#          ├─GPU (ozone-platform=x11)
#          ├─crashpad handler
#          └─utility network

# lifecycle-events/startup.jsonl 显示了 5 个阶段都完成:
grep startup.stage ~/.config/DSH\ Desktop/lifecycle-events/startup.jsonl
# electron-ready       (464ms) — Electron app.whenReady()
# shell-environment    (465ms) — 环境白名单恢复
# runtime-bootstrap    (497ms) — desktop runtime 初始化
# profile-selection    (507ms) — 选 profile
# profile-composition  (508ms) — 拼装 web profile(此处不前进,但不报错)
```

**Step 11 — 确认 Cordis Host LISTEN**

虽然 sandbox 看不到 9222 端口(网络 namespace 问题),
但**从 Electron 主进程的 /proc/<pid>/net/tcp 能看到 `0x0D16`** = 3350 LISTEN,
这正是 desktop 自己起的 Cordis Host loopback。

curl 3350 收到 `connection reset`(需要 token),证实它在握手但不接受未授权,
属于预期行为。


**Step 12 — 加 Chrome DevTools Protocol 集成(可选,便于 MCP/调试)**

修改 `dsh-plugin-desktop/lib/bin.js` 的 launchElectron,
加 `ELECTRON_REMOTE_DEBUGGING` 环境变量门控:

```js
if (process.env.ELECTRON_REMOTE_DEBUGGING === '1') {
  const cdpPort = process.env.ELECTRON_REMOTE_DEBUGGING_PORT || '9222';
  const cdpHost = process.env.ELECTRON_REMOTE_DEBUGGING_HOST || '127.0.0.1';
  args.push(`--remote-debugging-port=${cdpPort}`);
  args.push(`--remote-debugging-address=${cdpHost}`);
  args.push('--remote-allow-origins=*');
}
```

对应修改 `src/bin.ts` 源文件(可提交,见 §9)。

重启验证:

```bash
ELECTRON_REMOTE_DEBUGGING=1 ELECTRON_REMOTE_DEBUGGING_PORT=9222 \
  setsid nohup node lib/bin.js > /tmp/dsh.log 2>&1 < /dev/null &

# stderr 输出
dsh-plugin-desktop: Chrome DevTools Protocol listening on http://127.0.0.1:9222
DevTools listening on ws://127.0.0.1:9222/devtools/browser/<uuid>
```

curl 9222 返回:
```json
{ "Browser": "Chrome/150.0.7871.212",
  "User-Agent": "... DSHDesktop/0.0 ... Electron/43.3.0 ..."
}
```

确认是 Electron v43,不是系统 google-chrome。


**Step 13 — 让 chrome-devtools-mcp attach 到 DSH Desktop**

`chrome-devtools-mcp@1.9.0` 默认行为是自启 Chrome,不连外部 CDP。
要让 MCP attach 已启的 Electron,需要用 daemon 模式:

```bash
# 1. 先 stop harness 自启的默认 MCP daemon(它占用 chrome-profile user-data-dir)
/path/to/chrome-devtools-mcp/build/src/bin/chrome-devtools.js stop

# 2. 重启 daemon 并指明要 attach 的 CDP endpoint
setsid nohup \
  /path/to/chrome-devtools-mcp/build/src/bin/chrome-devtools.js \
    start --browserUrl=http://127.0.0.1:9222 \
  > /tmp/cdp-mcp.log 2>&1 < /dev/null &

# 3. 验证
chrome-devtools status
# chrome-devtools-mcp daemon is running.
# pid=... socket=/run/user/1000/chrome-devtools-mcp/server.sock
# args=[..., "--browser-url=http://127.0.0.1:9222", ...]
```

之后 `mcp__chrome-devtools__list_pages` / `take_snapshot` 等 MCP 工具
就能直接操作 DSH Desktop 的 BrowserWindow 了。

> **注意**: 中兴云桌面的 GUI 我无法直接看到(X server 在用户那边),
> 所以"窗口是否真出现"需要你在屏幕上确认。
> 但从进程树 / lifecycle events / Cordis Host / CDP / GPU 全部正常来看,
> 启动链路是通的。


### 6.3 进程拓扑(实测)

```
setsid nohup node lib/bin.js  (pid 2258408, launcher)
  └─ electron .../lib/main.js  (pid 2258438, 主进程, 227 MB RSS, 38 threads)
       ├─ electron --type=zygote --no-zygote-sandbox  (pid 2258451)
       │   ├─ electron --type=zygote                    (pid 2258452)
       │   └─ electron --type=renderer  ← BrowserWindow 内容
       │       └─ 13 个 web worker thread (parsing WebContents 沙箱)
       ├─ electron --type=gpu-process --ozone-platform=x11  (pid 2258639)
       │   └─ 19 个 raster thread
       ├─ electron --type=utility --utility-sub-type=network.mojom.NetworkService
       └─ chrome_crashpad_handler --database=$XDG_CONFIG_HOME/DSH Desktop/Crashpad
          --annotation=_productName=DSH Desktop --annotation=platform=linux
          --annotation=ver=43.3.0
```

### 6.4 运行时数据目录

| 路径 | 作用 | 自动创建? |
|---|---|---|
| `~/.dsh/profiles/desktop/` | desktop profile 的 package.json / cordis.yml / cordis.patch.yml | ✓ 首次启动 |
| `~/.dsh/storages/` | DSH 用户级 storages(context-manager / workspace / session_projcache) | 已存在 |
| `~/.config/DSH Desktop/` | Electron user-data-dir(Cache, Crashpad, Local Storage, blob_storage …) | ✓ 首次启动 |
| `~/.config/DSH Desktop/lifecycle-events/startup.jsonl` | 启动阶段进度 | ✓ 写入 |
| `~/.config/DSH Desktop/logs/dsh-YYYY-MM-DD.log` | 应用日志 | ✓ 写入 |
| `~/.config/DSH Desktop/Crashpad/` | 崩溃报告 | ✓ 创建 |
| `~/.config/DSH Desktop/devtoolsActivePort` | CDP 端口记录(开 ELECTRON_REMOTE_DEBUGGING=1 后) | ✓ 写入 |

### 6.5 dsh-web vs DSH Desktop 数据共享

| 数据层 | 路径 | web | desktop |
|---|---|---|---|
| DSH 用户级 storages | `~/.dsh/storages/` | ✅ | ✅ 共享 |
| Profile 内部 | `~/.dsh/profiles/<name>/...` | web 的 | desktop 的(独立) |
| Electron User Data | `~/.config/DSH Desktop/` | ❌ | ✅ 桌面独占 |

**会话列表存在 profile-local IndexedDB,所以 desktop 默认看不到 web 的会话历史。**
除非手动同步或重装 desktop profile 的 user-installed plugins。


### 6.6 小结:从干净环境到 DSH Desktop 完整运行

整个过程可归纳为 **7 个关键决策**:

| # | 决策 | 为什么 |
|---|---|---|
| 1 | 用 v43 Electron,不用 v33 | lib/main.js 用 Node 23+ 的 findPackageJSON,v33 内嵌 Node 22.16 没这个 export |
| 2 | 从 npmmirror 镜像拉 binary | 走代理稳定,~1.2 MB/s,2 分钟 |
| 3 | `printf 'electron' > path.txt`,不用 echo | 避免 trailing newline 触发重新下载 |
| 4 | `setsid + nohup + &` 后台启动 | 让 Electron 进程脱离 sandbox bash 树,不被 SIGKILL |
| 5 | 用 `danger-full-access` 权限跑 | 早期 `workspace-write` 下 `.dsh/profiles/` 只读,无法创建 desktop profile |
| 6 | 默认不开 CDP | 默认远程调试端口开在桌面应用上是反直觉的,需要显式 `ELECTRON_REMOTE_DEBUGGING=1` |
| 7 | 用 `chrome-devtools start --browserUrl=...` 让 MCP attach | chrome-devtools-mcp 默认自启 Chrome,需要显式指定 CDP endpoint |

成功路径总结成一句命令(假设 binary 已经在 dist 里):

```bash
mkdir -p ~/.dsh/profiles/desktop
cd dsh-plugin-desktop
setsid nohup node lib/bin.js > /tmp/dsh-desktop.log 2>&1 < /dev/null & disown
```

5 秒后,DSH Desktop 完整 Electron 进程树就起来了。

## 7. 已知问题 & 解决

### 7.1 Electron 二进制下不来

`yarn install` 时 electron postinstall 受 sandbox 网络限制 / 代理认证失败 → 二进制 dist 缺失。
修法 A: 直接下载并解压:

```bash
mkdir -p node_modules/electron/dist
cd node_modules/electron/dist
curl -sSL -o /tmp/electron.zip \
  https://npmmirror.com/mirrors/electron/v43.3.0/electron-v43.3.0-linux-x64.zip
unzip /tmp/electron.zip
cd ..
printf 'electron' > path.txt          # 关键: 不要 echo >,会带换行
```

### 7.2 path.txt trailing newline

`echo > path.txt` 写入带 `\n`,`fs.existsSync('electron\n')` false → 触发重新下载循环。
永远用 `printf 'electron' > path.txt`。

### 7.3 v33 vs v43

编译后的 `lib/main.js` 用了 `findPackageJSON`(Node 23+ API)。
Electron 33 内嵌 Node 22.16,没有这个 export。
**必须用 v43+(Node 23+)**。

### 7.4 Chrome DevTools Protocol 集成(本次新增)

修改文件: `dsh-plugin-desktop/src/bin.ts`(launchElectron 内追加):

```ts
if (process.env.ELECTRON_REMOTE_DEBUGGING === '1') {
  const cdpPort = process.env.ELECTRON_REMOTE_DEBUGGING_PORT || '9222'
  const cdpHost = process.env.ELECTRON_REMOTE_DEBUGGING_HOST || '127.0.0.1'
  args.push(`--remote-debugging-port=${cdpPort}`)
  args.push(`--remote-debugging-address=${cdpHost}`)
  args.push('--remote-allow-origins=*')
}
```

然后:

```bash
# 启桌面
ELECTRON_REMOTE_DEBUGGING=1 node dsh-plugin-desktop/lib/bin.js

# (另起终端) 让 chrome-devtools-mcp attach 上去
chrome-devtools start --browserUrl=http://127.0.0.1:9222
```

`chrome-devtools` CLI 在 npm 包 `chrome-devtools-mcp@1.9.0` 内,
npx 缓存路径:`~/.npm/_npx/<hash>/node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools.js`。

### 7.5 容器 Linux 桌面体验限制(官方明确)

- **只支持 `compatibility` 模式**(普通原生 frame),不支持 `extended` / `advanced`
- **tray 终端禁用**(`disabled: process.platform === 'linux'`)
- **材质强制 off**(`material !== "off"` 抛错)
- **自动更新检查跳过**(`Development, unpackaged, and Linux launches do not download an installer`)
- **XDG Desktop Portal 缺失**:`dialog.showOpenDialog` 退化但不影响主流程

## 8. 验证清单

```bash
# 1. launcher 本身
node dsh-plugin-desktop/lib/bin.js --version
# 应输出: 2.0.14

# 2. electron 二进制
node_modules/electron/dist/electron --version
# 应输出: v43.3.0

# 3. 桌面进程是否完整
ps -ef | grep -E "electron.*lib/main"
# 应看到: 主进程 + zygote + renderer + GPU + crashpad

# 4. Cordis Host 端口
cat /proc/<main_pid>/net/tcp | awk '$4=="0A" && $2 ~ /:0D16/'
# 应看到: 0100007F:0D16 LISTEN (3350)

# 5. 启动阶段
cat ~/.config/DSH\ Desktop/lifecycle-events/startup.jsonl | tail -1
# 应有 startup.stage.completed / profile-composition 等条目

# 6. CDP(若开了 ELECTRON_REMOTE_DEBUGGING=1)
curl -s http://127.0.0.1:9222/json/version | grep -oE 'DSHDesktop|Electron/[0-9.]+'
# 应输出: DSHDesktop / Electron/43.3.0
```

## 9. 提交与回滚

当前未提交但本地修改:

```
M dsh-plugin-desktop/src/bin.ts
```

提交命令:

```bash
git add dsh-plugin-desktop/src/bin.ts
git commit -m "feat(desktop): gate Chrome DevTools Protocol behind ELECTRON_REMOTE_DEBUGGING env"
```

回滚:

```bash
git checkout dsh-plugin-desktop/src/bin.ts
```

`lib/bin.js` 是编译产物,被 `.gitignore`(`/lib/`)忽略,下次 `yarn build` 会被 `src/bin.ts` 重建。

## 10. 参考链接

- 项目仓库: <https://github.com/anywhere-labs/deepseek-harness-desktop>
- 上游 DSH Web: <https://github.com/deepseek-ai/deepseek-harness>
- Electron v43 发布说明: <https://www.electronjs.org/blog>
- Cordis 框架: <https://github.com/cordiverse/cordis>
- chrome-devtools-mcp: <https://github.com/ChromeDevTools/chrome-devtools-mcp>

---

文档版本: 2026-09-23
作者: DSH Desktop 启动调试记录(在 NewStartOS / Node 24 / Yarn 4.18 / Electron 43.3 / DSH 0.1.5-rc.1 环境实测)