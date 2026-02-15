import jwt
import pytest
from django.urls import reverse
from django.conf import settings

from nfctags import get_nfctag_model
from domain.services import NFCTagService


def create_test_jwt_token(user):
    """
    Create a test JWT token for a user.

    Uses the ID service's RS256 private key to sign the token.
    The token is valid for 1 hour in tests.
    """
    from pathlib import Path

    # Load the ID service's private key for signing test tokens
    private_key_path = Path(__file__).resolve().parent.parent.parent / "id" / "backend" / "config" / "keys" / "jwt_private_key.pem"

    try:
        with open(private_key_path) as f:
            private_key = f.read()
    except FileNotFoundError:
        pytest.skip("ID service private key not found for test token generation")

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "uuid": str(user.id),  # Using user ID as UUID for testing
        "iat": 1234567890,
        "exp": 1234571490,  # 1 hour later
    }

    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.mark.django_db
def test_list_parity(client, django_user_model):
    user = django_user_model.objects.create_user("u", "u@example.com", "p")
    client.login(username="u", password="p")

    NFCTag = get_nfctag_model()
    service = NFCTagService(user=user)
    t1 = service.create_tag(uid="AAA")
    t2 = service.create_tag(uid="BBB")

    # HTML list view (uses session auth via @login_required)
    resp_html = client.get(reverse("domain:list_nfctags"))
    assert resp_html.status_code == 200
    html_items = {str(t.uuid) for t in resp_html.context["nfctags"]}

    # API list (uses JWT token in Authorization header)
    token = create_test_jwt_token(user)
    resp_api = client.get("/api/nfctags?limit=100", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp_api.status_code == 200
    api_items = {i["uuid"] for i in resp_api.json()["items"]}

    assert html_items == api_items


@pytest.mark.django_db
def test_detail_parity(client, django_user_model):
    user = django_user_model.objects.create_user("u2", "u2@example.com", "p")
    client.login(username="u2", password="p")

    service = NFCTagService(user=user)
    tag = service.create_tag(uid="CCC")

    # HTML detail view (uses session auth via @login_required)
    resp_html = client.get(reverse("domain:view_nfctag", args=[str(tag.uuid)]))
    assert resp_html.status_code == 200
    html_uuid = str(resp_html.context["nfctag"].uuid)

    # API detail (uses JWT token in Authorization header)
    token = create_test_jwt_token(user)
    resp_api = client.get(f"/api/nfctags/{tag.uuid}", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp_api.status_code == 200
    api_uuid = resp_api.json()["uuid"]

    assert html_uuid == api_uuid
