# Replay 标签与解析口径

后续更新：[78 场缺失原因与 GUI](../status/2026-09-30-missing-results-and-explorer.md)、
[探索与确认方法](analysis-method.md)。CSV 为中间数据，交互分析使用本地 GUI。

本文件记录 2026-09-30 对本项目录像与当前国服客户端的实测。录像版本为
`2.4.0.0`，文件头显示 `v.2.4.0.1 #949`。升级客户端或改变录像来源后重新验证。

## 数据来源

| 标签 | 来源与口径 |
| --- | --- |
| 地图 | 第一个 JSON 块的 `mapName`、`mapDisplayName`；保留模式变体 ID |
| 日期 | 第一个 JSON 块 `dateTime`；按 UTC+08 解释，与结果 `common.arenaCreateTime` 交叉检查；这是录像开始时刻，较 arena 创建通常晚约 10 秒，不冒充战斗计时开始 |
| 自己的车辆 | 头部 `playerVehicle` 与第二 JSON 块的最终车辆表交叉检查；车辆表按结果 `vehicles[*][*].accountDBID` 关联本人；文件名仅辅助 |
| 车辆类别 | 当前客户端 `scripts.pkg/scripts/item_defs/vehicles/<nation>/list.xml` 的 `tags`；不按名称猜测 |
| 队伍 | 有战报时按 accountDBID 关联本人并交叉检查 players、personal.avatar、vehicles 的 team；只有头部时用唯一匹配的玩家名找到 header.team，并明确来源 |
| 出生方 | 使用当前地图 `gameplayTypes/comp7/teamSpawnPoints/team1|team2`，保存队伍编号及配置坐标；不把普通模式出生点用于猛攻，也不将配置坐标冒充实际出生轨迹。当前先用 team1/team2，南北名称需单独核验 |
| 胜负 | `common.winnerTeam` 与本人 team 比较；0 为平局，1/2 为获胜队。身份、队伍、车辆、时间不一致则隔离。缺失不算负场 |
| 表现 | 结果车辆条目中的伤害、协助、击杀、生存时间、血量、格挡、占点、技能次数、猛攻声望等；保留原始指标，不定义统一的好/差阈值 |
| 分段 | `avatars[accountDBID].comp7Rank` 为 `(rank, divisionIndex, serialIndex)`；第三项不是积分。前两项通过该录像自身 `serverSettings.comp7_ranks_config.divisions` 映射 |
| 定级赛 | `comp7QualActive` 为真时，分段范围不作为已定级实力标签；单独标记 qualification |
| 本人积分 | `personal.avatar.comp7Rating` 是战前积分；战后值为 `max(0, comp7Rating + comp7RatingDelta)`。当前客户端战报 UI 的 prevRating/currentRating 代码直接证明 |
| 他人积分 | 当前战报提供他人的段位类别，不提供每人的精确积分；保留段位及对应区间，不用区间中点假装真实积分 |
| 组队 | 保存结果 players 的 prebattleID；是否属于某一组队关系还需要明确语义，暂不据此解释胜负 |

完整战报中，339/339 场本人的 comp7Rank 与战前积分分段吻合，与战后积分仅
251/339 吻合；本人的 personal.avatar 与 avatars 分段 339/339 一致。
这支持战报分段的战前口径。其他玩家分段采用同一字段和客户端展示方式，未用
当前账号查询结果倒填历史段位，也未逐人做独立视频核对。

## 已确认的陷阱

- 头部部分 `vehicles[*].vehicleType` 为空，`position=[-32768,-32768]` 为占位值。
- `ranked`、`prestigeLevel` 等名称相近字段不能替代猛攻 `comp7Rank`。
- 完整战报的精确积分在客户端定义中为 ACCOUNT_SELF；分段为 ACCOUNT_ALL。
- ReplayCache.db 是辅助缓存。此次虽能按 basename 和文件大小匹配全部录像，
  但没有 JSON 战报的 91 场在缓存中也全部为 `iIsWinner=-1`，无法补齐。
- 缓存有部分 GBK 字符串；审计只选择 ASCII 路径和数值列，不直接按 UTF-8 全表读取。
- 2026-09-18 22:02 的恩斯克 E 100 录像有第二 JSON 块，但本人在车辆结果中缺失，
  personal.avatar 身份不一致；缓存却显示胜利。必须隔离，不能盲信“存在第二块”或缓存。
- 回放记录缺少最终阶段时，不能从本人死亡、最后一帧优势、下场积分差等直接填入胜负。

## 数据与统计约束

- 窗口固定为 `[cutoff−7天, cutoff)`，旧录像保留，分析时过滤。
- 每场主表一行；参战者表一场 14 行。段位组合中的队友排除本人，只包括 6 人。
- 按文件 SHA-256 和有效战报 arenaUniqueID 去重，结果未知的录像仍进入缺失率分母。
- 原始输入只读；输出保留相对文件名、哈希、解析状态和字段来源。
- 已知胜率为 wins/(wins+losses+draws)，unknown 单独展示。
- 同时报告缺失敏感性上下界：wins/total 到 (wins+unknown)/total。
  这是缺失结果全部为负/胜时的确定性边界，不是置信区间。
- 地图表提供 Wilson 95% 区间、相对其余地图的单侧 Fisher 检验与 22 张地图 BH 校正。
  这些只用于探索；仍有连续作战相关性、缺失偏差、选车及分段混杂，不能视为最终因果结论。
- 地图×出生方、地图×头部车型仅做描述，不对所有组合穷举显著性；缺结果时头部车型仍待战报交叉验证。

当前证据：[可行性报告](../status/2026-09-30-analysis-feasibility.md)、
[字段审计](../status/evidence/2026-09-30-replay-audit/audit.json)、
[客户端字节码证据](../status/evidence/2026-09-30-replay-audit/client-bytecode.json)。
