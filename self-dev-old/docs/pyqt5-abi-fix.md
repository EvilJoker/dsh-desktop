---
date: 2026-06-18
status: verified
target: NewStartOS V4.4.2-ZTE (RHEL8-based) + Python 3.6.8 + PyQt5 中文输入法兼容
---

# PyQt5 ABI 不匹配系统 Qt 导致中文输入法失效的修复

## 1. 现象

PyQt5 5.12.x / 5.13.x / 5.15.x 任何 wheel 安装后，PyQt5 panel 内的 `QLineEdit`
都出现以下问题：

- 字母能正常输入
- 切换到中文（搜狗/fcitx）输入拼音，候选框出现，但按数字或空格选词后**汉字不上屏**
- 点击 panel 任意位置，输入法图标**自动跳回英文**
- v2 单窗口版与 v3 Edge Dock（双窗口）版**现象完全一致**，与代码重构无关
- PyQt5.QtWidgets 进程 `qt.qpa.inputmethod` debug 日志中，preedit 字符串能拿到，
  但 commit string 永远是空

## 2. 根因：wheel 里的 Qt 运行时与系统 Qt ABI 不匹配

### 2.1 系统 Qt（用于 fcitx/ibus 输入法插件）

```
/lib64/libQt5Core.so.5     -> libQt5Core.so.5.12.5
/lib64/libQt5Gui.so.5      -> libQt5Gui.so.5.12.5
/lib64/libQt5Widgets.so.5  -> libQt5Widgets.so.5.12.5
```

`/usr/lib64/qt5/plugins/platforminputcontexts/libfcitxplatforminputcontextplugin.so`
在编译时链接到 `libQt5Gui.so.5`，需要的 ABI 段：

```
readelf -V /lib64/libQt5Gui.so.5.12.5 | grep -E 'Qt_5'
  Qt_5                              (基础段，PyQt5 wheel 都满足)
  Qt_5.12                           ← fcitx-qt5 编译时需要的段
  Qt_5.12.5_PRIVATE_API             ← 关键！私有 API 段
```

`Qt_5.12.5_PRIVATE_API` 是 system Qt 5.12.5 暴露的私有符号版本段，
**只有同版本系统 Qt 库才能满足**。

### 2.2 PyQt5 wheel 自带的 Qt 运行时

```
PyQt5-5.13.1-5.13.1-cp36-cp36m-manylinux1_x86_64.whl
PyQt5-5.15.6-cp36-abi3-manylinux1_x86_64.whl
PyQt5-Qt5-5.15.x-cp36-abi3-manylinux1_x86_64.whl
```

wheel 里的 QtCore/QtGui/QtWidgets 都是 PyQt 项目组编译的，
使用自带的 Qt 5.12.10 / 5.15.x 运行时（libQt5Core.so 一起塞在 wheel 里）。

**关键事实**：这些 wheel 自带的 `libQt5Gui.so` **没有 `Qt_5.12.5_PRIVATE_API` 段**。

```bash
# 把 wheel 解压出来看
mkdir /tmp/wheel-check && cd /tmp/wheel-check
unzip ~/.cache/pip/wheels/.../PyQt5-5.15.6-cp36-abi3-manylinux1_x86_64.whl
ldd PyQt5/Qt/lib/libQt5Gui.so.5.12.10  # 看依赖
readelf -V PyQt5/Qt/lib/libQt5Gui.so.5.12.10 | grep Qt_5  # 看版本段
# 输出只有 Qt_5 + Qt_5.12（没有 Qt_5.12.5_PRIVATE_API）
```

### 2.3 冲突如何表现

PyQt5 wheel 里的 `QtWidgets.cpython-36m-x86_64-linux-gnu.so` 通过
`dlopen("libQt5Gui.so.5")` 动态加载时，**会优先找 wheel 内的 libQt5Gui**，
而不是系统 `/lib64/libQt5Gui.so.5`。

结果：

| 模块 | 实际加载的 libQt5Gui |
| --- | --- |
| PyQt5 binding | wheel 内的 5.12.10（无 `Qt_5.12.5_PRIVATE_API` 段） |
| fcitx-qt5 input context plugin | **系统 5.12.5**（需要 `Qt_5.12.5_PRIVATE_API` 段） |

