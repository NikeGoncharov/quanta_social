"""Derived metrics: KPIs (CTR/CVR/CPM/CPC/CPA/ROAS/win-rate) and the glass-box 'why'
diagnostics that explain what is limiting a campaign's delivery."""
from .diagnostics import Diagnosis, diagnose
from .kpis import Kpis, rollup

__all__ = ["Kpis", "rollup", "Diagnosis", "diagnose"]
