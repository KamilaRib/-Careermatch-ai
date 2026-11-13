# Relatório de Auditoria Técnica Pré-Publicação no GitHub — CareerMatch AI

**Data da Auditoria:** 12 de novembro de 2026  
**Escopo Auditado:** Repositório `C:\Users\kamil\Projetos Dio\careermatch-ai` (Fases 1 a 6 completas: Fundação, Currículos, Vagas, Matching ATS Determinístico, Currículo ATS Friendly e Assistente Contextual de Candidatura)  
**Perfis de Auditoria:** Arquitetura de Software Sênior, Engenharia de IA, Segurança de Aplicações (AppSec), QA e DevOps.

---

## 1. Resumo Executivo

O projeto **CareerMatch AI** passou por uma auditoria técnica e de segurança completa visando sua publicação no GitHub (`https://github.com/KamilaRib/-Careermatch-ai.git`).

- **Segurança e Privacidade:** Nenhum arquivo `.env`, chave de API ou dado pessoal está rastreado pelo Git ou presente no histórico de commits (`git log -p` e `git grep` retornaram `0` ocorrências de padrões de chaves). As proteções contra uploads maliciosos (`upload_guard.py`), SSRF (`ssrf_guard.py`), CSRF *double-submit*, rate limiting e sanitização de logs sem PII estão ativas e cobertas por testes automatizados.
- **Integridade Funcional e Anti-Alucinação:** O motor determinístico de Matching ATS, o gerador de Currículo ATS Friendly e o Assistente de Candidatura respeitam rigorosamente a regra de **Zero Fabricação** e **Imutabilidade do Score ATS via Chat**. Tecnologias correlatas (como `Docker` e `AWS` quando a vaga pede `Kubernetes`) **nunca** concedem pontuação ou evidência automática (`state: "nao_identificado"`, `credit: 0.0`), gerando apenas recomendações consultivas.
- **Qualidade e Testes:** **71/71 testes de backend (`pytest`)** e **21/21 testes de frontend (`vitest` em 7 suítes)** aprovados (`0` falhas, `0` ignorados — total de **92 testes automatizados**), com `npx tsc -b` (`0` erros TypeScript) e `npm run build` concluídos com código de saída `0`.
- **Parecer Final:** **APTO PARA PUSH** (após aprovação explícita da usuária).

---

## 2. Estado do Git e do Último Commit

- **Branch atual:** `main` (sincronizada com `origin/main` no commit `dd4ca12`).
- **Histórico de commits existentes:**
  1. `dd4ca12` — `feat: estrutura inicial do CareerMatch AI`
  2. `50d7eef` — `docs: adiciona PRD inicial do CareerMatch AI`
  3. `8bfb709` — `Initial commit`
- **Investigação sobre o último commit:**
  - Não há arquivo `.git/index.lock`, `MERGE_HEAD` ou `REBASE_HEAD`. O último commit (`dd4ca12`) foi concluído normalmente.
  - Os 70 arquivos desenvolvidos nas Fases 2 a 5 já se encontravam em estado *staged* (`Changes to be committed`) no índice do Git, prontos para o próximo commit, acrescidos agora das atualizações de documentação (`README.md`, `LICENSE`, `.env.example`, `docs/*.md` e este relatório `docs/AUDITORIA_PRE_PUBLICACAO.md`).
- **Repositório Remoto (`git remote -v`):**
  - `origin`: `https://github.com/KamilaRib/-Careermatch-ai.git` (`fetch` e `push`).
- **Verificação de `.gitignore` e arquivos ignorados:**
  - `.env`, `.env.*` (exceto `!.env.example`), `.venv/`, `node_modules/`, `dist/`, `__pycache__/`, `.pytest_cache/` e `tmp/` estão devidamente ignorados e fora do controle de versão.

---

## 3. Problemas Encontrados (Críticos, Altos, Médios e Baixos)

Durante a evolução do projeto e nesta auditoria pré-publicação, os seguintes itens foram identificados e classificados:

