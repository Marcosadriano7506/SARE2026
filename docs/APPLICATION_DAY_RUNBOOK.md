# SARE — Runbook do dia da aplicação

## Antes da abertura

1. Confirmar `/health` com HTTP 200.
2. Confirmar painel de status:
   - PostgreSQL persistente OK;
   - Google Drive OK;
   - HTTPS/cookie seguro OK;
   - homologação desativada.
3. Confirmar backup recente.
4. Confirmar avaliação correta como ativa.
5. Confirmar base de estudantes, gabarito e habilidades.
6. Baixar/guardar:
   - PDF dos códigos das turmas;
   - lista de aplicadores;
   - contatos da coordenação.
7. Fazer teste com uma turma fictícia de contingência.
8. Confirmar espaço/funcionamento do Shared Drive.

## Para o aplicador

1. Entrar com login individual.
2. Digitar/ler o código da turma.
3. Conferir escola/turma antes de iniciar.
4. Não compartilhar senha.
5. Um único aplicador por turma.
6. Para cada estudante:
   - marcar Presente ou Ausente;
   - preencher autodeclaração somente quando informada;
   - lançar A/B/C/D;
   - questão sem marcação pode ficar em branco;
   - presente exige foto da discursiva.
7. Observar o status de envio antes de avançar.
8. Em conexão instável:
   - não fechar a página;
   - o rascunho de presença/respostas fica no aparelho;
   - a foto pode precisar ser selecionada novamente.
9. Só finalizar quando a tela indicar zero pendências.
10. Baixar o comprovante PDF.

## Para a coordenação

Acompanhar **Monitorar aplicações**:

- Não iniciada;
- Em andamento;
- Finalizada;
- Reaberta;
- Inconsistência.

Antes de reabrir:
1. confirmar turma;
2. identificar a necessidade;
3. registrar motivo claro;
4. avisar o aplicador.

Toda reabertura fica auditada.

## Contingência — internet caiu

### Queda no celular do aplicador
- manter a página aberta;
- evitar limpar dados do navegador;
- aguardar reconexão;
- revisar rascunho restaurado;
- selecionar novamente a foto se necessário;
- salvar antes de sair do estudante.

### Escola inteira sem internet
- continuar a aplicação em papel;
- manter provas organizadas por turma;
- não finalizar a turma no sistema;
- lançar assim que a conectividade retornar.

## Contingência — Render indisponível

1. Confirmar se `/health` está inacessível.
2. Verificar status/logs do serviço.
3. Não criar uma segunda aplicação paralela.
4. Manter aplicação física normalmente.
5. Aguardar restauração do serviço.
6. Conferir auditoria e turmas em andamento ao retornar.

## Contingência — Google Drive indisponível

- respostas podem ser preservadas em rascunho;
- turma NÃO deve ser finalizada sem todas as fotos confirmadas;
- manter as folhas discursivas físicas identificadas;
- após retorno do Drive, reenviar as fotos e somente depois finalizar.

## Contingência — banco

- interromper gravações se o healthcheck indicar banco indisponível;
- não tentar migrações ou comandos destrutivos durante a aplicação;
- restaurar somente com procedimento técnico aprovado.

## Pós-aplicação

1. Confirmar todas as turmas esperadas:
   - finalizadas; ou
   - justificadas/reabertas.
2. Baixar backup administrativo.
3. Gerar:
   - Excel final;
   - relatório PDF;
   - ausentes;
   - resultados por questão;
   - resultados por habilidade.
4. Conferir o total de discursivas no Drive com o total de presentes.
5. Guardar os comprovantes e auditoria.
6. Remover qualquer fixture sintético de carga.
