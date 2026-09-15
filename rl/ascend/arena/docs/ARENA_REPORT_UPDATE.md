# Arena 在线现状报告交付

最新版本 2 已增加 [真实内容目录](https://arena-system-report.redstonemanliu.chatgpt.site/catalogue.html)，完整记录见 [真实内容阶段交付](ARENA_CATALOGUE_UPDATE.md)。下文保留版本 1 的实验与发布记录。

2026-09-08。报告位于 `reports/arena-status/`，独立 Sites 源仓库，只发布报告与合成实验结果，不推送父 Arena 工作树或 adapter。

## 内容

- 可点击的系统关系图：内容、主数据、编译、培育流程、考试、实况、策略编码、恢复、外部 adapter。
- 体力／资源、事件触发、训练试镜、卡牌物品、选择流程、恢复实况的实现摘要和当前边界。
- 两个真实基础卡示例：軽い足取り `p_card-01-act-1_002`、可愛い仕草 `p_card-02-act-0_009`。前者搭配アピールの基本 `p_card-00-act-0_001`。
- 参数切换、达标线选择、逐步结算时间线、当前 JSON 内容包导出和完整 HTML 下载。

主数据固定在 `gakumasu-diff@571dbb62601e78998cddeacdbce3ea1bc672d7fc`。
修改后的卡牌明确标注为自创／合成配置；原卡与初始条件分别标识。3 回合、倍率 ×1、初始资源与每回合显式结束均为受控实验，不是官方实况考试。

## 结果如何产生

`scripts/export_report_experiments.py` 通过内容编译入口生成定义，并执行当前 Arena 原生结算，输出 90 组センス和 45 组ロジック记录。
批处理不反复复制无须恢复的选择检查点；原生 step 与公共 ContentExam.act 基准逐帧相等。
两个原卡的直接导入与配置复刻也逐帧相等。网页只查找这 135 组精确运行记录，没有另写 JS 评分公式。
达标线仅比较最终得分；405 种导出配置通过 Schema，6 个边界包通过编译，两个默认达标线已对照实际执行。

基准：軽い足取り实验累计 66 分、体力 12；可愛い仕草实验累计 7 分、体力 30。
这些数值包含未用完行动窗时主动结束回合的 2 点体力回复，以及当前引擎的状态衰减设置。

## 验证

- Node 模型测试 4 项通过：原卡基准、全部可选组合、导出隔离、非法输入。
- 本报告 `npm run lint` 与静态构建通过；脚本语法经过 V8 检查。
- 首次本地预览根页与 HTML 返回 HTTP 200；本阶段未进行用户未要求的浏览器视觉／点击测试。
- 可选 WebMCP 的浏览器端注册与调用未验证，普通页面交互不依赖它。
- 独立 HTML 285549 字节；发布包只含报告 HTML、favicon 和 Sites manifest。
- HTML SHA256：`8a0c4fc5c2649ca26f3ada6be8967d793401c3358737e6beea1657703c00392d`。

## 发布记录

- Sites project：`appgprj_6a9f6efdfcc88191bf73c908ebaaefbe`。
- 版本 1，源提交 `feb65753861f0e7ab0a972eb32b456e3cccf11a4`。
- deployment：`appgdep_6a9f75c7f09c81918931407e4c7301d2`。
- 访问：仅当前所有者；异地使用同一 ChatGPT 账号登录。
- 状态：发布成功，服务端状态 `succeeded`。
- 在线入口：[Arena 系统现状与交互实验](https://arena-system-report.redstonemanliu.chatgpt.site)。

完整本地 HTML：[arena-report.html](../reports/arena-status/public/arena-report.html)。
