import pytest
from django.urls import reverse

from nfctags import get_nfctag_model
from domain.services import NFCTagService


@pytest.mark.django_db
def test_list_parity(client, django_user_model):
    user = django_user_model.objects.create_user("u", "u@example.com", "p")
    client.login(username="u", password="p")

    NFCTag = get_nfctag_model()
    service = NFCTagService(user=user)
    t1 = service.create_tag(uid="AAA")
    t2 = service.create_tag(uid="BBB")

    # HTML list view (ensure this matches your urlpattern name)
    resp_html = client.get(reverse("domain:list_nfctags"))
    assert resp_html.status_code == 200
    html_items = {str(t.uuid) for t in resp_html.context["nfctags"]}

    # API list (if session auth isn’t enabled for /api in prod, attach a JWT in a helper)
    resp_api = client.get("/api/nfctags?limit=100")
    assert resp_api.status_code == 200
    api_items = {i["uuid"] for i in resp_api.json()["items"]}

    assert html_items == api_items


@pytest.mark.django_db
def test_detail_parity(client, django_user_model):
    user = django_user_model.objects.create_user("u2", "u2@example.com", "p")
    client.login(username="u2", password="p")

    service = NFCTagService(user=user)
    tag = service.create_tag(uid="CCC")

    # HTML detail view
    resp_html = client.get(reverse("domain:view_nfctag", args=[str(tag.uuid)]))
    assert resp_html.status_code == 200
    html_uuid = str(resp_html.context["nfctag"].uuid)

    # API detail
    resp_api = client.get(f"/api/nfctags/{tag.uuid}")
    assert resp_api.status_code == 200
    api_uuid = resp_api.json()["uuid"]

    assert html_uuid == api_uuid
