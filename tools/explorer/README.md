# 天梯对局研究 GUI

当前情景：按你指定的 30% 估计 78 场提前结束录像的胜率。
整体估计为 49.2%，与已知战报胜率、逐场未知结果分别展示。
分组/筛选使用同一 30% 分配假设；旧的未调查未知录像不参与该估计。

在开发工作树双击根目录 `Start-Explorer.cmd`，或运行：

```powershell
python tools/explorer/server.py --open-browser
```

访问 http://127.0.0.1:8765/ 。默认端口被占用时，可加 `--port 8766`。
关闭运行窗口或 Ctrl+C 停止服务。服务只绑定 127.0.0.1，没有上传和修改录像功能。
数据服务仅使用 Python 标准库，前端无 npm 安装、外部 CDN 或网络依赖。

默认地图分析；左侧添加多个分组标签，并叠加多值筛选。窄屏时先点“展开标签与筛选”。
点击分组名称查看组内所有对局，再点击时间打开单场详情。

数据源是 `DOCS/status/evidence/2026-09-30-replay-audit/` 的固定快照：
CSV 是提取器的内部交换格式，服务负责规范化为 JSON；浏览器负责探索式分组和统计。
新增录像不会自动进入这份快照。更新数据需要重新运行提取器，保留新快照并修改服务路径。
没有实现直接播放录像；详情提供原始文件路径和下载，供当前兼容游戏客户端打开。

输入区分 None 与 0、保留大整数战斗 ID 为字符串；队友构成排除本人。
战报缺失时仍可用文件头车型在已验证的当前客户端类别映射中分组，但标记尚无战报复核。
出生方暂用队伍 1/2，与天梯模式配置点关联，不擅自标记南北。

分析口径见 [方法说明](../../DOCS/facts/analysis-method.md)。
验证：

```powershell
python -m unittest discover -s tools/explorer -p test_*.py
node --check tools/explorer/app.js
```

缺失机制调查复现：

```powershell
python tools/replay_analysis/missing_results.py --battles DOCS/status/evidence/2026-09-30-replay-audit/battles.csv --output DOCS/status/evidence/2026-09-30-replay-audit/missing-results.json
python tools/replay_analysis/cache_audit.py --battles DOCS/status/evidence/2026-09-30-replay-audit/battles.csv --output DOCS/status/evidence/2026-09-30-replay-audit/cache-audit.json
```

`missing_results.py` 需要 cryptography；`cache_audit.py` 读取当前本机战报缓存，缓存会随游戏变化。
两者均只读原文件。没有为了调查安装游戏模组或改动游戏设置。
