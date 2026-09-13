# Especificação funcional — SARE

## 1. Visão
Sistema independente para registrar aplicações SARE de Língua Portuguesa e Matemática do 2º ao 9º ano, acompanhar conclusão em tempo real e consolidar resultados.

## 2. Entidades principais
- Usuário
- Aplicador
- Escola
- Turma
- Estudante
- Avaliação
- Prova
- Questão
- Habilidade
- Gabarito
- Aplicação de turma
- Registro de estudante
- Resposta
- Discursiva
- Finalização
- Log de auditoria

## 3. Preparação
O administrador cria uma avaliação e associa anos, provas, questões, componentes, alternativas corretas e códigos de habilidade.
A base de escolas/turmas/estudantes será importada de planilha.
Cada turma recebe código exclusivo e poderá receber QR Code posteriormente.

## 4. Aplicador
### Entrada
1. Login próprio.
2. Tela para código da turma.
3. Validação do código.
4. Lista de estudantes.

### Lista
Cada estudante exibe status:
- pendente;
- presente concluído;
- ausente.

### Formulário
Presença obrigatória.
Se ausente: somente salvar.
Se presente: autodeclaração opcional, questões opcionais e foto obrigatória.
Autodeclarações possíveis:
- Preto
- Pardo
- Amarelo
- Indígena
- Branco

Cada questão objetiva oferece A/B/C/D ou nenhuma seleção.

### Foto
Uma foto discursiva por estudante presente na primeira versão.
Upload para storage externo com organização por avaliação/escola/turma/aluno.

### Salvamento
Ao salvar, retornar à lista da turma.

### Finalização
Quando todos os estudantes tiverem presença e todos os presentes tiverem foto confirmada, habilitar finalização.
Exibir conferência de totais.
Após confirmação, bloquear turma e gerar PDF simples de comprovante.

## 5. Coordenador
### Aplicadores
Cadastro:
- nome;
- função na Secretaria;
- login;
- senha;
- status ativo/inativo.

### Gerenciar aplicações
Navegação escola -> turmas.
Cores/estados:
- cinza: não iniciada;
- amarelo: em andamento;
- verde: finalizada;
- vermelho: inconsistência quando aplicável.

Ao abrir turma, mostrar aplicador, início, finalização, presentes, ausentes e status.
Coordenador pode reabrir mediante auditoria.

### Relatórios
PDF e Excel conforme o tipo.
Mínimos:
- ausentes por turma;
- ausentes por escola;
- ranking de escolas;
- ranking de turmas;
- melhores alunos por ano na rede;
- resultados por autodeclaração por ano/escola/turma;
- proficiência;
- desempenho por questão;
- desempenho por habilidade;
- desempenho LP/Matemática;
- gráficos.

### Proficiência
- 0–40%: Defasagem
- >40–70%: Intermediário
- >70–100%: Avançado

## 6. Exportação oficial
Arquivo único com abas 2º, 3º, 4º, 5º, 6º, 7º, 8º e 9º ano.
Modelo final será baseado em planilha-template fornecida pelo usuário.
Campos-base:
ESCOLA / ALUNO / TURMA / AUTODECLARAÇÃO / habilidade-q1 / habilidade-q2 / ...

Resultado de cada habilidade/questão na saída: 1 acerto, 0 erro.
O dado bruto da alternativa permanece preservado no banco.

## 7. Não funcionais
- mobile-first;
- funcionamento aceitável em internet instável;
- arquitetura preparada para PWA/fila offline em fase posterior;
- idempotência nos salvamentos críticos;
- sem duplicação de resposta por duplo clique/retry;
- auditoria;
- HTTPS;
- backups;
- boa acessibilidade;
- telas simples para usuários com baixa proficiência digital.

## 8. Fora do MVP inicial
- leitura automática da discursiva;
- IA;
- correção automática da discursiva;
- aplicativo nativo;
- integração com CI-EDUC;
- Supabase Auth;
- dashboards preditivos.
