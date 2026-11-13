# CareerMatch AI

Plataforma inteligente de análise de compatibilidade entre currículos e vagas (**Matching ATS**) e geração de **Currículos ATS Friendly**, construída com **React 19 + TypeScript + ShadCN/UI** no frontend e **Python 3.12 + FastAPI + Pydantic v2** no backend, integrada ao **Ollama (`llama3.2`)** para inferência local gratuita e privada.

> **Princípio Inegociável (Zero Fabricação):** O CareerMatch AI melhora a estrutura, a clareza e o alinhamento terminológico das experiências reais da pessoa candidata, mas **nunca inventa** cargos, empresas, períodos, formações, certificações ou competências técnicas não comprovadas.

---

## Sumário Executivo (Desafio DIO)

### 1. O Problema Resolvido
Candidatos qualificados frequentemente são reprovados na triagem inicial por sistemas *Applicant Tracking System* (ATS) devido a problemas estruturais no currículo (layouts em múltiplas colunas, tabelas, ausência de termos canônicos exigidos na vaga) ou por desconhecerem quais requisitos obrigatórios e desejáveis precisam ser evidenciados. Ao mesmo tempo, ferramentas genéricas de IA costumam "alucinar" qualificações inexistentes, expondo o candidato a riscos éticos em entrevistas.

### 2. Evolução do Megaprompt e Arquitetura de IA Responsável
O projeto evoluiu de um megaprompt conceitual para uma arquitetura em camadas com **separação estrita entre interpretação assistida por IA e cálculo determinístico**:
- **Camada Multiprovedor (`backend/app/ai/providers/`):** Suporta **Ollama (`llama3.2`)** localmente como provedor padrão gratuito, além de **Google Gemini** e **OpenAI** como provedores opcionais via configuração, sem alterar nenhuma regra de negócio.
- **Fallback Determinístico Transparente:** Quando nenhum LLM está disponível ou ocorre timeout, o sistema aciona parsers determinísticos e informa explicitamente na interface (`extraction_method: "deterministic_fallback"`), sem jamais simular que o resultado veio de uma IA.
- **Validação Determinística de Evidências (`evidence_validator.py`):** Cada experiência, formação, certificação e competência extraída deve conter um trecho literal (`evidence_quote`) comprovável no texto original do currículo.
- **Defesa contra Prompt Injection:** Textos de currículos e descrições de vagas são encapsulados em delimitadores XML (`<untrusted_resume_text>`, `<untrusted_job_text>`) com instruções de sistema que proíbem seguir comandos contidos nos documentos.

### 3. Como Funciona a Análise e o Matching Determinístico
1. **Currículo (`/curriculo`):** Upload seguro (`PDF`, `DOCX`, `TXT`) validado por *magic bytes* (`upload_guard.py`) ou colagem de texto → extração estruturada → validação de evidências → revisão e confirmação humana obrigatória.
2. **Vaga (`/vaga`):** Colagem da descrição, preenchimento manual ou extração de URL pública protegida contra SSRF (`ssrf_guard.py`) → classificação de requisitos em `obrigatorio`, `desejavel`, `contextual` e `nao_especificado` → revisão e confirmação humana.
3. **Matching ATS (`/compatibilidade`):** O motor determinístico (`matching_engine.py`) compara o currículo confirmado e a vaga confirmada aplicando pesos documentados (`30%` Competências Técnicas, `25%` Experiência Profissional, `20%` Requisitos Obrigatórios, `10%` Formação/Certificações, `10%` Comportamentais, `5%` Palavras-Chave), com renormalização automática de categorias não aplicáveis.
   - **Regra sobre Tecnologias Correlatas:** Experiência em `Docker` e `AWS` **não** comprova automaticamente conhecimento em `Kubernetes` (`state: "nao_identificado"`, `credit: 0.0`). Tecnologias correlatas geram apenas recomendações consultivas.
4. **Currículo ATS Friendly (`/curriculo-ats`):** Reordena competências comprovadas, alinha o resumo profissional com apoio do Ollama local, passa pelo guardião determinístico anti-fabricação (`verify_and_sanitize_ats_resume`), exibe o histórico de alterações com justificativas e exige aprovação humana antes de exportar em **PDF**, **DOCX**, **TXT** ou **Markdown**.

---

## Status do Roadmap

| Fase | Escopo | Status |
|---|---|---|
| **1. Fundação** | Monorepo, layout, navegação, API base, sessões anônimas, CSRF, segurança, Docker | ✅ Concluída |
| **2. Currículos** | Upload seguro (PDF/DOCX/TXT), extração, parsing com Ollama + fallback, revisão e confirmação | ✅ Concluída |
| **3. Vagas** | Análise de descrição colada, URL pública com proteção anti-SSRF, manual e confirmação | ✅ Concluída |
| **4. Matching ATS** | Motor determinístico ponderado, 5 estados de avaliação, evidências e dashboard Recharts | ✅ Concluída |
| **5. Currículo ATS** | Otimização sem fabricação, histórico de alterações, aprovação humana e exportação PDF/DOCX | ✅ Concluída |
| **6. Assistente** | Chat contextual de carreira | ⏳ Planejada |
| **7. Qualidade E2E** | Automação Playwright ponta a ponta | ⏳ Planejada |

