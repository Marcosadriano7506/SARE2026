# SARE — Configuração para produção

Este documento descreve os segredos e variáveis necessários para retirar o SARE da homologação.

## 1. Banco persistente — Supabase

No projeto Supabase **SARE2026**:

1. Abra o projeto no Dashboard.
2. Clique em **Connect**.
3. Selecione **Session pooler**.
4. Copie a connection string que usa a porta **5432**.
5. Substitua `[YOUR-PASSWORD]` pela senha do banco.
6. Se a senha tiver caracteres reservados de URI, use a string copiada pelo painel e faça percent-encoding quando necessário.

No Render > serviço `sare-homologacao` > Environment:

- `DATABASE_URL` = connection string completa do Session pooler.

O código aceita `postgresql://...` e converte automaticamente para o driver psycopg.

Depois do primeiro deploy com Supabase:
- abrir `/health`;
- confirmar HTTP 200;
- entrar no painel;
- criar um aplicador de teste;
- reiniciar/redeployar o serviço;
- confirmar que o aplicador continua existindo.

Não usar a conexão direta IPv6 do Supabase no Render Free. Preferir Session pooler IPv4/porta 5432.

## 2. Fotos — Google Drive

### Requisito recomendado

Usar um **Shared Drive do Google Workspace**, pois service accounts não têm cota própria de armazenamento e não devem ser proprietárias dos arquivos.

Estrutura recomendada:

```
Shared Drive: SARE
└── DISCURSIVAS
    └── SARE 2026.2
        └── Escola
            └── Turma
                └── estudante__id.jpg
```

### Google Cloud

1. Criar/selecionar um projeto Google Cloud.
2. Ativar **Google Drive API**.
3. Criar uma Service Account exclusiva, ex. `sare-drive-uploader`.
4. Abrir a Service Account > **Keys** > **Add key** > **Create new key** > **JSON**.
5. O arquivo JSON será baixado uma única vez.

Nunca adicionar esse JSON ao GitHub.

### Shared Drive

1. Criar ou escolher um Shared Drive institucional.
2. Criar uma pasta raiz para o SARE, ex. `DISCURSIVAS`.
3. Adicionar o e-mail da Service Account como membro do Shared Drive com permissão suficiente para criar e remover arquivos.
4. Copiar o ID da pasta raiz `DISCURSIVAS`.

O ID da pasta é a parte após `/folders/` na URL do Google Drive.

### Render

Adicionar no Environment:

- `STORAGE_PROVIDER=GOOGLE_DRIVE`
- `GOOGLE_DRIVE_ROOT_FOLDER_ID=<id da pasta raiz>`
- `GOOGLE_SERVICE_ACCOUNT_JSON=<conteúdo integral do JSON da service account>`

O JSON deve ser salvo como uma única variável de ambiente secreta.

Depois do deploy:
- abrir o status do sistema;
- confirmar storage Google Drive OK;
- fazer uma aplicação fictícia;
- fotografar uma discursiva;
- confirmar criação automática de Avaliação/Escola/Turma no Drive;
- substituir a foto e confirmar que a anterior foi removida;
- marcar o aluno como ausente e confirmar limpeza do arquivo.

## 3. Desligar homologação

Somente depois de Supabase e Drive estarem validados:

- `ALLOW_HOMOLOGATION_BOOTSTRAP=false`
- `AUTO_CREATE_DEMO_DATA=false`
- remover ou esvaziar:
  - `BOOTSTRAP_ADMIN_PASSWORD`
  - `BOOTSTRAP_APPLICATOR_PASSWORD`
  - `LOAD_TEST_PASSWORD`
- `SESSION_COOKIE_SECURE=true`
- `STORAGE_PROVIDER=GOOGLE_DRIVE`

Manter `SECRET_KEY` forte e gerada no Render.

## 4. Teste de carga

Criar fixture sintético somente em homologação:

```bash
flask create-load-fixture --users 100 --students-per-class 30
```

Requer:

```
ALLOW_HOMOLOGATION_BOOTSTRAP=true
LOAD_TEST_PASSWORD=<senha sintética de teste>
```

Executar:

```bash
python scripts/load_test.py \
  --base-url https://sare-homologacao.onrender.com \
  --scenario applicator \
  --users 100 \
  --concurrency 50 \
  --reads 2 \
  --prefix load \
  --password "<LOAD_TEST_PASSWORD>" \
  --max-error-rate 0.02 \
  --max-p95 3.0
```

Remover os dados sintéticos depois:

```bash
flask delete-load-fixture --confirm REMOVER
```

## 5. Critério mínimo para produção

- Supabase persistente confirmado após redeploy.
- Google Drive real confirmado com upload/replace/delete.
- RLS e privilégios públicos bloqueados.
- Cookie HTTPS ativo.
- CI verde.
- Teste de carga aprovado.
- Teste de campo em celular Android/iPhone e internet instável.
- Backup baixado e restauração testada.
- Base DEMO/fixture de carga removidos.
- Homologation banner desativado.