跨 ABI 调用导致 QInputContext 内部状态错乱，commit string 永远为 null，
输入法状态无法正确同步。

## 3. 失败的尝试

| 方案 | 操作 | 失败原因 |
| --- | --- | --- |
| A. 装 ibus | `dnf install ibus-qt5` | NewStartOS EL8 仓库没有 `ibus-qt5` 包 |
| B. PyQt5-Qt5 5.12.5 wheel | `pip install PyQt5-Qt5==5.12.5` | PyPI 上没有 5.12.5 wheel，只有 5.15.x |
| C. 重新编译 fcitx-qt5 | 拉 fcitx-qt5 源码 build | 需要完整的 Qt5 + Plasma 依赖，编译耗时 1h+，且每次 Qt 升级都要重建 |
| D. 用更老的 wheel (5.12.1 / 5.12.3) | pip 找 abi tag 匹配的 | 同样 ABI 不匹配，私有段缺失 |
| E. 改用 XIM（不走 Qt platform input context） | `QT_IM_MODULE=xim` | 新版 fcitx 强烈推荐走 Qt 平台插件，XIM 兼容性差且已不维护 |

## 4. 唯一可行：PyQt5 源码编译，链接到系统 Qt 5.12.5

### 4.1 思路

让 PyQt5 binding 的 `.so` 在编译时**链接到系统的 `libQt5Gui.so.5`（5.12.5）**，
而不是 wheel 内的 5.12.10。这样 PyQt5 和 fcitx-qt5 plugin 都用同一份系统 Qt，
ABI 完全一致，`Qt_5.12.5_PRIVATE_API` 段都能满足。

### 4.2 环境准备

```bash
# 编译工具链
sudo dnf install -y gcc-c++ python36-devel qt5-qtbase-devel qt5-qttools-devel

# 编译工具
/usr/bin/python3 -m pip install --user sip PyQt-builder

# qmake 软链（sipbuild 隔离环境不继承 PATH，需要显式 qmake）
sudo ln -sf /usr/bin/qmake-qt5 /usr/local/bin/qmake

# 卸掉所有 wheel 版 PyQt5（避免干扰）
/usr/bin/python3 -m pip uninstall -y PyQt5 PyQt5-sip PyQt5-Qt5
rm -rf ~/.local/lib/python3.6/site-packages/PyQt5*
```

### 4.3 编译（关键命令）

```bash
QMAKE=/usr/bin/qmake-qt5 \
/usr/bin/python3 -m pip install --user \
    --no-build-isolation \
    -v \
    --no-binary PyQt5 \
    PyQt5==5.15.6
```

要点：
- **`--no-build-isolation`**：sipbuild 默认会建一个干净 venv，里面没有 PyQt-builder，
  会失败。关掉后用当前 site-packages 里的 PyQt-builder。
- **`--no-binary PyQt5`**：强制走源码，PyPI 没有 5.15.6 的 cp36 wheel（5.15.x 都是
  `cp36-abi3` 的 manylinux1 wheel），但用 wheel 也行不通（ABI 问题），
  所以强制源码。
- **`QMAKE=...`**：pip 不支持 `--config-setting`（pip 21.3.1），但 sipbuild 读
  `QMAKE` 环境变量。

### 4.4 编译时间

实测 43 分钟（系统 8C16T，全部打满，CPU 持续 800%+）。

### 4.5 ABI 验证

编译完**必须**验证 .so 链接：

```bash
# 应该看到 /lib64/libQt5Gui.so.5（系统 5.12.5），不是 wheel 的 PyQt5/Qt/lib/...
ldd ~/.local/lib/python3.6/site-packages/PyQt5/QtWidgets.abi3.so | grep Qt5

# 版本段必须匹配
readelf -V ~/.local/lib/python3.6/site-packages/PyQt5/QtWidgets.abi3.so | grep Qt_5
# 只依赖 Qt_5（不需要 Qt_5.12 私有段，因为 PyQt5 不调私有 API）

# 运行时探测的版本必须 = 系统 Qt 版本
/usr/bin/python3 -c "from PyQt5 import QtCore; print(QtCore.QT_VERSION_STR)"
# 必须输出 5.12.5
```

