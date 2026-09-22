.PHONY: build dev clean ingest

PORT ?= 8080

ingest:
	python3 scripts/run_ingest.py

build:
	@echo "Static portfolio — nothing to compile."
	@echo "scripts/build_site.py is retired and will not overwrite index.html."
	@test -f index.html
	@test -f css/pin.css
	@test -f og-image.png

dev:
	@echo "Dylan — local preview at http://localhost:$(PORT)"
	PORT=$(PORT) python3 scripts/preview.py

clean:
	@echo "No generated site assets to clean."
