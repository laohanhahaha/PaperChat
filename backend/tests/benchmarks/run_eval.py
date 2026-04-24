"""运行多模态评估

用法:
    # 干运行：仅生成样本清单
    python -m tests.benchmarks.run_eval

    # 完整评估（需要 LLM 服务可用）
    python -m tests.benchmarks.run_eval --live

    # 仅运行指定类别
    python -m tests.benchmarks.run_eval --live --categories chart_type

    # 与上次报告对比
    python -m tests.benchmarks.run_eval --live --compare
"""
import argparse
import asyncio
import sys
from pathlib import Path

# 确保 backend 目录在 sys.path 中
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.benchmarks.multimodal_eval import MultimodalBenchmark


async def dry_run():
    """干运行：仅生成样本清单，不调用 LLM"""
    benchmark = MultimodalBenchmark()
    benchmark.load_samples()
    print(f"已生成 {len(benchmark.samples)} 个样本模板")

    # 按类别统计
    from collections import Counter
    cat_counts = Counter(s.category for s in benchmark.samples)
    for cat, count in cat_counts.items():
        print(f"  {cat}: {count} 样本")

    print(f"\n数据目录: {benchmark.data_dir}")
    print("放入测试图片后，使用 --live 参数运行完整评估")


async def live_run(categories: list[str] = None, compare: bool = False):
    """完整评估：调用 LLM 服务"""
    try:
        from app.services.llm_service import llm_service
    except ImportError:
        print("错误: 无法导入 llm_service，请确保在 backend 目录下运行")
        print("  cd backend && python -m tests.benchmarks.run_eval --live")
        sys.exit(1)

    benchmark = MultimodalBenchmark()

    print("开始评估...")
    report = await benchmark.run_all(llm_service, categories=categories)

    # 打印汇总
    benchmark.print_summary(report)

    # 保存报告
    report_path = Path(__file__).parent / "latest_report.json"
    benchmark.save_report(report, str(report_path))
    print(f"\n报告已保存: {report_path}")

    # 对比上次结果
    if compare:
        prev_path = Path(__file__).parent / "previous_report.json"
        if prev_path.exists():
            delta = benchmark.compare_with_previous(str(prev_path))
            print("\n--- 与上次对比 ---")
            for cat_name, d in delta.get("categories", {}).items():
                acc_d = d["accuracy_delta"]
                lat_d = d["latency_delta_ms"]
                acc_arrow = "↑" if acc_d > 0 else "↓" if acc_d < 0 else "→"
                lat_arrow = "↓" if lat_d < 0 else "↑" if lat_d > 0 else "→"
                print(
                    f"  {cat_name:25s} | Acc {acc_arrow} {acc_d:+.1%} | "
                    f"Latency {lat_arrow} {lat_d:+.0f}ms"
                )
        else:
            print("\n未找到上次报告，跳过对比")

    # 将当前报告备份为 previous_report.json
    import shutil
    shutil.copy2(report_path, Path(__file__).parent / "previous_report.json")


def main():
    parser = argparse.ArgumentParser(description="多模态评估基准")
    parser.add_argument("--live", action="store_true", help="运行完整评估（需要 LLM 服务）")
    parser.add_argument(
        "--categories", nargs="*", default=None,
        choices=["chart_type", "data_extraction", "image_text_matching"],
        help="仅运行指定类别",
    )
    parser.add_argument("--compare", action="store_true", help="与上次报告对比")
    args = parser.parse_args()

    if args.live:
        asyncio.run(live_run(categories=args.categories, compare=args.compare))
    else:
        asyncio.run(dry_run())


if __name__ == "__main__":
    main()
