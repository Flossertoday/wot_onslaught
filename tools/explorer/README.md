# 天梯对局研究 GUI

历史情景：按你指定的 30% 估计此前已调查的 78 场提前结束录像的胜率。
该批原始样本整体估计为 49.2%；新录像进入后，当前数值随筛选范围变化。
分组/筛选使用同一 30% 分配假设；新增及其他未调查未知录像不参与该估计。

在开发工作树双击根目录 `Start-Explorer.cmd`，或运行：

```powershell
python tools/explorer/server.py --open-browser
```

访问 http://127.0.0.1:8765/ 。默认端口被占用时，可加 `--port 8766`。
关闭运行窗口或 Ctrl+C 停止服务。服务只绑定 127.0.0.1，没有上传和修改录像的 HTTP 接口。
每次启动先从 `C:\Games\World_of_Tanks_CN\replays` 同步天梯录像，再重新提取分析数据。
页面顶部显示同步数量及刷新结果。首次同步较多录像时，请等待启动窗口输出访问地址。
启动提取器需要现有 Python 环境中的 scipy 和本机游戏资源；前端无 npm 安装、外部 CDN 或网络依赖。

同步仅复制源目录顶层的 `.wotreplay`，按文件头 `gameplayID=comp7`、`battleType=43` 筛选，
存入当前工作树的 `replays/<地图>/`。已有同名同内容文件跳过；同名不同内容报告冲突，
不覆盖。源录像不删除、不修改，`ReplayCache.db` 不同步。临时录像 `temp.wotreplay`、
最后修改不足 10 秒或复制过程中变化的文件留待下次启动；这不是常驻目录监控。

也可只同步文件（不启动 GUI、不刷新分析）：

```powershell
python tools/replay_analysis/sync_replays.py
```

脚本支持 `--source <源目录>`、`--destination <目标目录>`，默认目标由脚本所在工作树决定，
与当前终端目录无关。GUI 支持 `--replay-source <源目录>`、`--game <游戏安装目录>`；
加 `--no-sync` 会跳过复制，但仍重新分析本地录像。

默认按地图比较**积分变化**；顶部可切换“积分变化 / 声望 / 胜率”三个并列的结果视图。
结果视图决定主指标、分组表、升降序排序、相对其余对局的差值和最小有值场数口径。
积分与声望视图包含均值、中位数、中间 50% 对局、胜局/负局拆分；积分另有已记录净变化。
切换结果保留当前分组和筛选。保存视图也保存结果指标，旧版视图恢复为胜率。
左侧添加多个分组标签，并叠加多值筛选。窄屏时先点“展开标签与筛选”。
日期筛选支持“今日、昨日、前日、三日、七日”快捷选项，按当前 UTC+08 自然日计算；
“三日”和“七日”包含今日。点击立即更新起止日期和结果，仍可手动调整或保存日期范围。
点击分组名称查看组内所有对局，再点击时间打开单场详情。

声望与积分已接入：总览及分组显示本人平均声望、场均/合计积分变化及有值场数，
可按本人声望区间、积分变化区间分组或筛选。对局列表直接显示声望与加减分。
详情可看本人战前/战后积分、双方 14 人的 19 项战后指标，按声望排序并高亮本人。
点击“更多战报”展开其余指标，窄屏可在表格内横向滚动。
声望原值可能超过 200；精确积分变化仅本人可见。缺失不算 0，不套用胜率情景补估积分。
实测及字段覆盖见 [声望与全场战报](../../DOCS/status/2026-09-30-prestige-and-scoreboard.md)。

启动时的分析截止时间取当前 UTC+08 时间，默认研究最近七天；其他日期可通过筛选查看。
CSV 是提取器的内部交换格式，服务负责规范化为 JSON；浏览器负责探索式分组和统计。
临时提取输出放在被 Git 忽略的 `.drafts/explorer/`，读取完成后清理。
`DOCS/status/evidence/2026-09-30-replay-audit/` 历史证据保持原样。
若提取失败，GUI 明确提示正在显示历史快照，新录像尚未纳入；具体错误见启动窗口。
源目录不可用时仍会尝试分析已归档录像。新复制的录像属于本地数据，不由同步脚本自动提交 Git。
历史缺失机制调查仅复用于路径和 SHA-256 都匹配的录像；新录像缺少结果时保持“未知/未调查”，
不自动套用 30% 情景，也不在每次启动时重新解密整批录像。
没有实现直接播放录像；详情提供原始文件路径和下载，供当前兼容游戏客户端打开。

输入区分 None 与 0、保留大整数战斗 ID 为字符串；队友构成排除本人。
战报缺失时仍可用文件头车型在已验证的当前客户端类别映射中分组，但标记尚无战报复核。
出生方暂用队伍 1/2，与天梯模式配置点关联，不擅自标记南北。

分析口径见 [方法说明](../../DOCS/facts/analysis-method.md)。
验证：

```powershell
python -m unittest discover -s tools/explorer -p test_*.py
node --check tools/explorer/app.js
node tools/explorer/test_scenario.cjs
node tools/explorer/test_results.cjs
```

缺失机制调查复现：

```powershell
python tools/replay_analysis/missing_results.py --battles DOCS/status/evidence/2026-09-30-replay-audit/battles.csv --output DOCS/status/evidence/2026-09-30-replay-audit/missing-results.json
python tools/replay_analysis/cache_audit.py --battles DOCS/status/evidence/2026-09-30-replay-audit/battles.csv --output DOCS/status/evidence/2026-09-30-replay-audit/cache-audit.json
```

`missing_results.py` 需要 cryptography；`cache_audit.py` 读取当前本机战报缓存，缓存会随游戏变化。
两者均只读原文件。没有为了调查安装游戏模组或改动游戏设置。
