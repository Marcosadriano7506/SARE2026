def test_public_oauth_branding_pages_are_accessible_without_login(client):
    about = client.get("/sobre")
    privacy = client.get("/privacidade")
    terms = client.get("/termos")

    assert about.status_code == 200
    assert privacy.status_code == 200
    assert terms.status_code == 200

    about_body = about.get_data(as_text=True)
    privacy_body = privacy.get_data(as_text=True)

    assert "SARE" in about_body
    assert "Sistema de Avaliação Riachense de Educação" in about_body
    assert "/privacidade" in about_body
    assert "Finalidade do aplicativo" in about_body

    assert "Dados do Google acessados pelo aplicativo" in privacy_body
    assert "Como os dados obtidos do Google são utilizados" in privacy_body
    assert "Retenção e exclusão" in privacy_body
    assert "Revogação do acesso ao Google" in privacy_body
    assert "Uso limitado de dados das APIs do Google" in privacy_body
