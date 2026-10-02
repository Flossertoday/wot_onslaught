# WoT 天梯对局分析器

World of Tanks Onslaught replay explorer: a local browser UI for comparing maps,
vehicles, lobby composition, rating changes, prestige and win rate.

中文界面，面向 Windows 上的《坦克世界》国服天梯玩家。
当前为源代码版本，需要 **Python 3.11 或更新版本**、现代浏览器，以及分析个人录像时使用的本机游戏资源。
普通 GUI 只使用 Python 标准库，无需 Anaconda、npm 或额外 Python 包。

## 开始使用

1. 从本项目 GitHub 页面的 **Code → Download ZIP** 下载并解压，或克隆项目。
   将项目放在你有写入权限的目录中。
2. 安装 [Python 3.11+](https://www.python.org/downloads/windows/)，确保 `py` 或 `python` 命令可用。
3. 双击 `Start-Explorer.cmd`。首次启动会用最多约 2 秒查找游戏安装目录。
   找到一个时按 Enter 接受；找到多个时输入编号选择，也可输入 `0` 手动填写目录。
   未找到时直接回退到手动输入；按 Enter 可先打开空页面。
   游戏目录必须包含 `res/packages/scripts.pkg`；路径中可以有空格和中文。
4. 设置保存在项目根目录的 `explorer.local.json`，后续启动自动复用。
   工具从该游戏目录的 `replays/` 复制已完成的天梯录像，再打开本地分析页面。
5. 首次没有录像时显示空页面；在游戏中启用录像保存，完成天梯对局后重新启动工具。
   关闭控制台或按 Ctrl+C 停止服务。

游戏源文件只读，已有同名不同内容录像不会被覆盖。项目自己的录像归档位于
`replays/<地图>/`，与本地设置、分析缓存一起被 Git 忽略。游戏资源和原始录像不随项目分发。

## 目录设置和命令行

复制 `explorer.example.json` 为 `explorer.local.json`，把示例目录改为你的实际目录。
`game` 是游戏安装目录；可选 `replay_source` 指向其他录像源目录。
JSON 路径推荐用 `/`；使用 `\` 时需要写成 `\\`。
相对路径以设置文件所在目录为基准。

也可以直接传参，以下路径仅为示例：

```powershell
python tools/explorer/server.py --game "D:/Games/World_of_Tanks" --open-browser
python tools/explorer/server.py --game "D:/Games/World_of_Tanks" --replay-source "D:/Saved Replays" --open-browser
python tools/explorer/server.py --no-sync --port 8766
```

参数也可传给 `Start-Explorer.cmd`。支持 `--config <设置文件>`；命令行参数优先于
`WOT_GAME_DIR` / `WOT_REPLAY_SOURCE` 环境变量，再优先于本地设置。
改变 `--game` 时默认录像源随新游戏目录变化；独立录像目录则使用 `--replay-source`。
程序只监听 `127.0.0.1`；控制台会显示实际访问地址。

自动查找仅在双击启动且尚未配置游戏目录时进行，检查 Windows 安装记录及本地固定磁盘上
少量常见位置，不递归扫描整盘。候选目录同时校验 `WorldOfTanks.exe` 和
`res/packages/scripts.pkg`；没有 `replays/` 目录也能完成设置。
已保存目录、环境变量及命令行参数优先于自动查找；单独配置的录像源目录会保留。

## 不安装游戏先试用

```powershell
python tools/explorer/server.py --demo --open-browser
```

演示模式显式标记为**历史演示**，使用 `DOCS/status/evidence/2026-09-30-replay-audit/`
中的历史研究数据，既不是你的对局，也不会同步游戏录像。
这些派生数据已移除玩家名和账号 ID，仍包含录像文件名、哈希、对局 ID、分段和表现指标。
原始录像未包含在仓库中，因此下载按钮只在文件确实存在时显示。
普通启动及提取失败均不会自动展示这批历史数据。

## 能力与限制

- 积分变化、声望、胜率三个结果视图；支持多标签分组、筛选、日期范围和单场战报。
- 精确积分变化只来自本人战报；缺失数据保留为未知，真实 0 不丢弃。
- 所有无最终战报对局使用明确标注的 **30% 胜率情景假设**，并不代表实际胜负。
- 日期按 UTC+08 解释。已验证国服天梯录像和匹配游戏资源；其他地区、版本和模式尚未验证。
- 游戏更新或旧录像格式不匹配可能导致解析失败。查看启动窗口的错误，不将失败当作胜负数据。
- 这是本地分析工具，未提供独立 EXE 或在线播放录像功能，也不是 Wargaming 官方产品。

详细操作见 [GUI 使用说明](tools/explorer/README.md)，数据口径见
[分析方法](DOCS/facts/analysis-method.md)。历史调查记录是开发证据，不是当前用户的分析结果。

## 可选研究工具与开发验证

仅做 GUI 分析无需安装下列依赖。完整统计报告、事件流调查和字节码证据采集使用可选研究依赖：

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-research.txt
.venv/Scripts/python -m unittest discover -s tools/explorer -p "test_*.py"
.venv/Scripts/python -m unittest discover -s tools/replay_analysis -p "test_*.py"
```

有 Node.js 时可执行前端验证（不需要 npm 安装）：

```powershell
node --check tools/explorer/app.js
node tools/explorer/test_scenario.cjs
node tools/explorer/test_results.cjs
node tools/explorer/test_entry_rank.cjs
```

更多命令见 [研究工具](tools/replay_analysis/README.md)。
报告问题时请提供 Python 版本、游戏地区/版本、操作步骤和去除个人路径的错误信息。
不要把原始录像、账号数据或本地设置附在公开 issue 中。

## License

[MIT](LICENSE)。格式研究的参考来源见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)。
