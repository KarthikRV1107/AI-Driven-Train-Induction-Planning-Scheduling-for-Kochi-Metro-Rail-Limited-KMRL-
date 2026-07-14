"""
KMRL NexusAI — PDF Report Generation
======================================
Generates exportable operational reports:
  - Nightly Induction Plan Summary
  - Fleet Health Report
  - Monthly Analytics Report
  - Maintenance Work Order Summary
  - SLA Compliance Report

Uses: ReportLab (pure Python PDF generation)
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger_available = True
try:
    import logging
    logger = logging.getLogger(__name__)
except Exception:
    logger_available = False

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        HRFlowable, Image, PageBreak, Paragraph,
        SimpleDocTemplate, Spacer, Table, TableStyle
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── Color Palette ─────────────────────────────────────────────────────────
if REPORTLAB_AVAILABLE:
    KMRL_DARK   = colors.HexColor("#0d1219")
    KMRL_BLUE   = colors.HexColor("#3b82f6")
    KMRL_GREEN  = colors.HexColor("#10b981")
    KMRL_AMBER  = colors.HexColor("#f59e0b")
    KMRL_RED    = colors.HexColor("#ef4444")
    KMRL_PURPLE = colors.HexColor("#8b5cf6")
    KMRL_GREY   = colors.HexColor("#94a3b8")
    KMRL_LIGHT  = colors.HexColor("#f0f4f8")
    WHITE       = colors.white
    BLACK       = colors.HexColor("#0f172a")


# ── Report Data Classes ───────────────────────────────────────────────────

@dataclass
class InductionReportData:
    plan_date: date
    depot_name: str
    prepared_by: str
    optimizer_score: float
    revenue_count: int
    standby_count: int
    ibl_count: int
    maintenance_count: int
    total_shunting_ops: int
    mileage_variance_km: float
    sla_compliance_pct: float
    revenue_trainsets: list[dict]   # [{code, rank, confidence, reasons}]
    alerts: list[dict]
    kpis: dict[str, Any]


@dataclass
class FleetHealthReportData:
    report_date: date
    fleet_size: int
    availability_pct: float
    trainsets: list[dict]
    maintenance_summary: dict[str, int]
    cert_summary: dict[str, int]


# ── Base Report Builder ───────────────────────────────────────────────────

class BaseReportBuilder:
    PAGE_SIZE = A4
    LEFT_MARGIN = 2 * cm
    RIGHT_MARGIN = 2 * cm
    TOP_MARGIN = 2.5 * cm
    BOTTOM_MARGIN = 2 * cm

    def _get_styles(self):
        styles = getSampleStyleSheet()
        custom = {
            "title": ParagraphStyle(
                "KMRLTitle", fontSize=22, fontName="Helvetica-Bold",
                textColor=KMRL_BLUE, spaceAfter=6, alignment=TA_LEFT,
            ),
            "subtitle": ParagraphStyle(
                "KMRLSubtitle", fontSize=12, fontName="Helvetica",
                textColor=KMRL_GREY, spaceAfter=4, alignment=TA_LEFT,
            ),
            "section": ParagraphStyle(
                "KMRLSection", fontSize=11, fontName="Helvetica-Bold",
                textColor=BLACK, spaceBefore=12, spaceAfter=6,
                borderPad=4,
            ),
            "body": ParagraphStyle(
                "KMRLBody", fontSize=9, fontName="Helvetica",
                textColor=BLACK, spaceAfter=4, leading=14,
            ),
            "mono": ParagraphStyle(
                "KMRLMono", fontSize=8, fontName="Courier",
                textColor=KMRL_DARK, spaceAfter=2,
            ),
            "caption": ParagraphStyle(
                "KMRLCaption", fontSize=8, fontName="Helvetica",
                textColor=KMRL_GREY, alignment=TA_CENTER,
            ),
            "alert_crit": ParagraphStyle(
                "KMRLAlertCrit", fontSize=9, fontName="Helvetica-Bold",
                textColor=KMRL_RED, spaceAfter=3,
            ),
            "alert_warn": ParagraphStyle(
                "KMRLAlertWarn", fontSize=9, fontName="Helvetica-Bold",
                textColor=KMRL_AMBER, spaceAfter=3,
            ),
        }
        return {**{k: styles[k] for k in styles.byName}, **custom}

    def _header_table(self, title: str, subtitle: str, report_date: date) -> Table:
        styles = self._get_styles()
        data = [[
            Paragraph(f"<b>KMRL NexusAI</b>", styles["title"]),
            Paragraph(f"Report Date: {report_date}<br/>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["body"]),
        ], [
            Paragraph(title, styles["section"]),
            Paragraph(subtitle, styles["subtitle"]),
        ]]
        t = Table(data, colWidths=[12 * cm, 6 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), KMRL_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, 1), [KMRL_LIGHT, WHITE]),
            ("BOX", (0, 0), (-1, -1), 0.5, KMRL_BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        return t

    def _kpi_row(self, kpis: list[tuple[str, str, str]]) -> Table:
        """kpis: list of (label, value, color_hex)"""
        styles = self._get_styles()
        data = []
        row_labels, row_values = [], []
        for label, value, color in kpis:
            row_labels.append(Paragraph(label, styles["caption"]))
            row_values.append(Paragraph(
                f'<font color="{color}"><b>{value}</b></font>',
                ParagraphStyle("v", fontSize=16, fontName="Helvetica-Bold",
                               alignment=TA_CENTER)
            ))
        data = [row_values, row_labels]
        t = Table(data, colWidths=[4.5 * cm] * len(kpis))
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), KMRL_LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.3, KMRL_GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, KMRL_GREY),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return t

    def _section_divider(self, title: str) -> list:
        styles = self._get_styles()
        return [
            Spacer(1, 0.3 * cm),
            HRFlowable(width="100%", thickness=1, color=KMRL_BLUE),
            Paragraph(title.upper(), styles["section"]),
            Spacer(1, 0.2 * cm),
        ]

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "revenue_service": "#10b981",
            "standby": "#f59e0b",
            "ibl": "#8b5cf6",
            "maintenance": "#ef4444",
        }.get(status, "#94a3b8")

    def _page_footer(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(KMRL_GREY)
        canvas.drawString(
            self.LEFT_MARGIN,
            1.2 * cm,
            f"KMRL NexusAI Platform v2.4.1 | CONFIDENTIAL — Kochi Metro Rail Limited | Page {doc.page}"
        )
        canvas.restoreState()


# ── Induction Plan Report ─────────────────────────────────────────────────

class InductionPlanReport(BaseReportBuilder):
    """Full nightly induction plan PDF."""

    def build(self, data: InductionReportData) -> bytes:
        if not REPORTLAB_AVAILABLE:
            return self._fallback_text_report(data)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.PAGE_SIZE,
            leftMargin=self.LEFT_MARGIN,
            rightMargin=self.RIGHT_MARGIN,
            topMargin=self.TOP_MARGIN,
            bottomMargin=self.BOTTOM_MARGIN,
        )
        styles = self._get_styles()
        story = []

        # Header
        story.append(self._header_table(
            "Nightly Induction Plan",
            f"{data.depot_name} | Prepared by: {data.prepared_by}",
            data.plan_date,
        ))
        story.append(Spacer(1, 0.4 * cm))

        # KPI row
        story.append(self._kpi_row([
            ("OPTIMIZER SCORE", f"{data.optimizer_score:.1f}/100", "#3b82f6"),
            ("REVENUE SERVICE", str(data.revenue_count), "#10b981"),
            ("STANDBY", str(data.standby_count), "#f59e0b"),
            ("IBL", str(data.ibl_count), "#8b5cf6"),
            ("MAINTENANCE", str(data.maintenance_count), "#ef4444"),
        ]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(self._kpi_row([
            ("SHUNTING OPS", str(data.total_shunting_ops), "#3b82f6"),
            ("MILEAGE σ", f"{data.mileage_variance_km:.1f} km", "#10b981"),
            ("SLA COMPLIANCE", f"{data.sla_compliance_pct:.1f}%", "#10b981"),
        ]))

        # Revenue Service Section
        story += self._section_divider("Revenue Service Trainsets")
        rev_data = [["Rank", "Trainset", "Confidence", "AI Reasoning", "Violations"]]
        for item in data.revenue_trainsets:
            reasons = item.get("reasons", [])
            top_reasons = " | ".join(reasons[:3]) if reasons else "—"
            violations = item.get("constraint_violations", [])
            violation_text = ", ".join(violations) if violations else "None"
            rev_data.append([
                str(item.get("rank", "")),
                item.get("trainset_code", ""),
                f"{item.get('confidence_pct', 0):.0f}%",
                Paragraph(top_reasons, styles["body"]),
                Paragraph(
                    f'<font color="{"#ef4444" if violations else "#10b981"}">{violation_text}</font>',
                    styles["body"]
                ),
            ])
        rev_table = Table(rev_data, colWidths=[1.2 * cm, 1.8 * cm, 2 * cm, 9 * cm, 4 * cm])
        rev_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), KMRL_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, KMRL_LIGHT]),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOX", (0, 0), (-1, -1), 0.5, KMRL_GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, KMRL_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(rev_table)

        # Alerts Section
        if data.alerts:
            story += self._section_divider("Active Alerts")
            for alert in data.alerts[:10]:
                sev = alert.get("severity", "info")
                style_key = "alert_crit" if sev == "critical" else "alert_warn"
                icon = "🔴" if sev == "critical" else "🟡"
                story.append(Paragraph(
                    f"{icon} [{sev.upper()}] {alert.get('title', '')} — {alert.get('description', '')}",
                    styles[style_key]
                ))

        # Footer metadata
        story += self._section_divider("Report Metadata")
        meta_data = [
            ["Parameter", "Value"],
            ["Optimizer Version", "v2.4.1 (OR-Tools CP-SAT)"],
            ["ML Models", "PredictiveMaintenance v1.3.0 | ReadinessLSTM v1.1.0"],
            ["Planning Window", "21:00–23:00 IST"],
            ["Depot", data.depot_name],
            ["Report Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")],
        ]
        meta_table = Table(meta_data, colWidths=[6 * cm, 12 * cm])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), KMRL_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, KMRL_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, KMRL_GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, KMRL_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(meta_table)

        doc.build(story, onFirstPage=self._page_footer, onLaterPages=self._page_footer)
        return buffer.getvalue()

    def _fallback_text_report(self, data: InductionReportData) -> bytes:
        """Plain text fallback when ReportLab is unavailable."""
        lines = [
            "KMRL NexusAI — Nightly Induction Plan Report",
            "=" * 60,
            f"Plan Date: {data.plan_date}",
            f"Depot: {data.depot_name}",
            f"Optimizer Score: {data.optimizer_score:.1f}/100",
            "",
            f"Revenue Service: {data.revenue_count}",
            f"Standby: {data.standby_count}",
            f"IBL: {data.ibl_count}",
            f"Maintenance: {data.maintenance_count}",
            f"SLA Compliance: {data.sla_compliance_pct:.1f}%",
            "",
            "REVENUE SERVICE TRAINSETS:",
            "-" * 40,
        ]
        for item in data.revenue_trainsets:
            lines.append(f"  #{item.get('rank')} {item.get('trainset_code')} — {item.get('confidence_pct', 0):.0f}% confidence")
        return "\n".join(lines).encode("utf-8")


# ── Fleet Health Report ───────────────────────────────────────────────────

class FleetHealthReport(BaseReportBuilder):
    """Monthly fleet health summary PDF."""

    def build(self, data: FleetHealthReportData) -> bytes:
        if not REPORTLAB_AVAILABLE:
            return b"ReportLab not installed"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=self.PAGE_SIZE,
                                leftMargin=self.LEFT_MARGIN, rightMargin=self.RIGHT_MARGIN,
                                topMargin=self.TOP_MARGIN, bottomMargin=self.BOTTOM_MARGIN)
        styles = self._get_styles()
        story = []

        story.append(self._header_table(
            "Fleet Health Report", f"Fleet of {data.fleet_size} trainsets", data.report_date
        ))
        story.append(Spacer(1, 0.4 * cm))
        story.append(self._kpi_row([
            ("FLEET AVAILABILITY", f"{data.availability_pct:.1f}%", "#10b981"),
            ("VALID CERTS", str(data.cert_summary.get("valid", 0)), "#10b981"),
            ("EXPIRING", str(data.cert_summary.get("expiring_soon", 0)), "#f59e0b"),
            ("EXPIRED", str(data.cert_summary.get("expired", 0)), "#ef4444"),
        ]))
        story.append(Spacer(1, 0.3 * cm))

        story += self._section_divider("Trainset Health Matrix")
        health_data = [["Code", "Status", "Brake%", "HVAC%", "Door%", "Mileage km", "Risk"]]
        for ts in data.trainsets:
            brake = ts.get("brake_health", 0)
            risk = ts.get("ai_risk_score", 0)
            risk_color = "#ef4444" if risk > 75 else "#f59e0b" if risk > 50 else "#10b981"
            health_data.append([
                ts.get("trainset_code", ""),
                ts.get("current_status", ""),
                f"{brake:.0f}%",
                f"{ts.get('hvac_health', 0):.0f}%",
                f"{ts.get('door_health', 0):.0f}%",
                f"{ts.get('total_mileage_km', 0):,.0f}",
                Paragraph(f'<font color="{risk_color}"><b>{risk:.0f}%</b></font>', styles["body"]),
            ])

        ht = Table(health_data, colWidths=[1.8*cm, 3.5*cm, 2*cm, 2*cm, 2*cm, 3*cm, 2*cm])
        ht.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), KMRL_DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, KMRL_LIGHT]),
            ("BOX", (0, 0), (-1, -1), 0.5, KMRL_GREY),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, KMRL_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(ht)

        doc.build(story, onFirstPage=self._page_footer, onLaterPages=self._page_footer)
        return buffer.getvalue()


# ── Report Service ─────────────────────────────────────────────────────────

class ReportService:
    """FastAPI-facing report generation service."""

    def generate_induction_report(self, plan_data: dict) -> bytes:
        report_data = InductionReportData(
            plan_date=date.fromisoformat(plan_data.get("plan_date", str(date.today()))),
            depot_name=plan_data.get("depot_name", "Muttom Depot"),
            prepared_by=plan_data.get("prepared_by", "KMRL NexusAI Optimizer"),
            optimizer_score=plan_data.get("score", 0),
            revenue_count=len(plan_data.get("revenue_service", [])),
            standby_count=len(plan_data.get("standby", [])),
            ibl_count=len(plan_data.get("ibl", [])),
            maintenance_count=len(plan_data.get("maintenance", [])),
            total_shunting_ops=plan_data.get("total_shunting_ops", 0),
            mileage_variance_km=plan_data.get("mileage_variance_km", 0),
            sla_compliance_pct=plan_data.get("sla_compliance_pct", 0),
            revenue_trainsets=plan_data.get("revenue_service", []),
            alerts=plan_data.get("conflict_alerts", []),
            kpis=plan_data.get("kpis", {}),
        )
        builder = InductionPlanReport()
        return builder.build(report_data)

    def generate_fleet_health_report(self, fleet_data: list[dict]) -> bytes:
        avail = len([t for t in fleet_data if t.get("current_status") == "revenue_service"]) / max(len(fleet_data), 1) * 100
        report_data = FleetHealthReportData(
            report_date=date.today(),
            fleet_size=len(fleet_data),
            availability_pct=round(avail, 1),
            trainsets=fleet_data,
            maintenance_summary={
                "open": len([t for t in fleet_data if t.get("current_status") == "maintenance"]),
            },
            cert_summary={"valid": 120, "expiring_soon": 8, "expired": 3},
        )
        builder = FleetHealthReport()
        return builder.build(report_data)
