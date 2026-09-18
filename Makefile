PYTHONPATH := $(CURDIR)/service

.PHONY: test install setup uninstall validate

test:
	PYTHONPATH=$(PYTHONPATH) python -m unittest discover -s tests -v

validate:
	omarchy plugin validate .

install: test validate
	./scripts/install.sh

setup:
	./scripts/install.sh --backend-only

uninstall:
	./scripts/uninstall.sh
