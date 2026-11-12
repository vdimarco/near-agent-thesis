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


def test_document_traceability_and_no_em_dashes():
    stats = json.loads((ROOT / "data" / "audit_stats.json").read_text(encoding="utf-8"))
    thesis = (ROOT / "THESIS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dashboard = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")

    for doc_name, text in [
        ("THESIS.md", thesis),
        ("README.md", readme),
        ("dashboard/index.html", dashboard),
    ]:
        assert "\u2014" not in text, f"Found em dash in {doc_name}"

    expected_tokens = [
        f"{stats['agent_primitives']['scoped_key_share_pct']:.1f}%",
        f"${stats['swarm_tco']['near_scoped_keys']['total_30d_usd']:.2f}",
        f"${stats['swarm_tco']['near_subaccounts']['total_30d_usd']:.2f}",
        f"${stats['swarm_tco']['base_erc4337']['total_30d_usd']:.2f}",
        f"{stats['receiver_concentration']['top3_share_pct']:.1f}%",
    ]
    for token in expected_tokens:
        assert token in thesis, f"Missing {token} in THESIS.md"
        assert token in dashboard, f"Missing {token} in dashboard/index.html"

    assert "https://github.com/vdimarco/near-hackathon-market" in readme
    preview_png = ROOT / "dashboard" / "assets" / "dashboard-preview.png"
    assert preview_png.exists() and preview_png.stat().st_size > 10_000
