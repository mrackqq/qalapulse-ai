from __future__ import annotations

import csv
import io
import json
import shutil
import textwrap
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, or_, select, text
from sqlalchemy.orm import Session

from app.config import BASE_DIR, UPLOAD_DIR
from app.database import engine, get_db
from app.models import Base, DuplicateLink, Issue, StatusHistory
from app.schemas import CATEGORIES, DISTRICTS, STATUSES, IssueCreate, IssueRead, StatusUpdate
from app.services.ai_analyzer import AnalysisResult, apply_duplicate_bonus
from app.services.duplicate_detector import DuplicateCandidate, find_duplicates
from app.services.llm_analyzer import analyze_issue_mvp


CATEGORY_LABELS = {
    "transport": "Транспорт",
    "roads": "Дороги и тротуары",
    "lighting": "Освещение",
    "flooding": "Подтопления",
    "snow_ice": "Снег и гололед",
    "trash": "Мусор",
    "smell_ecology": "Запахи и экология",
    "playground": "Площадки",
    "safety": "Безопасность",
    "utilities": "ЖКХ",
    "other": "Другое",
}

DISTRICT_LABELS = {
    "Esil": "Есиль",
    "Nura": "Нура",
    "Almaty": "Алматы",
    "Saryarka": "Сарыарка",
    "Baikonur": "Байконур",
    "Unknown": "Не определен",
}

STATUS_LABELS = {
    "new": "Ожидает приема",
    "in_progress": "В работе",
    "resolved": "Решено",
    "rejected": "Отклонено",
}

RISK_LABELS = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}

SLA_LABELS = {
    "on_track": "В срок",
    "due_soon": "Скоро срок",
    "overdue": "SLA просрочен",
    "closed": "Закрыто",
    "not_set": "Не задано",
}

SERVICE_BY_CATEGORY = {
    "transport": "City Transportation Systems",
    "roads": "Управление дорог и тротуаров",
    "lighting": "Служба городского освещения",
    "flooding": "Служба ливневой канализации",
    "snow_ice": "Служба зимнего содержания",
    "trash": "Astana Tazalyk / отходы",
    "smell_ecology": "Экологический мониторинг",
    "playground": "Управление дворов и площадок",
    "safety": "Служба общественной безопасности",
    "utilities": "ЖКХ и коммунальные сети",
    "other": "City Operations Center",
}

SLA_HOURS_BY_RISK = {"high": 24, "medium": 72, "low": 168}
URGENT_CATEGORY_HOURS = {"safety": 12, "flooding": 12, "utilities": 18, "snow_ice": 24}

DEMO_USERS = {
    "resident": {"name": "Resident Demo", "role": "resident", "password": "demo", "district": None, "service": None},
    "operator": {"name": "City Operator", "role": "operator", "password": "demo", "district": None, "service": None},
    "esil": {"name": "Esil District Admin", "role": "district_admin", "password": "demo", "district": "Esil", "service": None},
    "lighting": {
        "name": "Lighting Service",
        "role": "service",
        "password": "demo",
        "district": None,
        "service": SERVICE_BY_CATEGORY["lighting"],
    },
    "roads": {
        "name": "Roads Service",
        "role": "service",
        "password": "demo",
        "district": None,
        "service": SERVICE_BY_CATEGORY["roads"],
    },
    "admin": {"name": "Super Admin", "role": "super_admin", "password": "demo", "district": None, "service": None},
}

ROLE_LABELS = {
    "guest": "Гость",
    "resident": "Житель",
    "operator": "Оператор",
    "district_admin": "Районный админ",
    "service": "Служба",
    "super_admin": "Super admin",
}

GEOCODE_POINTS = [
    {"name": "Mega Silk Way", "lat": 51.0895, "lon": 71.4132, "district": "Esil"},
    {"name": "EXPO", "lat": 51.0908, "lon": 71.4184, "district": "Esil"},
    {"name": "Ботанический сад", "lat": 51.1035, "lon": 71.4158, "district": "Esil"},
    {"name": "Қабанбай Батыр даңғылы", "lat": 51.141153, "lon": 71.418741, "district": "Esil"},
    {"name": "Мәңгілік Ел даңғылы", "lat": 51.107410, "lon": 71.430107, "district": "Esil"},
    {"name": "Сығанақ көшесі", "lat": 51.131261, "lon": 71.371859, "district": "Esil"},
    {"name": "Достық көшесі", "lat": 51.126328, "lon": 71.427531, "district": "Esil"},
    {"name": "Тұран даңғылы", "lat": 51.141908, "lon": 71.410526, "district": "Nura"},
    {"name": "Ұлы Дала даңғылы", "lat": 51.093483, "lon": 71.496820, "district": "Esil"},
    {"name": "Қорғалжын тас жолы", "lat": 51.126055, "lon": 71.298990, "district": "Nura"},
    {"name": "Абылай Хан даңғылы", "lat": 51.143931, "lon": 71.513655, "district": "Almaty"},
    {"name": "Тәуелсіздік даңғылы", "lat": 51.140078, "lon": 71.466133, "district": "Almaty"},
    {"name": "Бауыржан Момышұлы даңғылы", "lat": 51.139382, "lon": 71.478820, "district": "Almaty"},
    {"name": "Сарыарқа даңғылы", "lat": 51.172011, "lon": 71.407279, "district": "Saryarka"},
    {"name": "Кенесары көшесі", "lat": 51.164377, "lon": 71.458145, "district": "Saryarka"},
    {"name": "Бөгенбай Батыр даңғылы", "lat": 51.177417, "lon": 71.426587, "district": "Baikonur"},
    {"name": "Бейбітшілік көшесі", "lat": 51.176639, "lon": 71.417130, "district": "Baikonur"},
    {"name": "Сәкен Сейфуллин көшесі", "lat": 51.171974, "lon": 71.430704, "district": "Baikonur"},
    {"name": "Бараев көшесі", "lat": 51.156726, "lon": 71.435162, "district": "Baikonur"},
]


