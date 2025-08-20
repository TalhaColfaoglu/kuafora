import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_login_me_flow():
    client = APIClient()
    # Register
    payload = {
        "full_name": "Test User",
        "email": "user@example.com",
        "password": "StrongPass123",
        "gender": "male",
        "phone": "+901234567890",
    }
    r = client.post("/api/auth/register", payload, format="json")
    assert r.status_code == 201

    # Login
    r = client.post("/api/auth/login", {"email": payload["email"], "password": payload["password"]}, format="json")
    assert r.status_code == 200
    tokens = r.json()
    assert "access" in tokens and "refresh" in tokens

    # Me
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == payload["email"]

    # Change password
    r = client.patch("/api/auth/change-password", {"old_password": payload["password"], "new_password": "NewStrongPass123"}, format="json")
    assert r.status_code == 200