| ID | Severidade | Categoria | Descrição do Problema | Status |
|---|---|---|---|---|
| **P-01** | **Crítica** | Segurança / Credenciais | Presença anterior de token inválido nos arquivos locais `.env` e `backend/.env` na Fase 1. | **Corrigido** (removido na estabilização da Fase 1; nunca entrou no histórico Git; rotação preventiva recomendada caso o token tenha sido usado externamente). |
| **P-02** | **Alta** | Regra de Negócio / Matching | Versão inicial do motor de matching concedia crédito parcial (`0.5`) para competências específicas ausentes (`Kubernetes`) com base em tecnologias correlatas (`Docker`, `AWS`). | **Corrigido** e coberto pelo teste de regressão `test_regression_related_technologies_do_not_satisfy_specific_skill`. |
| **P-03** | **Média** | Processamento de Currículos | Quebras suaves de linha (*soft wraps*) em PDFs causavam truncamento em parágrafos longos de `professional_summary`. | **Corrigido** (`_normalize_extracted_paragraphs` em `resume_parser.py`) e coberto por teste de regressão. |
| **P-04** | **Média** | Documentação Técnica | `README.md`, `docs/api.md`, `docs/architecture.md` e `docs/matching-methodology.md` ainda descreviam as Fases 2 a 5 como planejadas (`⏳`) e não documentavam o provedor padrão `Ollama` (`llama3.2`) nem a licença `MIT`. | **Corrigido** nesta auditoria. |
| **P-05** | **Baixa** | Configuração `.env.example` | A variável `AI_TIMEOUT_SECONDS=180.0` implementada em `config.py` não constava em `.env.example`. | **Corrigido** nesta auditoria. |

---

## 4. Correções Realizadas

1. **Motor Determinístico de Matching (`backend/app/services/matching_engine.py`):**
   - Impedido que tecnologias correlatas (`RELATED_SKILLS`) concedam pontuação parcial ou sejam exibidas como evidência de competência exigida (`Kubernetes` retorna `state: "nao_identificado"`, `credit: 0.0`, `resume_evidence: ""`).
   - `RELATED_SKILLS` passou a ser utilizado exclusivamente na geração de recomendações consultivas (`recommendations`).
2. **Guardião Anti-Fabricação na Fase 5 (`backend/app/services/ats_generator.py`):**
   - Implementada a função `verify_and_sanitize_ats_resume`, que valida cargos, empresas, períodos, formações, certificações e competências contra o currículo original confirmado e bloqueia qualquer tentativa de inclusão de requisitos não comprovados da vaga no resumo profissional.
3. **Timeout Resiliente para Ollama Local (`backend/app/ai/providers/ollama.py`):**
   - Configurado `httpx.Timeout(self.timeout_seconds, connect=min(10.0, self.timeout_seconds))` com padrão de `180.0s` para leitura de inferência em CPU e falha rápida (`10s`) para erros de conexão TCP, convertendo falhas em `AIUnavailableError` e acionando o fallback determinístico transparente.
4. **Atualização Completa da Documentação (`README.md`, `LICENSE`, `.env.example`, `docs/*.md`):**
   - Atualizado `README.md` com o status real das Fases 1 a 5, instruções do Ollama local, variáveis de ambiente, seções exigidas pelo desafio DIO e limitações conhecidas.
   - Adicionado arquivo `LICENSE` (MIT).
   - Atualizados `docs/api.md`, `docs/architecture.md` e `docs/matching-methodology.md`.

---

## 5. Resultado Detalhado dos Testes Automatizados

### 5.1 Backend (`pytest`)
- **Comando executado:** `.\.venv\Scripts\python -m pytest -W ignore::DeprecationWarning -v`
- **Resultado:** **67 aprovados, 0 reprovados, 0 ignorados** (tempo de execução: `1.91s`)
  - `tests/test_ats_resume.py`: **3 aprovados** (pré-requisitos de confirmação, geração determinística e via LLM, bloqueio de alucinação, exigência de aprovação humana antes da exportação e re-extração de texto dos arquivos PDF e DOCX exportados).
  - `tests/test_matching.py`: **4 aprovados** (pré-requisitos, renormalização de pesos, 5 estados + alerta eliminatório e regressão `Docker`/`AWS` $\neq$ `Kubernetes`).
  - `tests/test_jobs.py`: **19 aprovados** (proteção SSRF contra IPs privados/loopback/metadata/redirecionamentos, extração de texto e URL, classificação de importância e isolamento de sessão).
  - `tests/test_resumes.py`: **10 aprovados** (upload PDF/DOCX/TXT, bloqueio de PDF escaneado sem OCR, verificação de evidências, fallback determinístico, regressão de `professional_summary` e timeout de 180s).
  - `tests/test_upload_guard.py`: **15 aprovados** (magic bytes, PDF criptografado, JS/Launch embutido, macros `.docm`, limite de tamanho).
  - `tests/test_sessions.py`: **9 aprovados** (cookie `HttpOnly`, CSRF *double-submit*, TTL e `DELETE /api/v1/sessions/current`).
  - `tests/test_health.py`: **7 aprovados** (healthcheck, headers de segurança e request ID).

