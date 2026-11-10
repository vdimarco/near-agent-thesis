from pathlib import Path
import json
from src.analyze import run_analysis

ROOT = Path(__file__).resolve().parent.parent


def test_run_analysis_builds_audit_stats_and_four_svg_charts():
    stats = run_analysis(ROOT)
    audit_path = ROOT / "data" / "audit_stats.json"
    assert audit_path.exists()
    loaded = json.loads(audit_path.read_text(encoding="utf-8"))
    assert loaded == stats

    for key in [
        "macro_network",
        "agent_primitives",
        "receiver_concentration",
        "intents_quotes",
        "swarm_tco",
        "falsification_checks",
    ]:
        assert key in stats

    for chart_name in [
        "chart1_primitives.svg",
        "chart2_concentration.svg",
        "chart3_intents_spreads.svg",
        "chart4_swarm_tco.svg",
    ]:
        svg_path = ROOT / "dashboard" / "assets" / chart_name
        assert svg_path.exists()
        content = svg_path.read_text(encoding="utf-8")
        assert content.startswith("<svg") and "</svg>" in content
