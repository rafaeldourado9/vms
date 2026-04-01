.PHONY: help up down build logs test test-unit test-bdd test-cov test-e2e lint typecheck migrate shell

# ─── Variáveis ──────────────────────────────────────────────────────────────
API_SERVICE=api
COMPOSE=docker compose
PYTEST=python -m pytest

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Stack ───────────────────────────────────────────────────────────────────
up: ## Sobe a stack completa
	$(COMPOSE) up -d

up-dev: ## Sobe em modo dev (com hot-reload)
	$(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml up

down: ## Derruba a stack
	$(COMPOSE) down

down-v: ## Derruba a stack e apaga volumes
	$(COMPOSE) down -v

build: ## Rebuilda todas as imagens
	$(COMPOSE) build --no-cache

logs: ## Segue logs de todos os serviços
	$(COMPOSE) logs -f

logs-api: ## Segue logs da API
	$(COMPOSE) logs -f $(API_SERVICE)

# ─── Migrations ──────────────────────────────────────────────────────────────
migrate: ## Roda migrations pendentes
	$(COMPOSE) exec $(API_SERVICE) alembic upgrade head

migrate-create: ## Cria nova migration (uso: make migrate-create MSG="descrição")
	$(COMPOSE) exec $(API_SERVICE) alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Mostra histórico de migrations
	$(COMPOSE) exec $(API_SERVICE) alembic history

migrate-downgrade: ## Reverte última migration
	$(COMPOSE) exec $(API_SERVICE) alembic downgrade -1

# ─── Testes ──────────────────────────────────────────────────────────────────
test: ## Roda todos os testes (exceto e2e)
	cd api && $(PYTEST) tests/ -m "not e2e" -v

test-unit: ## Roda apenas testes unitários
	cd api && $(PYTEST) tests/unit/ -v

test-bdd: ## Roda apenas testes BDD
	cd api && $(PYTEST) tests/bdd/ -v

test-analytics: ## Roda testes do analytics service
	cd analytics && $(PYTEST) tests/ -v

test-agent: ## Roda testes do edge agent
	cd edge_agent && $(PYTEST) tests/ -v

test-cov: ## Roda com relatório de coverage
	cd api && $(PYTEST) tests/ -m "not e2e" \
		--cov=src/vms \
		--cov-report=term-missing \
		--cov-report=html:coverage_html \
		--cov-fail-under=80 \
		-v

test-e2e: ## Roda testes E2E (requer stack docker up)
	cd api && $(PYTEST) tests/ -m e2e -v

# ─── Qualidade ────────────────────────────────────────────────────────────────
lint: ## Roda ruff check
	cd api && ruff check src/ tests/
	cd analytics && ruff check src/ tests/
	cd edge_agent && ruff check src/ tests/

lint-fix: ## Corrige problemas ruff automaticamente
	cd api && ruff check --fix src/ tests/

format: ## Formata código com ruff
	cd api && ruff format src/ tests/
	cd analytics && ruff format src/ tests/

typecheck: ## Roda mypy
	cd api && mypy src/vms
	cd analytics && mypy src/analytics
	cd edge_agent && mypy src/agent

check: lint typecheck test ## Roda lint + typecheck + test

# ─── Dev Utilities ────────────────────────────────────────────────────────────
shell: ## Shell na API
	$(COMPOSE) exec $(API_SERVICE) bash

shell-db: ## psql no banco
	$(COMPOSE) exec postgres psql -U vms -d vms

create-tenant: ## Cria tenant admin (uso: make create-tenant NAME="X" EMAIL="x@y.com" PASS="z")
	$(COMPOSE) exec $(API_SERVICE) python -m vms.scripts.create_tenant \
		--name "$(NAME)" --email "$(EMAIL)" --password "$(PASS)"

backup: ## Backup do banco
	./infra/scripts/backup_db.sh

health: ## Checa saúde da stack
	curl -s http://localhost/health | python -m json.tool

# ─── Frontend ────────────────────────────────────────────────────────────────
dev-fe: ## Inicia o frontend em modo dev com hot-reload
	cd frontend && npm run dev

build-fe: ## Gera build de produção do frontend
	cd frontend && npm run build
