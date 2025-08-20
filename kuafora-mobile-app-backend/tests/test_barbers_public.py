import pytest
from rest_framework.test import APIClient
from model_bakery import baker


@pytest.mark.django_db
def test_public_list_barbershops_filtered_by_gender():
    male_shop = baker.make("barbers.Barbershop", gender="male")
    female_shop = baker.make("barbers.Barbershop", gender="female")
    unisex_shop = baker.make("barbers.Barbershop", gender="unisex")

    client = APIClient()

    # Anonymous should see all (no gender constraint without auth)
    r = client.get("/api/barbershops")
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()}
    assert male_shop.id in ids and female_shop.id in ids and unisex_shop.id in ids


