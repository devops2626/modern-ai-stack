.PHONY: up down build logs restart clean health test

up:
	docker compose up --build -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

restart:
	docker compose restart

health:
	curl -s http://localhost:8000/health | python -m json.tool

clean:
	docker compose down -v --remove-orphans
	rm -rf backend/uploads frontend/.next frontend/node_modules

test:
	cd backend && python -m pytest tests/ -v --tb=short
