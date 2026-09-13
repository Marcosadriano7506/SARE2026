def test_service_worker_is_available_at_root_scope(client):
    response = client.get("/sw.js")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert response.headers["Cache-Control"] == "no-cache"
    assert b"sare-shell" in response.data


def test_manifest_is_served_as_static_asset(client):
    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    assert b'"short_name": "SARE"' in response.data
