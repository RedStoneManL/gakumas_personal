"""Human-readable first-run results; no external plotting dependencies."""
import json
from pathlib import Path


def write_report(output):
    output = Path(output)
    result = json.loads((output / "final_test.json").read_text(encoding="utf-8"))
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    lines = ["# HIF 本战第二轮试跑结果", "",
             f"完成 {status['decisions']:,} 次可选择的决策、{status['batches']} 个训练批次；用时 {status['elapsed_seconds']/60:.1f} 分钟。", "",
             "以下各策略使用相同的留出种子和入场配置；训练过程没有使用这些种子。", "",
             "| 策略 | 平均终局分 | 平均值标准误 | 最低分 | 经验 P10 |", "|---|---:|---:|---:|---:|"]
    initial_label = ('迁移起点（旧课程已训练权重）'
                     if result.get('initialization', {}).get('kind') == 'transferred_trained_weights'
                     else '初始权重（未训练）')
    for key, label in [("initialized", initial_label), ("random", "随机合法动作"),
                       ("latest", "最新权重"), ("best_validation", "验证集选出的权重")]:
        r = result[key]
        lines.append(f"| {label} | {r['mean']:,.0f} | {r['mean_se']:,.0f} | {r['minimum']:,.0f} | {r['p10_empirical']:,.0f} |")
    lines += ["", "逐局配对比较：", ""]
    for key, label in [("gain_vs_initialized", "初始策略"), ("gain_vs_random", "随机策略")]:
        r = result[key]
        lines.append(f"- 最新权重相对{label}平均变化 **{r['mean']:+,.0f} 分**，配对标准误 {r['mean_se']:,.0f}；{r['positive_pairs']}/{r['episodes']} 局更高。")
    lines += ["", "这是一轮可行性试验。少量种子上的涨分不能证明泛化；应结合标准误、低分表现及后续独立重复实验判断。", "",
              "评估策略选择最大概率动作；训练时按概率采样。价值头学习的是采样策略的期望回报，不能直接当成已校准的通用卡组评分器。", "",
              "本结果只适用于 manifest.json 记录的 Arena 版本、课程与入场分布；不代表完整真实游戏的 HIF 成绩。", "",
              "latest.pt 用于恢复最新进度；best.pt 是验证集选择的权重。每局动作、种子和成绩见 episodes.jsonl；训练曲线原始数据见 metrics.jsonl。", ""]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
