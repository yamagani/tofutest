.PHONY: help install test fmt run compose-up compose-down compose-logs \
        docker-server docker-lambda lambda-run lambda-stop deploy destroy

ARCH ?= arm64
REGION ?= us-east-1

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install the package + dev deps into the active environment
	python -m pip install -e ".[dev]"

test: ## Run the test suite
	pytest -q

run: ## Run the API locally with autoreload (uvicorn)
	uvicorn insurance_extractor.api:app --reload --port 8000

compose-up: ## Build & start the HTTP API via docker-compose (:8000)
	docker compose up --build api

compose-down: ## Stop docker-compose services
	docker compose down

compose-logs: ## Tail compose logs
	docker compose logs -f api

docker-server: ## Build the server image
	docker build --target server -t insurance-extractor:server .

docker-lambda: ## Build the Lambda image
	docker build --target lambda --platform linux/$(ARCH) -t insurance-extractor:lambda .

lambda-run: docker-lambda ## Run the Lambda image locally via the RIE (:9000)
	docker rm -f ie-local 2>/dev/null || true
	docker run -d -p 9000:8080 --name ie-local insurance-extractor:lambda

lambda-stop: ## Stop the local Lambda container
	docker rm -f ie-local 2>/dev/null || true

deploy: ## Build+push image and apply infra (needs aws + tofu)
	scripts/deploy.sh $(REGION)

destroy: ## Tear down all AWS resources
	scripts/destroy.sh $(REGION)