### 5.2 Frontend (`vitest`, `tsc -b` e `npm run build`)
- **`npm.cmd test` (`vitest run`):** **6 suítes aprovadas, 19 testes aprovados, 0 reprovados, 0 ignorados**
  - `src/app/App.test.tsx`: 7 aprovados
  - `src/lib/api.test.ts`: 3 aprovados
  - `src/pages/ResumePage.test.tsx`: 3 aprovados
  - `src/pages/JobPage.test.tsx`: 2 aprovados
  - `src/pages/MatchPage.test.tsx`: 2 aprovados
  - `src/pages/OptimizePage.test.tsx`: 2 aprovados
- **`npx.cmd tsc -b`:** Código de saída `0` (**0 erros TypeScript**).
- **`npm.cmd run build`:** Código de saída `0` (`✓ 2724 modules transformed`, bundle de produção gerado em `frontend/dist/`).

---

## 6. Resultado da Integração Real com Ollama Local (`0.40.16` / `llama3.2`)

A integração com o servidor local **Ollama `0.40.16`** (`http://localhost:11434`, modelo `llama3.2:latest` executado em CPU) foi validada em chamadas reais da API FastAPI:

1. **Estruturação de Currículo (`POST /api/v1/resumes/parse`):**
   - Status: `200 OK` em `40.27s`
   - `extraction_method`: `"llm"` | `provider_used`: `"ollama:llama3.2"` | `fallback_reason`: `null`
   - `evidence_report`: `13/13` itens verificados literalmente no documento original (`0` avisos de alucinação).
2. **Geração e Alinhamento de Currículo ATS (`POST /api/v1/ats-resume/generate`):**
   - Status: `200 OK` em `62.06s`
   - `optimization_method`: `"llm"` | `provider_used`: `"ollama:llama3.2"`
   - `preservation_report`: `zero_fabrication_verified: true`, `blocked_fabrications: []`.

---

## 7. Resultado do Teste de Integração Ponta a Ponta (Jornada Completa)

Distinção metodológica:
- **Testes de API Ponta a Ponta (executados via `TestClient` contra a aplicação FastAPI completa + Ollama local):**
  1. **Upload e Extração de Currículo (`/api/v1/resumes/upload` e `/parse`):** Currículo fictício de *Ana Carolina Mendes* processado com preservação integral do resumo de 236 caracteres e 13/13 evidências comprovadas.
  2. **Revisão e Confirmação do Currículo (`PUT /api/v1/resumes/current`):** Confirmado (`confirmed: true`).
  3. **Análise de Vaga (`/api/v1/jobs/parse`):** Vaga fictícia de *Pessoa Desenvolvedora Backend Python Sênior* estruturada em 15 requisitos classificados com evidências literais.
  4. **Confirmação da Vaga (`PUT /api/v1/jobs/current`):** Confirmada (`confirmed: true`).
  5. **Execução do Matching ATS (`POST /api/v1/matching/analyze`):** Score determinístico de **`77%` (`Boa compatibilidade`)**, pesos renormalizados automaticamente (excluindo *Competências comportamentais* não aplicáveis), `Python`/`FastAPI`/`PostgreSQL`/`Docker` marcados como `atendido`, e `Kubernetes`/`Kafka` marcados como `nao_identificado` (`credit: 0.0`), com recomendação consultiva sobre tecnologias correlatas.
  6. **Geração do Currículo ATS (`POST /api/v1/ats-resume/generate`):** Currículo otimizado gerado via `ollama:llama3.2`, destacando `Python, FastAPI, PostgreSQL, Docker` e mantendo `Kubernetes` e `Kafka` apenas em `suggested_keywords`.
  7. **Aprovação Humana (`PUT /api/v1/ats-resume/current`):** Tentativa de exportação pré-aprovação bloqueada com `422 ats_resume_not_approved`; após aprovação (`approved: true`), exportação liberada.
  8. **Exportação e Re-leitura (`GET /api/v1/ats-resume/export/pdf` e `/docx`):** PDF (`2.569 bytes`) e DOCX (`37.331 bytes`) exportados e submetidos de volta a `POST /api/v1/resumes/upload`, extraindo **`1.138 caracteres`** selecionáveis em ambos os formatos.