### 4.6 补 platform plugins

源码编译的 PyQt5 wheel **不带** platform plugins（不像官方 PyQt5 wheel
会把 `libqxcb.so`、`libfcitxplatforminputcontextplugin.so` 一起塞进
`PyQt5/Qt5/plugins/`）。必须手动从系统拷贝：

```bash
cp -r /usr/lib64/qt5/plugins/platforms \
      ~/.local/lib/python3.6/site-packages/PyQt5/Qt5/plugins/
cp -r /usr/lib64/qt5/plugins/platforminputcontexts \
      ~/.local/lib/python3.6/site-packages/PyQt5/Qt5/plugins/
```

少了 platform plugin → `QApplication()` 直接 SIGABRT（exit 134）。
少了 platform input context plugin → 中文输入法不工作。

### 4.7 Python 验证最小冒烟

```bash
DISPLAY=:0 /usr/bin/python3 -c "
from PyQt5 import QtCore, QtGui, QtWidgets
import sys
print('QT_VERSION_STR:', QtCore.QT_VERSION_STR)  # 必须是 5.12.5
print('PYQT_VERSION_STR:', QtCore.PYQT_VERSION_STR)  # 必须是 5.15.6
app = QtWidgets.QApplication(sys.argv)
print('platform:', app.platformName())  # 必须是 xcb
w = QtWidgets.QLineEdit()
w.setWindowTitle('PyQt5 ABI test')
w.show()
QtCore.QTimer.singleShot(500, app.quit)
app.exec_()
"
```

期望输出：
```
QT_VERSION_STR: 5.12.5
PYQT_VERSION_STR: 5.15.6
platform: xcb
```

## 5. PyInstaller 打包

```bash
cd desk-assistant
bash script/build.sh
```

关键变化：
- 旧的 wheel 版打包：panel 71M（含 wheel 内置的 Qt 5.12.10 运行时）
- 新源码版打包：panel 55M（不带 Qt 运行时，运行时 link 系统 5.12.5）

部署后通过 `desk-assistant_run.sh start` 启动，立即可用中文输入。

## 6. 回滚方案

源码编译版完整 rollback 脚本在 `/tmp/pyqt5-rollback/rollback.sh`：

```bash
bash /tmp/pyqt5-rollback/rollback.sh
```

它会：
1. 停 panel / server
2. 卸掉 pip 装的 PyQt5（源码 + 备份的 wheel 都清掉）
3. 从 `/tmp/pyqt5-rollback/PyQt5-wheel-3.6` 还原 site-packages
4. 还原 PyInstaller 打包出来的 panel/server 二进制
5. 验证

## 7. 经验教训

- **PyQt5 wheel ≠ ABI 兼容系统 Qt**：PyQt5 官方 wheel 在 Windows/macOS 上工作良好，
  因为这些平台 Qt 运行时也是 wheel 自带、自洽的。Linux 上若系统装了 Qt（如
  NewStartOS），并且装了 fcitx-qt5 / ibus-qt5 这类系统级输入法插件，
  **wheel 自带的 Qt 版本和系统 Qt 必须 minor 版本完全一致**，否则 ABI 段缺失。
- **检查 ABI 段用 `readelf -V`**：`ldd` 只看依赖，不看符号版本段。私有不一致只有
  `readelf -V` 能看到。
- **source compile 是 Linux PyQt5 + 系统 IME 的终极方案**：不到万不得已别走，
  一次编译 40+ 分钟，且每次 `qt5-qtbase` 升级都要重建。
- **distro 仓库里 PyQt5 包通常不可用**：NewStartOS 的 dnf 仓库有 `python3-PyQt5`，
  但版本老（5.12.x），不一定满足代码里的 API。
- **`pip install --no-build-isolation` 是关键**：sipbuild 默认 venv 隔离，
  找不到 PyQt-builder 必须显式关掉。