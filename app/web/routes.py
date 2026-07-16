"""Server-rendered page adapters; templates and page URLs remain unchanged."""
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.repositories.users import UserRepository
from app.schemas.tickets import TicketIn
from app.services.tickets import TicketService

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"title": "Dashboard"})


@router.get("/tickets", response_class=HTMLResponse)
def tickets_page(request: Request):
    return templates.TemplateResponse(request, "tickets.html", {"title": "Tickets"})


@router.get("/tickets/new", response_class=HTMLResponse)
def ticket_new(request: Request):
    return templates.TemplateResponse(request, "ticket_form.html", {"title": "New ticket"})


@router.post("/tickets/new")
def ticket_create(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form("General"),
    priority: str = Form("Medium"),
):
    with request.app.state.session_factory() as db:
        requester = UserRepository(db).by_email("requester@example.com")
        if requester is None:
            raise HTTPException(status_code=500, detail="Demo requester user is missing")
        ticket = TicketService(db).create(TicketIn(title=title, description=description, category=category, priority=priority), requester)
    return RedirectResponse(url=f"/tickets/{ticket['id']}", status_code=303)


@router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_page(ticket_id: int, request: Request):
    ticket = None
    with request.app.state.session_factory() as db:
        requester = UserRepository(db).by_email("requester@example.com")
        if requester is not None:
            try:
                ticket = TicketService(db).detail(ticket_id, requester)
            except HTTPException:
                ticket = None
    return templates.TemplateResponse(request, "ticket_detail.html", {"title": "Ticket detail", "ticket_id": ticket_id, "ticket": ticket})


@router.get("/knowledge-base", response_class=HTMLResponse)
def kb_page(request: Request):
    return templates.TemplateResponse(request, "knowledge_base.html", {"title": "Knowledge base"})
