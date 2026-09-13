# SARE 2026 — Sistema de Aplicação e Resultados

Aplicação web independente para coleta, acompanhamento e consolidação dos resultados do SARE.

## Objetivo

Digitalizar o fluxo de aplicação da avaliação, desde a identificação da turma e lançamento das respostas pelo aplicador até o monitoramento pela coordenação, geração de comprovante PDF, consolidação dos resultados e exportações oficiais.

## Stack inicial

- Python 3.12
- Flask
- PostgreSQL (Supabase no ambiente de homologação)
- SQLAlchemy + Alembic/Flask-Migrate
- Gunicorn
- Docker
- Render
- Google Drive para imagens das questões discursivas
- Pytest
- OpenPyXL
- ReportLab

## Perfis

- Administrador
- Coordenador
- Aplicador

## Ambientes

- Local: desenvolvimento
- Homologação: Render + Supabase
- Produção: definida após testes de carga

> Nenhuma credencial, dado real de estudante ou segredo deve ser versionado neste repositório.
