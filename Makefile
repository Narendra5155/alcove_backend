DC = docker compose
MANAGE = $(DC) exec web python manage.py

up:            ## Start everything
	$(DC) up --build -d
down:
	$(DC) down
logs:
	$(DC) logs -f web worker
migrate:
	$(MANAGE) migrate
makemigrations:
	$(MANAGE) makemigrations
seed:
	$(MANAGE) seed_demo
superuser:
	$(MANAGE) createsuperuser
shell:
	$(MANAGE) shell
css:
	$(DC) run --rm tailwind tailwindcss -i static/src/input.css -o static/css/app.css --minify
test:
	$(DC) exec -e DJANGO_SETTINGS_MODULE=alcove.settings.test web pytest -q

# ------------------------------------------------ local: Django on host, services in Docker
PY = .venv/bin/python
TAILWIND = .bin/tailwindcss
TAILWIND_URL = https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-macos-arm64

services:      ## PostGIS :5433, Redis :6380, Mailpit :8025 (SMTP :1025)
	$(DC) up -d db redis mailpit
local-migrate:
	$(PY) manage.py migrate
local-seed:
	$(PY) manage.py seed_demo
local-run:     ## Daphne-backed runserver (HTTP + WebSockets)
	$(PY) manage.py runserver 0.0.0.0:8000
local-worker:
	.venv/bin/celery -A alcove worker -l info -P threads -c 4  # prefork breaks on macOS
local-beat:
	.venv/bin/celery -A alcove beat -l info -s .celerybeat-schedule
local-css: $(TAILWIND)
	$(TAILWIND) -i static/src/input.css -o static/css/app.css --watch
local-test:
	DJANGO_SETTINGS_MODULE=alcove.settings.test .venv/bin/pytest -q
$(TAILWIND):
	mkdir -p .bin
	curl -sSLo $(TAILWIND) $(TAILWIND_URL)
	chmod +x $(TAILWIND)
