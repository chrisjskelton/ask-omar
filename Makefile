PYTHONPATH := $(CURDIR)/service

.PHONY: verify test install setup uninstall validate

verify:
	ASK_OMAR_COMMIT='$(ASK_OMAR_COMMIT)' ./scripts/verify-checkout.sh

test:
	PYTHONPATH=$(PYTHONPATH) python -m unittest discover -s tests -v

validate:
	omarchy plugin validate .

install: verify
	$(MAKE) test
	$(MAKE) validate
	./scripts/install.sh

setup: verify
	$(MAKE) test
	./scripts/install.sh --backend-only

uninstall:
	./scripts/uninstall.sh
