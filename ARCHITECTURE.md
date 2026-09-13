# Arquitetura — SARE

## Topologia de homologação

Browser/celular
→ Render Web Service
→ Flask + Gunicorn
→ PostgreSQL no Supabase

Uploads de discursivas
→ Flask/serviço de storage
→ Google Drive

Código
→ GitHub
→ deploy no Render

## Princípios
1. Portabilidade: aplicação não pode depender da infraestrutura do Render/Supabase para funcionar.
2. Twelve-factor: configuração por ambiente.
3. Banco relacional como fonte da verdade.
4. Resposta bruta separada de cálculo derivado.
5. Storage externo abstraído.
6. Autorização no backend.
7. Migrações versionadas.
8. Testes automatizados.

## Camadas
- web/routes: HTTP e validação de entrada.
- services: regras de negócio.
- repositories/models: persistência.
- integrations: Google Drive e futuras alternativas.
- reports: PDF/Excel/gráficos.
- auth: autenticação/autorização.
- audit: eventos sensíveis.

## Banco
Homologação: Supabase PostgreSQL.
A aplicação Flask acessará PostgreSQL por DATABASE_URL com SSL.
Não utilizar a Data API como camada principal do backend.
Em ambientes com pooler transacional, configurar SQLAlchemy de forma compatível com a conexão fornecida.

## Storage
Interface conceitual:

StorageService.upload_discursive(...)
StorageService.delete(...)
StorageService.exists(...)

Implementação inicial: GoogleDriveStorage.
Futura: S3/MinIO/GCS sem alterar regra de negócio.

## Segurança
- bcrypt/Argon2 via biblioteca consolidada;
- cookies Secure/HttpOnly/SameSite em produção;
- CSRF;
- timeouts e tamanho máximo de upload;
- MIME/type validation;
- UUIDs/códigos não sequenciais em recursos externos quando aplicável;
- autorização por perfil e escopo;
- logs sem conteúdo sensível.

## Observabilidade
- healthcheck HTTP;
- logs estruturados;
- correlation/request ID futuramente;
- métricas de erros de upload e finalização;
- auditoria persistida no banco.

## Estratégia de migração para VPS
A futura VPS deve exigir apenas:
- nova DATABASE_URL;
- novo endpoint de deployment;
- opcionalmente mudança de StorageService;
- mesmas imagens Docker e mesmas migrações.

Nenhuma regra de negócio pode depender do Render.
