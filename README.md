# CareerMatch AI

Compara um currículo com uma vaga, mostra a compatibilidade (palavras-chave encontradas e as que faltam) e gera uma versão **ATS friendly** do currículo, pronta para exportar em PDF ou DOCX.

> **Regra central:** a aplicação melhora como a pessoa se apresenta e **nunca inventa** cargos, experiências, competências, certificações ou resultados.

Não tem login: cada visitante recebe uma sessão anônima e temporária, que é apagada automaticamente.

## Status do roadmap

| Fase | Escopo | Status |
|---|---|---|
| 1. Fundação | Monorepo, layout, navegação, API base, sessões, segurança, Docker | ✅ Concluída |
| 2. Currículos | Upload, extração, parsing por IA, revisão | ⏳ |
| 3. Vagas | Texto, URL (anti-SSRF), manual | ⏳ |
| 4. Matching | Score determinístico e dashboard | ⏳ |
| 5. ATS | Otimização, templates, editor, exportação PDF/DOCX | ⏳ |
| 6. Assistente | Chat contextual | ⏳ |
| 7. Qualidade | E2E (Playwright), hardening, documentação final | ⏳ |

## Stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, componentes ShadCN/UI (Radix), Lucide, React Router, TanStack Query, React Hook Form, Zod, Recharts, Vitest e Testing Library.
- **Backend:** Python 3.12, FastAPI, Pydantic v2, Uvicorn, HTTPX, PyMuPDF, python-docx, ReportLab e pytest.
- **IA:** Google Gemini ou OpenAI, atrás de uma interface única (`app/ai/providers`).

## Requisitos

- Node.js 20+ (testado com 26)
- Python 3.12+
- (Opcional) Docker e Docker Compose
- Uma chave de API do Gemini **ou** da OpenAI (necessária a partir da Fase 2)

## Configuração

```bash
cp .env.example .env      # no Windows: copy .env.example .env
# edite .env e preencha GEMINI_API_KEY (ou OPENAI_API_KEY com AI_PROVIDER=openai)
```

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test` ou `production` (em produção exige chave de IA e usa cookie `Secure`) |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Bind do backend |
| `FRONTEND_URL` | `http://localhost:5173` | Origens permitidas no CORS (separadas por vírgula) |
| `AI_PROVIDER` | `gemini` | `gemini` ou `openai` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` | vazio | Chaves (só no backend, nunca no frontend) |
| `AI_MODEL` | vazio | Modelo; se vazio, usa o padrão do provedor |
| `AI_TEMPERATURE` | `0.2` | Temperatura do modelo |
| `MAX_UPLOAD_MB` | `10` | Limite de upload |
| `SESSION_TTL_MINUTES` | `60` | Expiração da sessão por inatividade |
| `LOG_LEVEL` | `INFO` | Nível de log (JSON estruturado) |

## Execução local

**Atalho (Windows):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```
**Atalho (Linux/macOS):** `./scripts/dev.sh`

**Manual:**
```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (em outro terminal)
cd frontend
npm install                   # no PowerShell com scripts bloqueados, use npm.cmd
npm run dev
```

- App: http://localhost:5173
- API docs (OpenAPI): http://localhost:8000/api/docs
- Health: http://localhost:8000/api/v1/health

O Vite faz proxy de `/api` para o backend, então os cookies de sessão ficam na mesma origem.

## Testes

```bash
cd backend && .venv/Scripts/python -m pytest
cd frontend && npm test
cd frontend && npm run build
```

## Docker

```bash
docker compose up --build
```
App em http://localhost:8080 (o Nginx serve o frontend e faz proxy de `/api` para o backend).

## Documentação

- [Arquitetura](docs/architecture.md)
- [API](docs/api.md)
- [Metodologia de matching](docs/matching-methodology.md)
- [Privacidade](docs/privacy.md)
