SHELL := /bin/bash

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose exec web python manage.py migrate

migrations:
	docker compose exec web python manage.py makemigrations

superuser:
	docker compose exec \
	  -e DJANGO_SUPERUSER_USERNAME=admin@example.com \
	  -e DJANGO_SUPERUSER_EMAIL=admin@example.com \
	  -e DJANGO_SUPERUSER_PASSWORD=admin \
	  web python manage.py createsuperuser --noinput

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

test:
	docker compose exec web pytest

shell:
	docker compose exec web python manage.py shell_plus || docker compose exec web python manage.py shell


