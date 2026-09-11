.PHONY: dev build test lint package production backend-dev doctor

PNPM ?= pnpm
PYTHON ?= python3

dev:
	$(PNPM) dev

build:
	$(PNPM) build

backend-dev:
	$(PYTHON) -m uvicorn backend.app.main:app --reload --port 8787

test:
	$(PNPM) build
	$(PYTHON) -m compileall backend/app

lint:
	$(PNPM) exec tsc --noEmit
	$(PYTHON) -m compileall backend/app

package:
	bash -n installer/install.sh installer/uninstall.sh installer/update.sh
	install -m 0644 systemd/rabby-host.service /tmp/rabby-host.service

production: build package
	@echo "Frontend build and Debian artifact validation complete. Run installer/install.sh on Debian 12/13."

doctor:
	$(PYTHON) -m backend.app.cli doctor


.PHONY: clean
clean:
	rm -rf .next
