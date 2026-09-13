# Roadmap de implementação

## Fase 0 — Fundação
- [x] Repositório inicializado
- [x] Documentação de produto/arquitetura
- [ ] Estrutura Flask
- [ ] Docker
- [ ] Configuração de ambiente
- [ ] Healthcheck
- [ ] Pytest/CI

## Fase 1 — Identidade e autorização
- [ ] Modelo User
- [ ] perfis ADMIN/COORDINATOR/APPLICATOR
- [ ] login/logout
- [ ] hash de senha
- [ ] autorização por decorators/policies
- [ ] auditoria inicial

## Fase 2 — Estrutura acadêmica
- [ ] escolas
- [ ] turmas
- [ ] estudantes
- [ ] avaliações
- [ ] provas
- [ ] questões
- [ ] habilidades
- [ ] gabaritos

## Fase 3 — Importação
- [ ] template de importação
- [ ] validação
- [ ] preview
- [ ] importação transacional
- [ ] códigos de turma
- [ ] relatório de inconsistências

## Fase 4 — Aplicador
- [ ] código da turma
- [ ] lista de estudantes
- [ ] presença
- [ ] autodeclaração
- [ ] A/B/C/D/em branco
- [ ] UI mobile-first
- [ ] salvamento idempotente

## Fase 5 — Discursiva
- [ ] interface StorageService
- [ ] Google Drive
- [ ] compressão/validação segura
- [ ] obrigatoriedade para presente
- [ ] confirmação de upload

## Fase 6 — Finalização
- [ ] validações de completude
- [ ] resumo
- [ ] bloqueio
- [ ] código do comprovante
- [ ] PDF simples
- [ ] reabertura por coordenador
- [ ] auditoria

## Fase 7 — Monitoramento
- [ ] dashboard
- [ ] escolas/turmas
- [ ] estados visuais
- [ ] totais em tempo real

## Fase 8 — Resultados
- [ ] motor de correção
- [ ] LP/Matemática
- [ ] habilidades
- [ ] proficiência
- [ ] autodeclaração

## Fase 9 — Relatórios
- [ ] ausentes
- [ ] rankings
- [ ] alunos por ano
- [ ] gráficos
- [ ] PDF
- [ ] Excel

## Fase 10 — Exportação oficial
- [ ] ingestão do template oficial
- [ ] oito abas
- [ ] mapeamento de habilidades
- [ ] testes de equivalência

## Fase 11 — Robustez de campo
- [ ] PWA
- [ ] fila offline
- [ ] retry idempotente
- [ ] indicador sincronizado/pendente

## Fase 12 — Produção
- [ ] teste de carga
- [ ] revisão LGPD
- [ ] backup/restore testado
- [ ] plano de contingência
- [ ] decisão Render vs VPS
