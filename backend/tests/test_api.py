import httpx

from app.schemas.analysis import RequirementMatch
from app.services.scoring import compute_score
from tests.conftest import OFFER_TEXT


async def create_offer(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.post("/api/offers", json={"raw_text": OFFER_TEXT})
    assert response.status_code == 201, response.text
    data: dict[str, object] = response.json()
    return data


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.json() == {"status": "ok"}


async def test_offer_needs_a_cv_first(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/offers", json={"raw_text": OFFER_TEXT})
    assert response.status_code == 409


async def test_cv_upload_as_text_and_file(client: httpx.AsyncClient, cv: dict[str, object]) -> None:
    assert cv["chunks"] == 2
    current = await client.get("/api/cv")
    assert current.json()["id"] == cv["id"]

    files = {
        "file": ("cv.txt", b"Python developer with Django and Docker experience.", "text/plain")
    }
    uploaded = await client.post("/api/cv", files=files)
    assert uploaded.status_code == 201
    assert (await client.get("/api/cv")).json()["id"] == uploaded.json()["id"]


async def test_empty_cv_file_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/cv", files={"file": ("cv.txt", b"   ", "text/plain")})
    assert response.status_code == 422


async def test_offer_analysis(client: httpx.AsyncClient, cv: dict[str, object]) -> None:
    offer = await create_offer(client)
    analysis = offer["analysis"]
    assert isinstance(analysis, dict)
    status = {m["name"]: m["status"] for m in analysis["matches"]}
    assert status["Python"] == status["Django"] == status["Docker"] == "met"
    assert status["Kubernetes"] == status["AWS"] == "missing"
    assert analysis["salary"]["monthly_min"] == 6720
    assert analysis["salary"]["contract"] == "b2b"
    matches = [RequirementMatch.model_validate(m) for m in analysis["matches"]]
    assert analysis["score"] == compute_score(matches)
    assert 50 < analysis["score"] < 100
    assert offer["status"] == "to_apply"

    listed = (await client.get("/api/offers")).json()
    assert [o["id"] for o in listed] == [offer["id"]]
    detail = (await client.get(f"/api/offers/{offer['id']}")).json()
    assert detail["analysis"]["score"] == analysis["score"]


async def test_cover_letter(client: httpx.AsyncClient, cv: dict[str, object]) -> None:
    offer = await create_offer(client)
    pl = await client.post(f"/api/offers/{offer['id']}/cover-letter", json={"language": "pl"})
    en = await client.post(f"/api/offers/{offer['id']}/cover-letter", json={"language": "en"})
    assert "Example Fintech" in pl.json()["text"]
    assert pl.json()["text"].startswith("Szanowni")
    assert en.json()["text"].startswith("Dear")


async def test_ask_the_agent(client: httpx.AsyncClient, cv: dict[str, object]) -> None:
    offer = await create_offer(client)
    response = await client.post(
        f"/api/offers/{offer['id']}/ask", json={"question": "Docker experience"}
    )
    body = response.json()
    assert [s["tool"] for s in body["steps"]] == ["search_cv"]
    assert "Docker" in body["answer"]


async def test_application_board(client: httpx.AsyncClient, cv: dict[str, object]) -> None:
    offer = await create_offer(client)
    [application] = (await client.get("/api/applications")).json()
    assert application["offer_id"] == offer["id"]

    patched = await client.patch(
        f"/api/applications/{application['id']}",
        json={"status": "applied", "notes": "Sent on Monday"},
    )
    assert patched.json()["status"] == "applied"
    assert patched.json()["notes"] == "Sent on Monday"

    invalid = await client.patch(f"/api/applications/{application['id']}", json={"status": "x"})
    assert invalid.status_code == 422

    await client.delete(f"/api/offers/{offer['id']}")
    assert (await client.get("/api/applications")).json() == []


async def test_unknown_ids_return_404(client: httpx.AsyncClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/api/offers/{missing}")).status_code == 404
    assert (await client.patch(f"/api/applications/{missing}", json={})).status_code == 404
