# pet-adapter-electron

petpal 一键唤醒 DSH 工作台的 **Electron 薄壳**。

> 目标：按下全局快捷键，直接打开已加载 DSH Web 的独立桌面包。DSH 本身是 Web 服务（默认 `127.0.0.1:3080`），Electron 只是"带壳浏览器 + 全局快捷键入口"。

## 已实现（Step 1）

- ✅ Electron 主进程 + BrowserWindow 加载 DSH URL（`http://127.0.0.1:3080`）
- ✅ **全局快捷键唤起/聚焦**：默认 `Ctrl+Alt+P`（Linux）/ `CmdOrCtrl+Shift+A`（macOS），可通过 `PETPAL_HOTKEY` 改
- ✅ 系统托盘常驻（可选，`PETPAL_TRAY=0` 关闭）
- ✅ 关窗隐藏到托盘（托盘模式）、点击托盘/快捷唤起聚焦
- ✅ 健康检查模式（`PETPAL_HEALTHCHECK=1`）验证"Electron 内嵌加载 DSH"是否成功

## 运行

```bash
# 默认（需 DISPLAY 环境，真实桌面）
npm start

# 受限/无 GPU 容器环境（虚拟显示、CI、docker）加这些开关：
DISPLAY=:0 \
PETPAL_NO_SANDBOX=1 \
PETPAL_SHM_FIX=1 \
npm start -- --disable-gpu
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `DSH_URL` | `http://127.0.0.1:3080` | DSH Web 地址 |
| `PETPAL_HOTKEY` | Linux `Ctrl+Alt+P` / 其他 `CmdOrCtrl+Shift+A` | 全局唤起快捷键 |
| `PETPAL_TRAY` | `1` | `0` 关闭托盘（关窗即退出） |
| `PETPAL_NO_SANDBOX` | 空 | `1` 加 `--no-sandbox`（受限容器/root） |
| `PETPAL_SHM_FIX` | 空 | `1` 加 `--disable-dev-shm-usage`（无 `/dev/shm` 环境） |
| `PETPAL_HEALTHCHECK` | 空 | `1` 加载完成后打印 url/title/body 并退出（验证用） |

## 兼容性（当前无 GPU/受限环境的踩坑记录）

在**无 GPU / 虚拟显示 / 无 `/dev/shm`** 的受限环境运行 Electron 需要：

1. **GPU 崩溃** → `--disable-gpu` 或 `app.disableHardwareAcceleration()`
2. **沙箱失败** → `--no-sandbox`（`PETPAL_NO_SANDBOX=1`）
3. **`/dev/shm` 不可写** → `--disable-dev-shm-usage`（`PETPAL_SHM_FIX=1`）

三者已在 `main.js` 中通过环境变量开关处理。**普通桌面环境（有 GPU + /dev/shm）不需要任何开关，直接 `npm start` 即可。**

## 待办 / 下一步

- [ ] **DSH 认证**：当前 DSH 返回 401，需要带 `dsh web` 打印的 token URL 或注入登录态，让"一键打开就是已认证工作台"
- [ ] 两层架构落地：把 `CONFIG` / 唤起逻辑抽到独立 `pet-core`，本包只做 `LauncherPort` 实现
- [ ] 自动起 DSH 服务（未运行则后台 `dsh web`）
- [ ] 打包分发（electron-builder）
