"""C：培养方案规则领域。"""

from app.domains.degree.audit import CALCULATION_VERSION, audit_degree_progress

__all__ = ["CALCULATION_VERSION", "audit_degree_progress"]
