"""
World Cup 2026 — Ticketing API
FastAPI microservice for managing match tickets, reservations, and validations.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import time

app = FastAPI(
    title="World Cup 2026 Ticketing API",
    description="Manages match tickets, reservations, and validations for FIFA World Cup 2026",
    version="1.0.0"
)

# --- Constants ---
TOKEN_EXPIRY_SECONDS = 360  # BUG: Should be 3600 (1 hour), typo causes tokens to expire in 6 minutes
MAX_TICKETS_PER_USER = 4
TICKET_CATEGORIES = ["Category 1", "Category 2", "Category 3", "Category 4"]

# --- Models ---
class TicketRequest(BaseModel):
    match_id: str
    category: str
    quantity: int
    user_id: str

class TicketResponse(BaseModel):
    ticket_id: str
    match_id: str
    category: str
    quantity: int
    user_id: str
    auth_token: str
    expires_at: str
    status: str

# --- In-Memory Store (demo) ---
tickets_db: dict = {}

# --- Auth Helpers ---
def generate_auth_token(user_id: str, match_id: str) -> str:
    """Generate a secure auth token for ticket validation."""
    payload = f"{user_id}:{match_id}:{time.time()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]

def validate_auth_token(token: str, created_at: datetime) -> bool:
    """Validate that an auth token has not expired."""
    expiry_time = created_at + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
    return datetime.utcnow() < expiry_time

# --- Endpoints ---
@app.get("/")
def root():
    return {"service": "World Cup 2026 Ticketing API", "version": "1.0.0", "status": "operational"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/tickets/reserve", response_model=TicketResponse)
def reserve_ticket(request: TicketRequest):
    """Reserve tickets for a World Cup match."""
    if request.category not in TICKET_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {TICKET_CATEGORIES}")
    
    if request.quantity < 1 or request.quantity > MAX_TICKETS_PER_USER:
        raise HTTPException(status_code=400, detail=f"Quantity must be between 1 and {MAX_TICKETS_PER_USER}")
    
    ticket_id = f"WC26-{request.match_id}-{hashlib.md5(f'{request.user_id}{time.time()}'.encode()).hexdigest()[:8].upper()}"
    auth_token = generate_auth_token(request.user_id, request.match_id)
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(seconds=TOKEN_EXPIRY_SECONDS)
    
    ticket = TicketResponse(
        ticket_id=ticket_id,
        match_id=request.match_id,
        category=request.category,
        quantity=request.quantity,
        user_id=request.user_id,
        auth_token=auth_token,
        expires_at=expires_at.isoformat(),
        status="reserved"
    )
    
    tickets_db[ticket_id] = {**ticket.dict(), "created_at": created_at}
    return ticket

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    """Retrieve ticket details by ID."""
    if ticket_id not in tickets_db:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return tickets_db[ticket_id]

@app.post("/tickets/{ticket_id}/validate")
def validate_ticket(ticket_id: str):
    """Validate a ticket for venue entry."""
    if ticket_id not in tickets_db:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = tickets_db[ticket_id]
    created_at = ticket["created_at"]
    
    if not validate_auth_token(ticket["auth_token"], created_at):
        raise HTTPException(status_code=401, detail="Auth token expired. Please re-authenticate.")
    
    ticket["status"] = "validated"
    return {"message": "Ticket validated successfully", "ticket_id": ticket_id, "status": "validated"}

@app.get("/matches/{match_id}/availability")
def check_availability(match_id: str):
    """Check ticket availability for a specific match."""
    return {
        "match_id": match_id,
        "availability": {
            "Category 1": {"available": 5000, "total": 10000, "price": 750},
            "Category 2": {"available": 12000, "total": 20000, "price": 450},
            "Category 3": {"available": 18000, "total": 30000, "price": 250},
            "Category 4": {"available": 8000, "total": 15000, "price": 100},
        }
    }
