.PHONY: dev dev-down dev-clean logs shell migrate fclean re

# Bring everything up locally
dev:
	docker compose up --build

# Quietly, no logs in the terminal
dev-bg:
	docker compose up --build -d

# Stop
dev-down:
	docker compose down

# Tear everything down including the DB data (careful!)
dev-clean:
	docker compose down -v --remove-orphans

# Rebuild and start again
re: dev-clean dev

# Logs of a specific service: make logs s=backend
logs:
	docker compose logs -f $(s)

# Open a shell in the Django container
shell:
	docker compose exec backend python manage.py shell

# Open a bash shell in a container: make bash s=backend
bash:
	docker compose exec $(s) /bin/sh

# Apply migrations
migrate:
	docker compose exec backend python manage.py migrate

# Create migrations
makemigrations:
	docker compose exec backend python manage.py makemigrations

# Create a superuser
createsuperuser:
	docker compose exec backend python manage.py createsuperuser

# Collect static files
collectstatic:
	docker compose exec backend python manage.py collectstatic --noinput

# Container status
status:
	docker compose ps

dump:
	docker compose exec backend python manage.py dumpdata core --indent 2 --output fixtures/data.json
	@echo "Data saved to fixtures/data.json"

# Load data from a file
restore:
	docker compose exec backend python manage.py loaddata fixtures/data.json
	@echo "Data loaded"

# fix #7: use $(MAKE) instead of make so commands run sequentially
# and pass environment variables correctly
start:
	@$(MAKE) dev-bg
	@echo "Waiting for database..."
	@until docker compose exec db pg_isready -U $${POSTGRES_USER:-transcendence}; do sleep 1; done
	@$(MAKE) migrate
	@$(MAKE) restore

finish:
	@$(MAKE) dump && $(MAKE) dev-clean

# Prune all unused Docker images/volumes (globally!)
fclean:
	docker system prune -af --volumes