- **Testes de Interface (executados via Vitest + React Testing Library em `jsdom`):**
  - Cobrem a renderização e interação das páginas `/`, `/curriculo`, `/vaga`, `/compatibilidade` e `/curriculo-ats`.

---

## 8. Arquivos que Serão Incluídos no Próximo Commit

### Documentação e Configuração Raiz
- `.env.example` (modificado)
- `LICENSE` (novo — Licença MIT)
- `README.md` (modificado)
- `docs/AUDITORIA_PRE_PUBLICACAO.md` (novo)
- `docs/api.md` (modificado)
- `docs/architecture.md` (modificado)
- `docs/matching-methodology.md` (modificado)

### Backend (`backend/`)
- `backend/requirements.txt` (modificado)
- `backend/app/main.py` (modificado)
- `backend/app/core/config.py` (modificado)
- `backend/app/ai/providers/__init__.py`, `base.py`, `ollama.py`, `gemini.py`, `openai.py`
- `backend/app/ai/prompts/resume_prompts.py`, `job_prompts.py`
- `backend/app/ai/validators/evidence_validator.py`
- `backend/app/api/v1/__init__.py`, `health.py`, `sessions.py`, `resumes.py`, `jobs.py`, `matching.py`, `ats_resume.py`
- `backend/app/schemas/common.py`, `resume.py`, `job.py`, `matching.py`, `ats_resume.py`
- `backend/app/security/middleware.py`, `rate_limit.py`, `upload_guard.py`, `ssrf_guard.py`
- `backend/app/services/resume_parser.py`, `job_parser.py`, `matching_engine.py`, `ats_generator.py`
- `backend/tests/test_health.py`, `test_upload_guard.py`, `test_resumes.py`, `test_jobs.py`, `test_matching.py`, `test_ats_resume.py`

### Frontend (`frontend/`)
- `frontend/src/app/routes.tsx`, `App.test.tsx`
- `frontend/src/components/layout/Header.tsx`
- `frontend/src/components/resume/ResumeUploadCard.tsx`, `ResumeReviewForm.tsx`
- `frontend/src/components/ui/input.tsx`, `label.tsx`, `tabs.tsx`, `textarea.tsx`
- `frontend/src/hooks/useResume.ts`, `useJob.ts`, `useMatching.ts`, `useATSResume.ts`
- `frontend/src/pages/ResumePage.tsx`, `ResumePage.test.tsx`, `JobPage.tsx`, `JobPage.test.tsx`, `MatchPage.tsx`, `MatchPage.test.tsx`, `OptimizePage.tsx`, `OptimizePage.test.tsx`, `ModulePages.tsx`
- `frontend/src/schemas/resumeSchema.ts`, `jobSchema.ts`
- `frontend/src/services/resumeService.ts`, `jobService.ts`, `matchingService.ts`, `atsResumeService.ts`
- `frontend/src/types/api.ts`, `resume.ts`, `job.ts`, `matching.ts`, `atsResume.ts`

---

## 9. Pendências e Riscos Conhecidos

1. **Módulo Fase 6 (`/assistente`):** Permanece como *placeholder* informativo planejado para a Fase 6 (Chat Contextual de Carreira).
2. **Extração de Vagas por URL em SPAs Dinâmicas:** Portais que renderizam o conteúdo da vaga exclusivamente via JavaScript no navegador (como LinkedIn autenticado ou Gupy dinâmico) não retornam a descrição no HTML estático; nesses casos, o usuário deve utilizar a aba **"Colar descrição"**.
3. **Inferência em CPU Local:** O tempo de resposta do Ollama (`llama3.2`) em CPU sem GPU dedicada varia de 35 a 65 segundos; o timeout de 180s e a opção de modo determinístico mitigam qualquer risco de bloqueio.

---

## 10. Parecer Final

### **APTO PARA PUSH**

O código-fonte, os mecanismos de segurança, a camada de inteligência artificial com validação determinística de evidências, a suíte de 86 testes automatizados (`67 pytest` + `19 vitest`) e a documentação técnica atendem integralmente aos requisitos de segurança, qualidade e integridade para publicação no GitHub.

Nenhuma operação de `git commit` ou `git push` foi executada durante esta auditoria, aguardando autorização explícita.

