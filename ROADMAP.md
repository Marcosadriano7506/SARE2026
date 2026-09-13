# Roadmap de implementação

> Atualizado em 13/09/2026. Este arquivo representa o estado real da branch `develop`.

## Fase 0 — Fundação
- [x] Repositório inicializado
- [x] Documentação de produto/arquitetura
- [x] Estrutura Flask
- [x] Docker
- [x] Configuração de ambiente
- [x] Healthcheck
- [x] Pytest/CI
- [x] Homologação no Render

## Fase 1 — Identidade e autorização
- [x] Modelo User
- [x] Perfis ADMIN/COORDINATOR/APPLICATOR
- [x] Login/logout
- [x] Hash de senha
- [x] Autorização por decorators/policies
- [x] Ativar/desativar usuários
- [x] Redefinição de senha de aplicador
- [x] Administração de coordenadores pelo ADMIN
- [x] Auditoria visível no painel
- [x] Bloqueio de sessão de usuário desativado

## Fase 2 — Estrutura acadêmica
- [x] Escolas
- [x] Turmas
- [x] Estudantes
- [x] Avaliações
- [x] Provas
- [x] Questões
- [x] Habilidades
- [x] Gabaritos
- [x] Janela de aplicação por data
- [x] Validação de prontidão antes de ativar avaliação

## Fase 3 — Importação
- [x] Template de importação da base
- [x] Validação da planilha
- [x] Prévia antes de gravar
- [x] Identificação de duplicidades aparentes na prévia
- [x] Importação transacional
- [x] Códigos exclusivos de turma
- [x] PDF imprimível de códigos/QR
- [x] Template e importação de gabarito/habilidades
- [ ] Prévia visual do gabarito antes de gravar

## Fase 4 — Aplicador
- [x] Código da turma
- [x] QR para preencher código
- [x] Lista de estudantes
- [x] Presença
- [x] Autodeclaração
- [x] A/B/C/D/em branco
- [x] UI mobile-first
- [x] Bloqueio contra outro aplicador assumir turma em andamento
- [x] Auditoria de abertura e alteração de respostas
- [x] Proteção contra duplo envio visual
- [x] Rascunho local de presença/autodeclaração/respostas

## Fase 5 — Discursiva
- [x] Interface StorageService
- [x] Provider Google Drive implementado
- [x] Provider local exclusivo de homologação
- [x] Validação real de JPG/PNG/WEBP
- [x] Correção de orientação EXIF
- [x] Remoção de EXIF/GPS
- [x] Redimensionamento e compressão para JPEG
- [x] Obrigatoriedade para estudante presente
- [x] Confirmação de upload antes da finalização
- [x] Substituição e remoção segura do arquivo anterior
- [ ] Credenciais institucionais do Google Drive configuradas no Render
- [ ] Teste real de upload na pasta institucional

## Fase 6 — Finalização
- [x] Validações de completude
- [x] Tela de conferência
- [x] Bloqueio após finalização
- [x] Código único do comprovante
- [x] PDF simples do aplicador
- [x] QR/código de verificação pública do comprovante
- [x] Tela de sucesso pós-finalização
- [x] Reabertura por coordenador com motivo
- [x] Auditoria

## Fase 7 — Monitoramento
- [x] Dashboard
- [x] Escolas/turmas
- [x] Estados visuais
- [x] Totais operacionais
- [x] Filtros por avaliação/escola/ano/status
- [x] Atualização automática da tela de monitoramento
- [x] Atribuição/reatribuição operacional de aplicação
- [x] Regeneração de código de turma

## Fase 8 — Resultados
- [x] Motor de correção
- [x] LP/Matemática
- [x] Resultado por questão
- [x] Resultado por habilidade
- [x] Proficiência
- [x] Autodeclaração por rede/escola/turma/ano
- [x] Cálculo ponderado em nível de item/estudante

## Fase 9 — Relatórios
- [x] Ausentes
- [x] Ranking de escolas
- [x] Ranking de turmas
- [x] Melhores alunos por ano
- [x] Gráficos leves e responsivos
- [x] PDF executivo de resultados
- [x] PDF de ausentes
- [x] Excel analítico

## Fase 10 — Exportação oficial
- [x] Referência baseada na planilha teste fornecida
- [x] Oito abas — 2º ao 9º ano
- [x] Aluno por linha
- [x] Item/habilidade por coluna
- [x] 1 = acerto / 0 = erro
- [x] Ausentes com células pedagógicas em branco
- [x] Totais, percentuais e proficiência de LP e Matemática
- [x] Desambiguação quando uma habilidade aparece em mais de uma questão
- [x] Abas analíticas complementares
- [x] Testes automatizados da estrutura da exportação
- [ ] Comparação final com uma planilha oficial preenchida real antes da primeira aplicação oficial

## Fase 11 — Robustez de campo
- [x] PWA instalável
- [x] Indicador global online/offline
- [x] Tela offline sem cache de dados pessoais
- [x] Rascunho local do formulário
- [x] Política `no-store` para páginas sensíveis
- [ ] Fila offline completa de POSTs com replay automático
- [ ] Upload offline de foto — deliberadamente não implementado por enquanto
- [ ] Teste de campo em escolas com conexão instável

## Fase 12 — Segurança, contingência e produção
- [x] Revisão inicial LGPD/segurança de aplicação
- [x] RLS habilitado em todas as tabelas do Supabase
- [x] Sem policies públicas nas tabelas
- [x] Perfis Supabase `anon` e `authenticated` sem SELECT/INSERT nas tabelas SARE
- [x] Headers de segurança e bloqueio de cache
- [x] Backup estruturado administrativo `.json.gz`
- [x] Restauração transacional por CLI com confirmação explícita
- [x] Página ADMIN de prontidão de ambiente
- [x] Pool SQLAlchemy preparado para Supabase Free
- [ ] Definir `DATABASE_URL` persistente no Render usando Session Pooler oficial do Supabase
- [ ] Configurar Google Drive institucional no Render
- [ ] Ativar `SESSION_COOKIE_SECURE=true`
- [ ] Desativar bootstrap/dados DEMO de homologação
- [ ] Testar backup/restore também sobre PostgreSQL/Supabase
- [ ] Teste de carga com cenário próximo do dia real de aplicação
- [ ] Teste ponta a ponta de campo
- [ ] Plano formal de contingência para o dia da aplicação
- [ ] Decisão final Render vs VPS após teste de carga

## Bloqueadores para dados reais

O sistema **não deve receber dados reais de estudantes** enquanto qualquer item abaixo estiver pendente:

1. `DATABASE_URL` persistente do Supabase não validada no Render.
2. Google Drive institucional não validado como storage das discursivas.
3. Cookie seguro HTTPS não ativado.
4. Modo de homologação/DEMO ainda ativo.
5. Teste ponta a ponta com backup e recuperação ainda não homologado no ambiente definitivo.
