ENV_NAME = atlas
MAMBA = micromamba run -n $(ENV_NAME)

.PHONY: env install dev backend frontend lint test build docker-up docker-down

env:
	micromamba env create -f environment.yml --yes
	cd frontend && npm install

install:
	$(MAMBA) pip install -e ".[dev]"
	cd frontend && npm install

dev:
	@echo "Starting Atlas backend + titiler + frontend..."
	@trap 'kill 0' EXIT; \
	$(MAMBA) uvicorn atlas.main:app --reload --host 0.0.0.0 --port 8000 & \
	$(MAMBA) uvicorn titiler.application.main:app --host 0.0.0.0 --port 8001 & \
	cd frontend && npm run dev & \
	wait

backend:
	$(MAMBA) uvicorn atlas.main:app --reload --host 0.0.0.0 --port 8000

titiler:
	$(MAMBA) uvicorn titiler.application.main:app --host 0.0.0.0 --port 8001

frontend:
	cd frontend && npm run dev

lint:
	$(MAMBA) ruff check src/ tools/
	cd frontend && npx tsc --noEmit

test:
	$(MAMBA) pytest tests/ tools/ -v

build:
	cd frontend && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down
