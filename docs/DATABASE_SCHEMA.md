# Banco de dados — SARE

Projeto Supabase de homologação:
- Nome: SARE2026
- Região: sa-east-1
- Project ref: `iyyfzgvwioqmmoooisyj`

## Tabelas iniciais
- users
- schools
- evaluations
- classes
- students
- tests
- skills
- questions
- class_applications
- student_records
- answers
- discursive_uploads
- audit_logs

## Segurança
Todas as tabelas do schema `public` têm RLS habilitado.
Os papéis `anon` e `authenticated` não possuem privilégios diretos nessas tabelas.
A aplicação Flask acessará o PostgreSQL por conexão server-side.

Isto é deliberado: o SARE não utilizará Supabase Auth nem acesso direto do navegador ao banco nesta fase.

## Conexão no Render
Render pode operar em ambiente IPv4. Para o runtime, preferir a URL do Supavisor em session mode (porta 5432) fornecida pelo painel Supabase.
Não versionar DATABASE_URL.

## Dados
Respostas objetivas preservam a alternativa selecionada.
O acerto é derivado comparando `answers.selected_option` com `questions.correct_option`.
Questões em branco permanecem NULL no banco.

## Migrações aplicadas
1. `initial_sare_schema`
2. `add_foreign_key_indexes`
