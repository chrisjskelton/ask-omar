PYTHONPATH := $(CURDIR)/service

.PHONY: verify test install setup uninstall validate

verify:
	@ASK_OMAR_COMMIT='$(ASK_OMAR_COMMIT)' ./scripts/verify-checkout.sh

test:
	PYTHONPATH=$(PYTHONPATH) python -m unittest discover -s tests -v

validate:
	omarchy plugin validate .

# Since 0.1.4 the widget is installed with `omarchy plugin add`, and this
# checkout only sets up the companion backend. See README.md#install.
install:
	@echo "Ask Omar installs with: omarchy plugin add https://github.com/chrisjskelton/ask-omar.git" >&2
	@echo "Then run make setup in the plugin folder. See README.md#install." >&2
	@exit 1

# The test suite is for development and CI; setup only checks the release
# commit and the plugin, then installs.
setup: verify
	@$(MAKE) --no-print-directory -s validate
	@./scripts/install.sh

uninstall:
	@./scripts/uninstall.sh
