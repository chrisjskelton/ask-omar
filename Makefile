PYTHONPATH := $(CURDIR)/service

.PHONY: test install uninstall validate

test:
	PYTHONPATH=$(PYTHONPATH) python -m unittest discover -s tests -v

validate:
	omarchy plugin validate plugin

install: test validate
	./scripts/install.sh

uninstall:
	./scripts/uninstall.sh