app = FastAPI(
    title="QalaPulse AI",
    description="Smart city MVP for Astana citizen issue analysis and prioritization.",
    version="0.2.0",
)

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
templates.env.globals["current_user_from_request"] = lambda request: get_current_user(request)
templates.env.globals["role_labels"] = ROLE_LABELS
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ensure_schema()


@app.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "page_title": "QalaPulse AI",
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "page_title": "Login",
            "users": DEMO_USERS,
            "role_labels": ROLE_LABELS,
        },
    )


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    account = DEMO_USERS.get(username)
    if account is None or account["password"] != password:
        return RedirectResponse(url="/login?error=1", status_code=303)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("qalapulse_user", username, httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("qalapulse_user")
    return response


@app.get("/submit", response_class=HTMLResponse)
def submit_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "submit.html",
        {
            "page_title": "Сообщить о проблеме",
            "categories": CATEGORIES,
            "category_labels": CATEGORY_LABELS,
        },
    )


@app.post("/submit", response_class=HTMLResponse)
def submit_issue(
    request: Request,
    user_name: str | None = Form(default=None),
    text: str = Form(...),
    address_text: str | None = Form(default=None),
    category_hint: str | None = Form(default=None),
    latitude: str | None = Form(default=None),
    longitude: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lat = _parse_float(latitude)
    lon = _parse_float(longitude)
    photo_path = _save_upload(photo)
    issue, duplicate_candidates = create_issue(
        db=db,
        user_name=_clean_optional(user_name),
        text=text,
        address_text=_clean_optional(address_text),
        latitude=lat,
        longitude=lon,
        category_hint=_clean_category_hint(category_hint),
        photo_path=photo_path,
        source="web",
    )
    duplicate_rows = get_duplicate_rows(db, issue.id)
    return templates.TemplateResponse(
        request,
        "submit_result.html",
        {
            "page_title": f"Заявка #{issue.id}",
            "issue": issue,
            "duplicate_candidates": duplicate_candidates,
            "duplicates": duplicate_rows,
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "risk_labels": RISK_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    category: str | None = Query(default=None),
    district: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sla: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    issues = list_filtered_issues(db, category=category, district=district, status=status, sla=sla)
    stats = get_stats_payload(db)
    duplicate_counts = get_duplicate_counts(db)
    map_points = [
        _issue_map_payload(issue, duplicate_counts.get(issue.id, 0))
        for issue in issues
        if issue.latitude and issue.longitude
    ]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "page_title": "Dashboard",
            "issues": issues,
            "map_points_json": json.dumps(map_points, ensure_ascii=False),
            "stats": stats,
            "duplicate_counts": duplicate_counts,
            "categories": CATEGORIES,
            "districts": DISTRICTS,
            "statuses": STATUSES,
            "sla_statuses": list(SLA_LABELS),
            "selected_category": category or "",
            "selected_district": district or "",
            "selected_status": status or "",
            "selected_sla": sla or "",
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "risk_labels": RISK_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/service", response_class=HTMLResponse)
def service_cabinet(
    request: Request,
    service: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sla: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user = get_current_user(request)
    selected_service = user.get("service") if user["role"] == "service" else service
    issues = list_filtered_issues(db, status=status, sla=sla, service=selected_service)
    return templates.TemplateResponse(
        request,
        "service.html",
        {
            "page_title": "Service cabinet",
            "issues": issues,
            "summary": build_report_summary(issues),
            "services": sorted(set(SERVICE_BY_CATEGORY.values())),
            "selected_service": selected_service or "",
            "selected_status": status or "",
            "selected_sla": sla or "",
            "statuses": STATUSES,
            "sla_statuses": list(SLA_LABELS),
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/district", response_class=HTMLResponse)
def district_cabinet(
    request: Request,
    district: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user = get_current_user(request)
    selected_district = user.get("district") if user["role"] == "district_admin" else district
    issues = list_filtered_issues(db, district=selected_district, status=status)
    return templates.TemplateResponse(
        request,
        "district.html",
        {
            "page_title": "District cabinet",
            "issues": issues,
            "summary": build_report_summary(issues),
            "districts": DISTRICTS,
            "statuses": STATUSES,
            "selected_district": selected_district or "",
            "selected_status": status or "",
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/performance", response_class=HTMLResponse)
def performance_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    payload = get_performance_payload(db)
    return templates.TemplateResponse(
        request,
        "performance.html",
        {
            "page_title": "SLA performance",
            "payload": payload,
            "services": payload["services"],
            "districts": payload["districts"],
        },
    )


@app.get("/issues/{issue_id}", response_class=HTMLResponse)
def issue_detail(request: Request, issue_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    refresh_issue_sla(issue)
    duplicates = get_duplicate_rows(db, issue_id)
    return templates.TemplateResponse(
        request,
        "issue_detail.html",
        {
            "page_title": f"Обращение #{issue.id}",
            "issue": issue,
            "duplicates": duplicates,
            "map_points_json": json.dumps(
                [_issue_map_payload(issue)] if issue.latitude and issue.longitude else [],
                ensure_ascii=False,
            ),
            "status_history": issue.status_history,
            "statuses": STATUSES,
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "risk_labels": RISK_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.post("/issues/{issue_id}/status")
def update_status_form(
    issue_id: int,
    status: str = Form(...),
    comment: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    set_issue_status(db, issue_id, status, _clean_optional(comment))
    return RedirectResponse(url=f"/issues/{issue_id}", status_code=303)


@app.post("/issues/{issue_id}/resolution")
def upload_resolution(
    issue_id: int,
    resolution_comment: str | None = Form(default=None),
    mark_resolved: str | None = Form(default=None),
    resolution_photo: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    photo_path = _save_upload(resolution_photo)
    if photo_path:
        issue.resolution_photo_path = photo_path
    issue.resolution_comment = _clean_optional(resolution_comment)
    issue.updated_at = datetime.utcnow()
    if mark_resolved:
        old_status = issue.status
        issue.status = "resolved"
        issue.resolved_at = issue.resolved_at or issue.updated_at
        issue.sla_status = get_sla_status(issue)
        db.add(
            StatusHistory(
                issue_id=issue.id,
                old_status=old_status,
                new_status="resolved",
                comment=issue.resolution_comment or "Resolved with photo evidence",
            )
        )
    db.commit()
    return RedirectResponse(url=f"/issues/{issue_id}", status_code=303)


@app.get("/analytics", response_class=HTMLResponse)
def analytics(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    payload = get_analytics_payload(db)
    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "page_title": "Analytics",
            "payload": payload,
            "categories_json": json.dumps(payload["categories"], ensure_ascii=False),
            "districts_json": json.dumps(payload["districts"], ensure_ascii=False),
            "statuses_json": json.dumps(payload["statuses"], ensure_ascii=False),
            "avg_priority_json": json.dumps(payload["avg_priority_by_district"], ensure_ascii=False),
            "sla_json": json.dumps(payload["sla"], ensure_ascii=False),
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    district: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    issues = list_filtered_issues(db, category=category, district=district, status=status)
    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            "page_title": "Reports",
            "issues": issues,
            "summary": build_report_summary(issues),
            "categories": CATEGORIES,
            "districts": DISTRICTS,
            "statuses": STATUSES,
            "selected_category": category or "",
            "selected_district": district or "",
            "selected_status": status or "",
            "query_string": _report_query_string(district, category, status),
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/reports/print", response_class=HTMLResponse)
def report_print(
    request: Request,
    district: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    issues = list_filtered_issues(db, category=category, district=district, status=status)
    return templates.TemplateResponse(
        request,
        "report_print.html",
        {
            "page_title": "QalaPulse AI Report",
            "issues": issues,
            "summary": build_report_summary(issues),
            "generated_at": datetime.utcnow(),
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.get("/reports/district.csv")
def report_csv(
    district: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    issues = list_filtered_issues(db, category=category, district=district, status=status)
    content = build_csv_report(issues)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=qalapulse-report.csv"},
    )


@app.get("/reports/district.xlsx")
def report_xlsx(
    district: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    issues = list_filtered_issues(db, category=category, district=district, status=status)
    content = build_xlsx_report(issues)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=qalapulse-report.xlsx"},
    )


@app.get("/reports/district.pdf")
def report_pdf(
    district: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    issues = list_filtered_issues(db, category=category, district=district, status=status)
    content = build_pdf_report(issues)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=qalapulse-report.pdf"},
    )


@app.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    stats = get_stats_payload(db)
    recent = list_filtered_issues(db)[:5]
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "page_title": "Demo scenario",
            "stats": stats,
            "recent": recent,
            "category_labels": CATEGORY_LABELS,
            "district_labels": DISTRICT_LABELS,
            "status_labels": STATUS_LABELS,
            "sla_labels": SLA_LABELS,
        },
    )


@app.post("/demo/create")
def demo_create(db: Session = Depends(get_db)) -> RedirectResponse:
    issue, _ = create_issue(
        db=db,
        user_name="Demo jury",
        text="На пешеходном маршруте у остановки Мәңгілік Ел вечером не работает освещение, жителям района небезопасно проходить участок",
        address_text="Мәңгілік Ел даңғылы, Астана",
        latitude=51.107410,
        longitude=71.430107,
        category_hint=None,
        source="demo",
    )
    return RedirectResponse(url=f"/issues/{issue.id}", status_code=303)


@app.post("/demo/pitch-data")
def demo_pitch_data(db: Session = Depends(get_db)) -> RedirectResponse:
    seed_pitch_dataset(db)
    return RedirectResponse(url="/demo", status_code=303)


@app.post("/api/issues", response_model=IssueRead)
def api_create_issue(payload: IssueCreate, db: Session = Depends(get_db)) -> Issue:
    issue, _ = create_issue(
        db=db,
        user_name=payload.user_name,
        text=payload.text,
        address_text=payload.address_text,
        latitude=payload.latitude,
        longitude=payload.longitude,
        category_hint=payload.category_hint,
        source="demo",
    )
    return issue


@app.get("/api/issues", response_model=list[IssueRead])
def api_list_issues(
    category: str | None = Query(default=None),
    district: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sla: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Issue]:
    return list_filtered_issues(db, category=category, district=district, status=status, sla=sla)


@app.get("/api/issues/{issue_id}", response_model=IssueRead)
def api_get_issue(issue_id: int, db: Session = Depends(get_db)) -> Issue:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    refresh_issue_sla(issue)
    return issue


@app.patch("/api/issues/{issue_id}/status", response_model=IssueRead)
def api_update_status(issue_id: int, payload: StatusUpdate, db: Session = Depends(get_db)) -> Issue:
    return set_issue_status(db, issue_id, payload.status, payload.comment)


@app.get("/api/stats")
def api_stats(db: Session = Depends(get_db)) -> dict:
    return get_stats_payload(db)


@app.get("/api/geocode")
def api_geocode(q: str = Query(..., min_length=2)) -> list[dict]:
    query = q.lower().strip()
    matches = [
        point
        for point in GEOCODE_POINTS
        if query in point["name"].lower() or point["name"].lower() in query
    ]
    return matches[:8]


@app.get("/api/performance")
def api_performance(db: Session = Depends(get_db)) -> dict:
    return get_performance_payload(db)


@app.get("/api/analytics/categories")
def api_analytics_categories(db: Session = Depends(get_db)) -> list[dict]:
    return get_analytics_payload(db)["categories"]


@app.get("/api/analytics/districts")
def api_analytics_districts(db: Session = Depends(get_db)) -> list[dict]:
    return get_analytics_payload(db)["districts"]


@app.get("/api/issues/{issue_id}/duplicates")
def api_duplicates(issue_id: int, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(Issue, issue_id) is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return get_duplicate_rows(db, issue_id)


def get_current_user(request: Request) -> dict:
    username = request.cookies.get("qalapulse_user")
    account = DEMO_USERS.get(username or "")
    if account is None:
        return {
            "username": "guest",
            "name": "Guest",
            "role": "guest",
            "district": None,
            "service": None,
        }
    return {"username": username, **account}


def get_performance_payload(db: Session) -> dict:
    issues = db.scalars(select(Issue)).all()
    for issue in issues:
        refresh_issue_sla(issue)
    return {
        "services": _ranking_payload(issues, key=lambda issue: issue.responsible_service),
        "districts": _ranking_payload(issues, key=lambda issue: issue.district),
    }


def seed_pitch_dataset(db: Session) -> None:
    db.execute(text("DELETE FROM duplicate_links"))
    db.execute(text("DELETE FROM status_history"))
    db.execute(text("DELETE FROM issues"))
    db.commit()
    # Разнообразные городские боли Астаны + один кластер дублей (flooding на Кабанбай батыра).
    # Поля: text, address, lat, lon, category, age_hours, status
    cases = [
        (
            "На тротуаре по Абылай хана большая выбоина, пожилым людям и людям с коляской приходится выходить на проезжую часть",
            "Абылай Хан даңғылы, Астана", 51.143931, 71.513655, "roads", 90, "new",
        ),
        (
            "После дождя у перехода на Кабанбай батыра стоит большая лужа, обойти можно только по проезжей части",
            "Қабанбай Батыр даңғылы, Астана", 51.141153, 71.418741, "flooding", 30, "new",
        ),
        (
            "На Кабанбай батыра возле остановки вода не уходит после осадков, пешеходам приходится перепрыгивать поток",
            "Қабанбай Батыр даңғылы, Астана", 51.141286, 71.418935, "flooding", 28, "in_progress",
        ),
        (
            "Тротуар вдоль Сарыарка не чистят ото льда, утром люди скользят и падают по пути к остановке",
            "Сарыарқа даңғылы, Астана", 51.172011, 71.407279, "snow_ice", 18, "new",
        ),
        (
            "Контейнерная площадка на Бейбітшілік переполнена третий день, мусор разносит ветром по двору",
            "Бейбітшілік көшесі, Астана", 51.176639, 71.417130, "trash", 40, "new",
        ),
        (
            "В доме на Момышулы вторые сутки нет горячей воды, аварийная бригада не приезжает по заявкам",
            "Бауыржан Момышұлы даңғылы, Астана", 51.139382, 71.478820, "utilities", 38, "in_progress",
        ),
        (
            "На нерегулируемом переходе у Туран стёрлась разметка и не работает подсветка, водители не успевают заметить пешеходов",
            "Тұран даңғылы, Астана", 51.141908, 71.410526, "safety", 54, "new",
        ),
        (
            "На остановке возле Мәңгілік Ел нет информации о прибытии автобусов, пассажиры долго ждут без понимания времени",
            "Мәңгілік Ел даңғылы, Астана", 51.107410, 71.430107, "transport", 12, "resolved",
        ),
        (
            "От коллектора у Кенесары по вечерам идёт резкий запах канализации, окна приходится держать закрытыми",
            "Кенесары көшесі, Астана", 51.164377, 71.458145, "smell_ecology", 80, "rejected",
        ),
    ]
    for text_value, address, lat, lon, category, age_hours, status in cases:
        issue, _ = create_issue(
            db=db,
            user_name="Pitch demo",
            text=text_value,
            address_text=address,
            latitude=lat,
            longitude=lon,
            category_hint=category,
            source="demo",
            created_at=datetime.utcnow() - timedelta(hours=age_hours),
        )
        if status != "new":
            set_issue_status(db, issue.id, status, "Pitch scenario demo status")


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "issues" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("issues")}
    dialect = engine.dialect.name
    specs = {
        "photo_evidence": "BOOLEAN DEFAULT false" if dialect != "sqlite" else "BOOLEAN DEFAULT 0",
        "ai_confidence": "INTEGER DEFAULT 70",
        "responsible_service": "VARCHAR(120) DEFAULT 'City Operations Center'",
        "sla_due_at": "TIMESTAMP NULL" if dialect != "sqlite" else "DATETIME",
        "sla_status": "VARCHAR(24) DEFAULT 'on_track'",
        "resolution_photo_path": "VARCHAR(255)",
        "resolution_comment": "TEXT",
        "ai_mode": "VARCHAR(32) DEFAULT 'rule_based'",
        "assigned_to": "VARCHAR(120)",
        "resolved_at": "TIMESTAMP NULL" if dialect != "sqlite" else "DATETIME",
    }
    with engine.begin() as connection:
        for column, ddl in specs.items():
            if column not in existing:
                connection.execute(text(f"ALTER TABLE issues ADD COLUMN {column} {ddl}"))


def create_issue(
    db: Session,
    user_name: str | None,
    text: str,
    address_text: str | None,
    latitude: float | None,
    longitude: float | None,
    category_hint: str | None = None,
    photo_path: str | None = None,
    source: str = "web",
    created_at: datetime | None = None,
) -> tuple[Issue, list[DuplicateCandidate]]:
    created_at = created_at or datetime.utcnow()
    analysis = analyze_issue_mvp(
        text=text,
        latitude=latitude,
        longitude=longitude,
        image_path=photo_path,
        created_at=created_at,
        category_hint=category_hint,
    )
    existing_issues = db.scalars(select(Issue)).all()
    duplicate_candidates = find_duplicates(
        new_text=text,
        category=analysis.category,
        latitude=latitude,
        longitude=longitude,
        existing_issues=existing_issues,
    )
    analysis = apply_duplicate_bonus(analysis, len(duplicate_candidates))
    issue = _issue_from_analysis(
        analysis=analysis,
        user_name=user_name,
        text=text,
        address_text=address_text,
        latitude=latitude,
        longitude=longitude,
        photo_path=photo_path,
        source=source,
        created_at=created_at,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    for candidate in duplicate_candidates:
        db.add(
            DuplicateLink(
                issue_id=issue.id,
                duplicate_issue_id=candidate.issue_id,
                similarity_score=candidate.similarity_score,
                distance_meters=candidate.distance_meters,
            )
        )
    db.commit()
    db.refresh(issue)
    return issue, duplicate_candidates


def set_issue_status(db: Session, issue_id: int, status: str, comment: str | None = None) -> Issue:
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    old_status = issue.status
    if old_status != status:
        issue.status = status
        issue.updated_at = datetime.utcnow()
        if status == "resolved":
            issue.resolved_at = issue.resolved_at or issue.updated_at
        elif old_status == "resolved":
            issue.resolved_at = None
        issue.sla_status = get_sla_status(issue)
        db.add(
            StatusHistory(
                issue_id=issue.id,
                old_status=old_status,
                new_status=status,
                comment=comment,
            )
        )
        db.commit()
        db.refresh(issue)
    return issue


def list_filtered_issues(
    db: Session,
    category: str | None = None,
    district: str | None = None,
    status: str | None = None,
    sla: str | None = None,
    service: str | None = None,
) -> list[Issue]:
    query = select(Issue)
    if category:
        query = query.where(Issue.category == category)
    if district:
        query = query.where(Issue.district == district)
    if status:
        query = query.where(Issue.status == status)
    if service:
        query = query.where(Issue.responsible_service == service)
    query = query.order_by(Issue.priority_score.desc(), Issue.created_at.desc())
    issues = list(db.scalars(query).all())
    for issue in issues:
        refresh_issue_sla(issue)
    if sla:
        issues = [issue for issue in issues if issue.sla_status == sla]
    return issues


def get_stats_payload(db: Session) -> dict:
    issues = db.scalars(select(Issue)).all()
    for issue in issues:
        refresh_issue_sla(issue)
    total = len(issues)
    status_counter = Counter(issue.status for issue in issues)
    sla_counter = Counter(issue.sla_status for issue in issues)
    avg_priority = round(sum(issue.priority_score for issue in issues) / total, 1) if total else 0
    avg_confidence = round(sum(issue.ai_confidence for issue in issues) / total, 1) if total else 0
    return {
        "total": total,
        "new": status_counter.get("new", 0),
        "in_progress": status_counter.get("in_progress", 0),
        "resolved": status_counter.get("resolved", 0),
        "rejected": status_counter.get("rejected", 0),
        "avg_priority": avg_priority,
        "avg_confidence": avg_confidence,
        "high_risk": sum(1 for issue in issues if issue.risk_level == "high"),
        "overdue": sla_counter.get("overdue", 0),
        "due_soon": sla_counter.get("due_soon", 0),
        "photo_evidence": sum(1 for issue in issues if issue.photo_evidence),
    }


def get_analytics_payload(db: Session) -> dict:
    issues = db.scalars(select(Issue)).all()
    for issue in issues:
        refresh_issue_sla(issue)
    category_counter = Counter(issue.category for issue in issues)
    district_counter = Counter(issue.district for issue in issues)
    status_counter = Counter(issue.status for issue in issues)
    sla_counter = Counter(issue.sla_status for issue in issues)
    district_scores: dict[str, list[int]] = defaultdict(list)
    zone_scores: dict[str, list[int]] = defaultdict(list)
    zone_counts: Counter[str] = Counter()

    for issue in issues:
        district_scores[issue.district].append(issue.priority_score)
        lat_part = f"{issue.latitude:.3f}" if issue.latitude is not None else "no-lat"
        lon_part = f"{issue.longitude:.3f}" if issue.longitude is not None else "no-lon"
        zone_key = f"{issue.district} · {CATEGORY_LABELS.get(issue.category, issue.category)} · {lat_part}, {lon_part}"
        zone_counts[zone_key] += 1
        zone_scores[zone_key].append(issue.priority_score)

    top_zones = [
        {
            "zone": zone,
            "count": count,
            "avg_priority": round(sum(zone_scores[zone]) / len(zone_scores[zone]), 1),
        }
        for zone, count in zone_counts.most_common(10)
    ]

    return {
        "categories": _counter_payload(category_counter, CATEGORY_LABELS),
        "districts": _counter_payload(district_counter, DISTRICT_LABELS),
        "statuses": _counter_payload(status_counter, STATUS_LABELS),
        "sla": _counter_payload(sla_counter, SLA_LABELS),
        "top_zones": top_zones,
        "avg_priority_by_district": [
            {
                "label": DISTRICT_LABELS.get(district, district),
                "value": round(sum(scores) / len(scores), 1),
            }
            for district, scores in sorted(district_scores.items())
            if scores
        ],
    }


def get_duplicate_counts(db: Session) -> dict[int, int]:
    links = db.scalars(select(DuplicateLink)).all()
    counts: Counter[int] = Counter()
    for link in links:
        counts[link.issue_id] += 1
        counts[link.duplicate_issue_id] += 1
    return dict(counts)


def get_duplicate_rows(db: Session, issue_id: int) -> list[dict]:
    links = db.scalars(
        select(DuplicateLink).where(
            or_(DuplicateLink.issue_id == issue_id, DuplicateLink.duplicate_issue_id == issue_id)
        )
    ).all()
    rows = []
    for link in links:
        duplicate_id = link.duplicate_issue_id if link.issue_id == issue_id else link.issue_id
        duplicate_issue = db.get(Issue, duplicate_id)
        if duplicate_issue is None:
            continue
        refresh_issue_sla(duplicate_issue)
        rows.append(
            {
                "issue": duplicate_issue,
                "similarity_score": link.similarity_score,
                "distance_meters": link.distance_meters,
            }
        )
    return sorted(rows, key=lambda row: row["similarity_score"], reverse=True)


def build_report_summary(issues: list[Issue]) -> dict:
    total = len(issues)
    return {
        "total": total,
        "high_risk": sum(1 for issue in issues if issue.risk_level == "high"),
        "overdue": sum(1 for issue in issues if issue.sla_status == "overdue"),
        "avg_priority": round(sum(issue.priority_score for issue in issues) / total, 1) if total else 0,
        "avg_confidence": round(sum(issue.ai_confidence for issue in issues) / total, 1) if total else 0,
        "services": Counter(issue.responsible_service for issue in issues).most_common(5),
    }


def build_csv_report(issues: list[Issue]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(report_headers())
    for issue in issues:
        writer.writerow(report_row(issue))
    return "\ufeff" + output.getvalue()


def build_xlsx_report(issues: list[Issue]) -> bytes:
    rows = [report_headers()] + [report_row(issue) for issue in issues]
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            cell_ref = f"{_excel_col(col_index)}{row_index}"
            value_text = escape("" if value is None else str(value))
            cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{value_text}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        + "".join(sheet_rows)
        + "</sheetData></worksheet>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="QalaPulse Report" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def build_pdf_report(issues: list[Issue]) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Install reportlab to generate PDF reports.") from exc

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = _register_pdf_font(pdfmetrics, TTFont)
    y = height - 48

    def draw(line: str, size: int = 10, bold: bool = False) -> None:
        nonlocal y
        if y < 48:
            pdf.showPage()
            y = height - 48
        pdf.setFont(font_name, size)
        pdf.drawString(42, y, line[:115])
        y -= 16 if not bold else 20

    summary = build_report_summary(issues)
    draw("QalaPulse AI report", 16, True)
    draw(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    draw(f"Total: {summary['total']} | High-risk: {summary['high_risk']} | Overdue: {summary['overdue']}")
    draw(f"Avg priority: {summary['avg_priority']} | Avg AI confidence: {summary['avg_confidence']}%")
    y -= 10
    for issue in issues[:45]:
        line = (
            f"#{issue.id} {CATEGORY_LABELS.get(issue.category, issue.category)} · "
            f"{DISTRICT_LABELS.get(issue.district, issue.district)} · "
            f"{issue.priority_score}/100 · {SLA_LABELS.get(issue.sla_status, issue.sla_status)}"
        )
        draw(line, 10, True)
        for wrapped in textwrap.wrap(issue.summary, width=92):
            draw(f"  {wrapped}", 9)
        draw(f"  Service: {issue.responsible_service}", 9)
        y -= 4
    pdf.save()
    return buffer.getvalue()


def report_headers() -> list[str]:
    return [
        "id",
        "summary",
        "category",
        "district",
        "priority_score",
        "risk_level",
        "ai_confidence",
        "ai_mode",
        "responsible_service",
        "assigned_to",
        "sla_due_at",
        "sla_status",
        "status",
        "resolved_at",
        "latitude",
        "longitude",
        "created_at",
    ]


def report_row(issue: Issue) -> list:
    return [
        issue.id,
        issue.summary,
        CATEGORY_LABELS.get(issue.category, issue.category),
        DISTRICT_LABELS.get(issue.district, issue.district),
        issue.priority_score,
        RISK_LABELS.get(issue.risk_level, issue.risk_level),
        issue.ai_confidence,
        issue.ai_mode,
        issue.responsible_service,
        issue.assigned_to,
        issue.sla_due_at.strftime("%Y-%m-%d %H:%M") if issue.sla_due_at else "",
        SLA_LABELS.get(issue.sla_status, issue.sla_status),
        STATUS_LABELS.get(issue.status, issue.status),
        issue.resolved_at.strftime("%Y-%m-%d %H:%M") if issue.resolved_at else "",
        issue.latitude,
        issue.longitude,
        issue.created_at.strftime("%Y-%m-%d %H:%M"),
    ]


def refresh_issue_sla(issue: Issue) -> None:
    issue.responsible_service = issue.responsible_service or service_for_category(issue.category)
    issue.sla_due_at = issue.sla_due_at or compute_sla_due_at(issue.created_at, issue.risk_level, issue.category)
    issue.sla_status = get_sla_status(issue)


def service_for_category(category: str) -> str:
    return SERVICE_BY_CATEGORY.get(category, SERVICE_BY_CATEGORY["other"])


def compute_sla_due_at(created_at: datetime, risk_level: str, category: str) -> datetime:
    hours = SLA_HOURS_BY_RISK.get(risk_level, 168)
    if risk_level == "high" and category in URGENT_CATEGORY_HOURS:
        hours = min(hours, URGENT_CATEGORY_HOURS[category])
    return created_at + timedelta(hours=hours)


def get_sla_status(issue: Issue, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    if issue.status in {"resolved", "rejected"}:
        return "closed"
    if issue.sla_due_at is None:
        return "not_set"
    if issue.sla_due_at < now:
        return "overdue"
    if issue.sla_due_at - now <= timedelta(hours=12):
        return "due_soon"
    return "on_track"


def _issue_from_analysis(
    analysis: AnalysisResult,
    user_name: str | None,
    text: str,
    address_text: str | None,
    latitude: float | None,
    longitude: float | None,
    photo_path: str | None,
    source: str,
    created_at: datetime,
) -> Issue:
    responsible_service = service_for_category(analysis.category)
    sla_due_at = compute_sla_due_at(created_at, analysis.risk_level, analysis.category)
    return Issue(
        source=source,
        user_name=user_name,
        text=text,
        summary=analysis.summary,
        category=analysis.category,
        district=analysis.district,
        latitude=latitude,
        longitude=longitude,
        address_text=address_text,
        photo_path=photo_path,
        photo_evidence=analysis.photo_evidence,
        priority_score=analysis.priority_score,
        risk_level=analysis.risk_level,
        ai_confidence=analysis.confidence,
        ai_mode=analysis.mode,
        ai_explanation=analysis.explanation,
        tags=analysis.tags,
        responsible_service=responsible_service,
        assigned_to=responsible_service,
        sla_due_at=sla_due_at,
        sla_status="on_track" if sla_due_at >= created_at else "overdue",
        status="new",
        created_at=created_at,
        updated_at=created_at,
    )


def _save_upload(photo: UploadFile | None) -> str | None:
    if photo is None or not photo.filename:
        return None
    suffix = Path(photo.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    filename = f"{uuid4().hex}{suffix}"
    destination = UPLOAD_DIR / filename
    with destination.open("wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)
    return f"/static/uploads/{filename}"


def _parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_category_hint(value: str | None) -> str | None:
    value = _clean_optional(value)
    return value if value in CATEGORIES else None


def _issue_map_payload(issue: Issue, duplicate_count: int = 0) -> dict:
    return {
        "id": issue.id,
        "summary": issue.summary,
        "text": issue.text[:180],
        "category": issue.category,
        "category_label": CATEGORY_LABELS.get(issue.category, issue.category),
        "district": issue.district,
        "district_label": DISTRICT_LABELS.get(issue.district, issue.district),
        "status": issue.status,
        "status_label": STATUS_LABELS.get(issue.status, issue.status),
        "risk_level": issue.risk_level,
        "priority_score": issue.priority_score,
        "ai_confidence": issue.ai_confidence,
        "ai_mode": issue.ai_mode,
        "responsible_service": issue.responsible_service,
        "sla_status": issue.sla_status,
        "sla_label": SLA_LABELS.get(issue.sla_status, issue.sla_status),
        "duplicate_count": duplicate_count,
        "latitude": issue.latitude,
        "longitude": issue.longitude,
        "heat_weight": round(max(0.25, issue.priority_score / 100), 2),
        "url": f"/issues/{issue.id}",
    }


def _counter_payload(counter: Counter, labels: dict[str, str]) -> list[dict]:
    return [
        {"key": key, "label": labels.get(key, key), "value": value}
        for key, value in counter.most_common()
    ]


def _ranking_payload(issues: list[Issue], key) -> list[dict]:
    groups: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        groups[key(issue) or "Unknown"].append(issue)
    rows = []
    for label, items in groups.items():
        total = len(items)
        resolved = [issue for issue in items if issue.status == "resolved"]
        closed = [issue for issue in items if issue.status in {"resolved", "rejected"}]
        overdue_open = [issue for issue in items if issue.sla_status == "overdue"]
        on_time_closed = [
            issue
            for issue in closed
            if issue.resolved_at is None or issue.sla_due_at is None or issue.resolved_at <= issue.sla_due_at
        ]
        avg_resolution = 0.0
        resolved_with_times = [issue for issue in resolved if issue.resolved_at]
        if resolved_with_times:
            avg_resolution = round(
                sum((issue.resolved_at - issue.created_at).total_seconds() / 3600 for issue in resolved_with_times)
                / len(resolved_with_times),
                1,
            )
        rows.append(
            {
                "label": label,
                "total": total,
                "resolved": len(resolved),
                "open": sum(1 for issue in items if issue.status in {"new", "in_progress"}),
                "overdue": len(overdue_open),
                "on_time_rate": round(len(on_time_closed) / len(closed) * 100, 1) if closed else 0,
                "avg_priority": round(sum(issue.priority_score for issue in items) / total, 1) if total else 0,
                "avg_resolution_hours": avg_resolution,
            }
        )
    return sorted(rows, key=lambda row: (row["overdue"], row["avg_priority"]), reverse=True)


def _excel_col(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _register_pdf_font(pdfmetrics, TTFont) -> str:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("QalaPulseFont", str(path)))
            return "QalaPulseFont"
    return "Helvetica"


def _report_query_string(district: str | None, category: str | None, status: str | None) -> str:
    params = []
    if district:
        params.append(f"district={district}")
    if category:
        params.append(f"category={category}")
    if status:
        params.append(f"status={status}")
    return "&".join(params)
