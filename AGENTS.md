# AGENTS.md

## Papel do agente
Você é o engenheiro de software executor deste repositório. Implemente estritamente as especificações do produto. Não altere stack, regras de negócio, modelos de autorização ou integrações estruturais sem instrução explícita.

## Regras arquiteturais imutáveis
- Sistema independente do CI-EDUC.
- Backend principal em Flask.
- Banco PostgreSQL.
- ORM SQLAlchemy e migrações versionadas.
- Interface mobile-first.
- Docker desde o início.
- Ambientes configurados exclusivamente por variáveis de ambiente.
- Homologação inicialmente em Render + Supabase PostgreSQL.
- Fotos discursivas armazenadas fora do banco e fora do filesystem persistente da aplicação.
- Integração inicial de fotos: Google Drive por uma camada abstrata de storage.
- Não usar Supabase Auth nesta fase; autenticação é da aplicação Flask.
- Não usar SQLite em homologação ou produção.
- Não incluir segredos no Git.
- Não persistir arquivos temporários após a entrega/download.

## Perfis e autorização
### ADMIN
- Acesso total.
- Cria coordenadores.
- Configura avaliações, bases, provas, habilidades e gabaritos.

### COORDENADOR
- Cadastra e gerencia aplicadores.
- Acompanha escolas/turmas/aplicações.
- Emite relatórios PDF/Excel.
- Exporta resultado geral.
- Pode reabrir turma finalizada; toda reabertura gera auditoria.

### APLICADOR
- Após login informa código da turma.
- Só acessa fluxo de aplicação.
- Nunca visualiza gabarito, acertos, notas, rankings ou relatórios analíticos.
- Não acessa dados de outras turmas sem código autorizado.

## Regras do formulário do estudante
1. Presença é obrigatória: PRESENTE ou AUSENTE.
2. Se AUSENTE:
   - ocultar autodeclaração;
   - ocultar questões;
   - ocultar upload de foto;
   - permitir salvar imediatamente;
   - respostas anteriores, se existirem em edição autorizada, não podem ser consideradas no resultado.
3. Se PRESENTE:
   - autodeclaração é opcional;
   - respostas A/B/C/D são opcionais individualmente;
   - questão em branco deve permanecer NULL no banco;
   - foto da discursiva é obrigatória antes de salvar.
4. Não preencher questão não significa erro no armazenamento bruto.
5. A camada de cálculo/exportação é responsável por converter acerto/erro/em branco conforme a regra do relatório.

## Respostas e gabarito
- Armazenar a alternativa marcada pelo estudante, não apenas 1/0.
- Gabarito fica separado da resposta.
- Acerto é derivado por comparação.
- Aplicador jamais recebe o gabarito na resposta HTML/API.
- Questões pertencem a componente (LP ou Matemática), ano, prova e habilidade.
- Habilidade deve preservar seu código original.

## Fluxo da turma
Estados mínimos:
- NOT_STARTED
- IN_PROGRESS
- FINALIZED
- REOPENED/INCONSISTENT quando aplicável

A turma só pode ser finalizada quando todos os estudantes tiverem presença registrada e todos os presentes tiverem foto discursiva confirmada.
Ao finalizar:
- registrar aplicador;
- registrar timestamps;
- bloquear edição pelo aplicador;
- gerar comprovante simples em PDF;
- não gerar Excel para o aplicador.
Somente coordenador/admin pode reabrir.

## Comprovante PDF do aplicador
Deve conter somente dados administrativos:
- avaliação;
- escola;
- turma/ano;
- aplicador e função;
- data;
- total de estudantes;
- presentes;
- ausentes;
- quantidade de registros concluídos;
- quantidade de fotos confirmadas;
- horário de início/finalização;
- código da turma;
- código único do comprovante;
- status finalizado.

Não incluir:
- respostas;
- autodeclaração individual;
- notas;
- gabarito;
- percentual de acerto;
- imagens.

## Fotos
- Presentes exigem foto.
- Upload só é considerado concluído após confirmação do storage.
- Organizar logicamente: avaliação/escola/turma/aluno.
- Nome do arquivo deve combinar nome normalizado + identificador imutável do aluno para evitar colisão.
- Guardar no banco apenas metadados necessários e ID/URL privada do arquivo.
- Não exibir foto em relatórios.
- Storage deve ser substituível via interface de serviço.

## Relatórios da coordenação
Prever:
- ausentes por turma e escola;
- participação;
- ranking de escolas;
- ranking de turmas;
- melhores alunos por ano;
- resultados por componente;
- resultados por habilidade;
- resultados por autodeclaração por ano/escola/turma;
- níveis de proficiência;
- gráficos;
- exportação geral oficial.

Faixas iniciais:
- Defasagem: 0% a 40% inclusive.
- Intermediário: >40% até 70% inclusive.
- Avançado: >70% até 100%.

## Exportação geral
- Um arquivo Excel.
- Abas do 2º ao 9º ano.
- Layout deve seguir template oficial fornecido posteriormente.
- Colunas de habilidades recebem 1 para acerto e 0 para erro.
- Tratamento de questão em branco na exportação deve ser configurável e explicitamente testado.

## Segurança
- Hash forte de senha; nunca texto puro.
- CSRF em formulários autenticados.
- Sessões seguras.
- Autorização server-side em toda rota.
- Auditoria de ações sensíveis.
- Rate limiting no login quando implantado.
- LGPD: autodeclaração é dado sensível e deve ter acesso restrito.
- Não registrar respostas/senhas/dados sensíveis em logs de aplicação.
- Usar HTTPS em homologação/produção.
- Banco remoto sempre com SSL.

## Qualidade
Antes de concluir qualquer tarefa:
1. Execute os testes relevantes.
2. Crie/atualize testes da regra alterada.
3. Não marque tarefa como concluída com teste falhando.
4. Não desative teste para fazê-lo passar.
5. Prefira alterações pequenas e rastreáveis.
6. Migrations devem ser reversíveis quando tecnicamente viável.

## Testes obrigatórios de negócio
- ausente salva sem foto;
- presente não salva sem foto;
- presente aceita questões em branco;
- questão em branco permanece NULL;
- aplicador não vê gabarito;
- aplicador não edita turma finalizada;
- coordenador reabre turma;
- reabertura gera auditoria;
- correta calcula 1;
- incorreta calcula 0;
- foto não aparece em relatórios;
- finalização falha com aluno pendente;
- PDF não contém resultado pedagógico.

## Proibições
Não:
- trocar Flask sem autorização;
- adotar Firebase/Supabase Auth sem autorização;
- guardar foto no PostgreSQL;
- usar chave service-role no browser;
- tornar pasta do Drive pública;
- inserir dados reais em fixtures;
- remover auditoria para simplificar;
- permitir que o frontend seja a única camada de autorização.
