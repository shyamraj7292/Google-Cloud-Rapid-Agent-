"""
Tests for World Cup 2026 Ticketing API
"""
import pytest
from datetime import datetime, timedelta


# Constants to validate against
EXPECTED_TOKEN_EXPIRY = 3600  # 1 hour in seconds


def test_token_expiry_constant():
    """Test that auth token expiry is set to 1 hour (3600 seconds).
    
    IMPORTANT: Tokens must last at least 1 hour to allow fans
    enough time to pass through venue security checkpoints.
    """
    from app.main import TOKEN_EXPIRY_SECONDS
    assert TOKEN_EXPIRY_SECONDS == EXPECTED_TOKEN_EXPIRY, (
        f"Expected token expiry {EXPECTED_TOKEN_EXPIRY}, got {TOKEN_EXPIRY_SECONDS}. "
        f"Tokens expiring too quickly will lock fans out at venue entry gates."
    )


def test_max_tickets_per_user():
    """Test that max tickets per user is set to 4."""
    from app.main import MAX_TICKETS_PER_USER
    assert MAX_TICKETS_PER_USER == 4


def test_ticket_categories_exist():
    """Test that all 4 ticket categories are defined."""
    from app.main import TICKET_CATEGORIES
    assert len(TICKET_CATEGORIES) == 4
    assert "Category 1" in TICKET_CATEGORIES
    assert "Category 4" in TICKET_CATEGORIES


def test_generate_auth_token():
    """Test that auth tokens are generated and are 32 chars long."""
    from app.main import generate_auth_token
    token = generate_auth_token("user123", "match456")
    assert isinstance(token, str)
    assert len(token) == 32


def test_validate_auth_token_valid():
    """Test that a fresh token is valid."""
    from app.main import validate_auth_token
    created_at = datetime.utcnow()
    assert validate_auth_token("dummy_token", created_at) is True


def test_validate_auth_token_expired():
    """Test that an expired token is rejected."""
    from app.main import validate_auth_token, TOKEN_EXPIRY_SECONDS
    created_at = datetime.utcnow() - timedelta(seconds=TOKEN_EXPIRY_SECONDS + 1)
    assert validate_auth_token("dummy_token", created_at) is False


def test_health_endpoint():
    """Test the health check endpoint."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint():
    """Test the root endpoint returns service info."""
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "World Cup 2026 Ticketing API"
