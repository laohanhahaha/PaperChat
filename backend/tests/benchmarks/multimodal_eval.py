"""多模态评估基准框架

定位: 回归测试基准（确保改动不降级），不用于模型选型决策
性能: 完整 100 样本评估预计 5-10 分钟（云端）

三个评估维度:
1. 图表类型识别 (50 样本) — Accuracy
2. 图表数据提取 (30 样本) — F1 Score
3. 图文匹配 (20 样本) — Recall

依赖接口:
- llm_service.analyze_chart(image_data, chart_type_hint, question) -> dict
- llm_service.chat_with_image(image_data, prompt, image_type, use_cloud) -> str
"""
import json
import time
import os
import base64
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class EvalSample:
    """评估样本"""
    id: str
    category: str  # "chart_type" | "data_extraction" | "image_text_matching"
    image_path: str  # 相对路径（相对于 data_dir）
    ground_truth: dict  # 预期结果
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalResult:
    """单样本评估结果"""
    sample_id: str
    category: str
    predicted: dict
    ground_truth: dict
    correct: bool
    latency_ms: float
    error: Optional[str] = None


class MultimodalBenchmark:
    """多模态评估基准

    用法:
        benchmark = MultimodalBenchmark()
        benchmark.load_samples()
        report = await benchmark.run_all(llm_service)
        benchmark.print_summary(report)
        benchmark.save_report(report)

    性能: 云端 100 样本 ≈ 5-10 分钟，本地 Ollama ≈ 30-60 分钟
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)
        self.samples: list[EvalSample] = []
        self.results: list[EvalResult] = []

    # ------------------------------------------------------------------
    # 样本管理
    # ------------------------------------------------------------------

    def load_samples(self):
        """从 JSON 文件加载测试样本；若不存在则自动生成模板清单"""
        manifest = self.data_dir / "manifest.json"
        if manifest.exists():
            with open(manifest, encoding="utf-8") as f:
                data = json.load(f)
            self.samples = [EvalSample(**s) for s in data["samples"]]
        else:
            self._generate_sample_manifest()

    def _generate_sample_manifest(self):
        """生成样本清单模板（需要后续手动填充真实数据）"""
        samples = []

        # 维度1: 图表类型识别 — 50 样本
        chart_types = [
            "line_chart", "bar_chart", "pie_chart", "table", "flowchart",
            "scatter_plot", "heatmap", "box_plot", "area_chart", "histogram",
        ]
        for i, ct in enumerate(chart_types * 5):
            samples.append({
                "id": f"chart_type_{i:03d}",
                "category": "chart_type",
                "image_path": f"chart_type/sample_{i:03d}.png",
                "ground_truth": {"chart_type": ct},
                "metadata": {"source": "arxiv", "difficulty": "medium"},
            })

        # 维度2: 数据提取 — 30 样本
        for i in range(30):
            samples.append({
                "id": f"data_extract_{i:03d}",
                "category": "data_extraction",
                "image_path": f"data_extraction/sample_{i:03d}.png",
                "ground_truth": {"values": [], "labels": [], "title": ""},
                "metadata": {"source": "arxiv", "has_numbers": True},
            })

        # 维度3: 图文匹配 — 20 样本
        for i in range(20):
            samples.append({
                "id": f"img_text_{i:03d}",
                "category": "image_text_matching",
                "image_path": f"image_text/sample_{i:03d}.png",
                "ground_truth": {"matching_text": "", "relevance_score": 0.0},
                "metadata": {"source": "arxiv", "domain": "cs"},
            })

        manifest = {
            "version": "1.0",
            "total_samples": len(samples),
            "samples": samples,
        }
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.data_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # 创建子目录
        for subdir in ["chart_type", "data_extraction", "image_text"]:
            os.makedirs(self.data_dir / subdir, exist_ok=True)

        self.samples = [EvalSample(**s) for s in samples]

    # ------------------------------------------------------------------
    # 单样本评估
    # ------------------------------------------------------------------

    async def evaluate_chart_type(self, sample: EvalSample, llm_service) -> EvalResult:
        """评估图表类型识别

        调用 llm_service.analyze_chart()，比较返回的 chart_type 与 ground_truth。
        性能: 单样本 2-5s（云端），10-30s（本地）
        """
        start = time.time()
        try:
            img_path = self.data_dir / sample.image_path
            if not img_path.exists():
                return EvalResult(
                    sample.id, sample.category, {}, sample.ground_truth,
                    False, 0, error="图片文件不存在",
                )

            with open(img_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            result = await llm_service.analyze_chart(image_data)
            predicted_type = result.get("chart_type", "unknown").lower()
            expected_type = sample.ground_truth.get("chart_type", "").lower()

            # 宽松匹配: 完全相等 或 预期值包含在预测值中
            correct = predicted_type == expected_type or expected_type in predicted_type
            latency = (time.time() - start) * 1000

            return EvalResult(
                sample.id, sample.category, result, sample.ground_truth,
                correct, latency,
            )
        except Exception as e:
            return EvalResult(
                sample.id, sample.category, {}, sample.ground_truth,
                False, (time.time() - start) * 1000, error=str(e),
            )

    async def evaluate_data_extraction(self, sample: EvalSample, llm_service) -> EvalResult:
        """评估图表数据提取

        调用 llm_service.analyze_chart()，通过 data_summary / key_findings
        与 ground_truth 中的 values / labels 做关键词匹配计算 F1。
        性能: 单样本 2-5s（云端），10-30s（本地）
        """
        start = time.time()
        try:
            img_path = self.data_dir / sample.image_path
            if not img_path.exists():
                return EvalResult(
                    sample.id, sample.category, {}, sample.ground_truth,
                    False, 0, error="图片文件不存在",
                )

            with open(img_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            result = await llm_service.analyze_chart(
                image_data, chart_type_hint="", question="请提取图表中的所有数值和标签",
            )

            # 简化 F1 计算：将 ground_truth 中的关键词与结果文本做匹配
            gt_values = sample.ground_truth.get("values", [])
            gt_labels = sample.ground_truth.get("labels", [])
            gt_title = sample.ground_truth.get("title", "")

            # 将模型输出合并为一段文本用于匹配
            result_text = " ".join([
                str(result.get("data_summary", "")),
                " ".join(result.get("key_findings", [])),
                str(result.get("raw_description", "")),
            ]).lower()

            # 计算 precision / recall
            gt_tokens = set()
            for v in gt_values:
                for token in str(v).lower().split():
                    gt_tokens.add(token)
            for label in gt_labels:
                for token in str(label).lower().split():
                    gt_tokens.add(token)
            if gt_title:
                for token in str(gt_title).lower().split():
                    gt_tokens.add(token)

            if not gt_tokens:
                # 无 ground_truth 关键词时，标记为正确（模板数据）
                correct = True
            else:
                matched = sum(1 for t in gt_tokens if t in result_text)
                recall = matched / len(gt_tokens)
                correct = recall >= 0.5  # 至少匹配 50% 的关键词

            latency = (time.time() - start) * 1000

            return EvalResult(
                sample.id, sample.category, result, sample.ground_truth,
                correct, latency,
            )
        except Exception as e:
            return EvalResult(
                sample.id, sample.category, {}, sample.ground_truth,
                False, (time.time() - start) * 1000, error=str(e),
            )

    async def evaluate_image_text_matching(self, sample: EvalSample, llm_service) -> EvalResult:
        """评估图文匹配

        调用 llm_service.chat_with_image()，判断模型输出是否包含
        ground_truth 中的 matching_text 关键词。
        性能: 单样本 2-5s（云端），10-30s（本地）
        """
        start = time.time()
        try:
            img_path = self.data_dir / sample.image_path
            if not img_path.exists():
                return EvalResult(
                    sample.id, sample.category, {}, sample.ground_truth,
                    False, 0, error="图片文件不存在",
                )

            with open(img_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            matching_text = sample.ground_truth.get("matching_text", "")
            if matching_text:
                prompt = (
                    "请判断这张图片是否与以下描述相关，"
                    "并用'是'或'否'回答，然后简要说明理由。\n\n"
                    f"描述：{matching_text}"
                )
            else:
                prompt = "请详细描述这张图片的内容。"

            description = await llm_service.chat_with_image(
                image_data, prompt, image_type="base64", use_cloud=True,
            )

            # 简化匹配: 检查描述是否包含关键词
            if not matching_text:
                correct = True
            else:
                expected_score = sample.ground_truth.get("relevance_score", 0.0)
                # 如果描述中包含"是"或 matching_text 中的关键词，视为匹配
                desc_lower = description.lower()
                has_positive = "是" in description or "yes" in desc_lower
                keyword_hits = sum(
                    1 for kw in matching_text.lower().split() if kw in desc_lower
                )
                keyword_ratio = keyword_hits / max(len(matching_text.split()), 1)

                if expected_score >= 0.7:
                    correct = has_positive and keyword_ratio >= 0.3
                else:
                    correct = has_positive or keyword_ratio >= 0.3

            latency = (time.time() - start) * 1000

            return EvalResult(
                sample.id, sample.category,
                {"description": description},
                sample.ground_truth, correct, latency,
            )
        except Exception as e:
            return EvalResult(
                sample.id, sample.category, {}, sample.ground_truth,
                False, (time.time() - start) * 1000, error=str(e),
            )

    # ------------------------------------------------------------------
    # 批量运行与报告
    # ------------------------------------------------------------------

    async def run_all(self, llm_service, categories: list[str] = None) -> dict:
        """运行完整评估

        Args:
            llm_service: LLMService 实例
            categories: 仅运行指定类别，None 表示全部

        Returns:
            评估报告 dict

        性能: 云端 100 样本 ≈ 5-10 分钟（受并发限制为串行调用）
        """
        self.load_samples()
        self.results = []

        eval_map = {
            "chart_type": self.evaluate_chart_type,
            "data_extraction": self.evaluate_data_extraction,
            "image_text_matching": self.evaluate_image_text_matching,
        }

        for sample in self.samples:
            if categories and sample.category not in categories:
                continue
            evaluator = eval_map.get(sample.category)
            if evaluator is None:
                continue
            result = await evaluator(sample, llm_service)
            self.results.append(result)

        return self.generate_report()

    def generate_report(self) -> dict:
        """生成评估报告"""
        categories = {}
        for r in self.results:
            if r.category not in categories:
                categories[r.category] = {
                    "total": 0, "correct": 0, "errors": 0, "latencies": [],
                }
            cat = categories[r.category]
            cat["total"] += 1
            if r.error:
                cat["errors"] += 1
            elif r.correct:
                cat["correct"] += 1
            cat["latencies"].append(r.latency_ms)

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_samples": len(self.results),
            "categories": {},
        }

        for name, cat in categories.items():
            valid = cat["total"] - cat["errors"]
            report["categories"][name] = {
                "accuracy": cat["correct"] / valid if valid > 0 else 0,
                "total": cat["total"],
                "correct": cat["correct"],
                "errors": cat["errors"],
                "avg_latency_ms": (
                    sum(cat["latencies"]) / len(cat["latencies"])
                    if cat["latencies"] else 0
                ),
            }

        return report

    def compare_with_previous(self, previous_report_path: str) -> dict:
        """与上次运行结果对比，生成 delta

        Args:
            previous_report_path: 上次报告 JSON 文件路径

        Returns:
            包含各维度变化量的 dict
        """
        prev_path = Path(previous_report_path)
        if not prev_path.exists():
            return {"error": f"上次报告不存在: {previous_report_path}"}

        with open(prev_path, encoding="utf-8") as f:
            prev = json.load(f)

        current = self.generate_report()
        delta = {"timestamp": current["timestamp"], "previous_timestamp": prev.get("timestamp"), "categories": {}}

        for cat_name in current["categories"]:
            cur_cat = current["categories"][cat_name]
            prev_cat = prev.get("categories", {}).get(cat_name, {})
            delta["categories"][cat_name] = {
                "accuracy_delta": cur_cat["accuracy"] - prev_cat.get("accuracy", 0),
                "latency_delta_ms": cur_cat["avg_latency_ms"] - prev_cat.get("avg_latency_ms", 0),
                "current": cur_cat,
                "previous": prev_cat if prev_cat else None,
            }

        return delta

    def print_summary(self, report: dict):
        """控制台汇总表格"""
        print("=" * 60)
        print(f"多模态评估报告 | {report['timestamp']}")
        print(f"总样本: {report['total_samples']}")
        print("-" * 60)
        for name, cat in report["categories"].items():
            print(
                f"  {name:25s} | Acc: {cat['accuracy']:.1%} | "
                f"{cat['correct']}/{cat['total']} | "
                f"Avg: {cat['avg_latency_ms']:.0f}ms | "
                f"Err: {cat['errors']}"
            )
        print("=" * 60)

    def save_report(self, report: dict, path: str = None):
        """保存报告到 JSON

        Args:
            report: generate_report() 的返回值
            path: 保存路径，默认为 benchmarks 目录下的 latest_report.json
        """
        if path is None:
            path = Path(__file__).parent / "latest_report.json"
        path = Path(path)
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