---

## Stack Tecnológica

- **Frontend:** React 19, TypeScript 5.9, Vite 8, Tailwind CSS v4, ShadCN/UI (Radix UI), Lucide Icons, React Router v7, TanStack Query v5, React Hook Form, Zod, Recharts, Vitest e Testing Library.
- **Backend:** Python 3.12, FastAPI, Pydantic v2, Uvicorn, HTTPX, PyMuPDF / pypdf, python-docx, ReportLab e Pytest.
- **Inteligência Artificial:** Ollama local (`llama3.2` em `http://localhost:11434`) como provedor principal gratuito + suporte opcional a Google Gemini e OpenAI + fallback determinístico.

---

## Variáveis de Ambiente (`.env`)

Copie o arquivo de exemplo antes de iniciar:

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` ou `production` |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Endereço e porta do backend FastAPI |
| `FRONTEND_URL` | `http://localhost:5173` | Origens permitidas no CORS (separadas por vírgula) |
| `AI_PROVIDER` | `ollama` | Provedor ativo: `ollama` (padrão local), `gemini` ou `openai` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL do servidor Ollama local |
| `OLLAMA_MODEL` | `llama3.2` | Modelo utilizado no Ollama |
| `GEMINI_API_KEY` | *(vazio)* | Chave opcional do Google AI Studio (`AIza...`) |
| `OPENAI_API_KEY` | *(vazio)* | Chave opcional da OpenAI (`sk-...`) |
| `AI_MODEL` | *(vazio)* | Sobrescreve o modelo padrão do provedor quando preenchido |
| `AI_TEMPERATURE` | `0.2` | Temperatura de geração |
| `AI_TIMEOUT_SECONDS` | `180.0` | Timeout de inferência (dimensionado para execução local em CPU) |
| `AI_FALLBACK_DETERMINISTIC` | `true` | Aciona extração determinística automática se o LLM estiver indisponível |
| `MAX_UPLOAD_MB` | `10` | Tamanho máximo de arquivo para upload de currículo |
| `SESSION_TTL_MINUTES` | `60` | Tempo de expiração da sessão anônima em memória |
| `LOG_LEVEL` | `INFO` | Nível de log estruturado (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Instruções de Instalação e Execução Local

### Pré-requisitos
- **Python 3.12+**
- **Node.js 20+**
- **(Opcional, recomendado):** [Ollama](https://ollama.com/) instalado localmente com o modelo `llama3.2` (`ollama pull llama3.2`). Caso o Ollama não esteja em execução, a aplicação funciona integralmente através do fallback determinístico.

### 1. Executar o Backend (FastAPI)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

### 2. Executar o Frontend (React + Vite)
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

- **Aplicação Web:** `http://localhost:5173`
- **Documentação Interativa da API (Swagger/OpenAPI):** `http://localhost:8000/api/docs`
- **Healthcheck:** `http://localhost:8000/api/v1/health`

---

## Executando os Testes Automatizados

```powershell
# Backend (67 testes unitários, de segurança e de integração)
cd backend
.\.venv\Scripts\python -m pytest -v

# Frontend (19 testes Vitest + verificação de tipos TypeScript + build de produção)
cd frontend
npm.cmd test
npx.cmd tsc -b
npm.cmd run build
```

---

## Limitações Conhecidas

1. **Vagas em Portais SPA (Renderização no Cliente):** O endpoint `POST /api/v1/jobs/extract-url` realiza download seguro do HTML estático com bloqueio anti-SSRF e não executa JavaScript remoto. Para vagas em portais dinâmicos (LinkedIn autenticado, Gupy, Workday), recomenda-se copiar e colar a descrição na aba **"Colar descrição"**.
2. **Documentos PDF Digitalizados (Imagens sem OCR):** PDFs gerados por escaneamento sem camada de texto selecionável são identificados e rejeitados com o código estruturado `ocr_not_available`, orientando o usuário a enviar um PDF textual, DOCX ou colar o texto.
3. **Latência do Ollama em CPU:** Em máquinas sem GPU dedicada (`VRAM = 0`), a inferência local com `llama3.2` leva entre 35 e 65 segundos. A interface oferece a opção de execução instantânea em modo determinístico.
4. **Sessões em Memória:** Por diretriz de privacidade (LGPD / retenção zero), os dados residem apenas em memória RAM durante a sessão ativa (`TTL = 60 min`) e são descartados ao clicar em **"Limpar meus dados"** ou reiniciar o servidor.

---

## Documentação Complementar e Licença

- [Arquitetura do Sistema](docs/architecture.md)
- [Referência da API REST v1](docs/api.md)
- [Metodologia de Compatibilidade ATS](docs/matching-methodology.md)
- [Privacidade, Segurança e LGPD](docs/privacy.md)
- [Auditoria Técnica Pré-Publicação](docs/AUDITORIA_PRE_PUBLICACAO.md)
- Distribuído sob a [Licença MIT](LICENSE).
