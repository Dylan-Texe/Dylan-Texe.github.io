.PHONY: build dev clean

PORT ?= 8080

build:
	@echo "Static portfolio - nothing to compile."
	@test -f index.html
	@test -f css/site.css
	@test -f og-image.png

dev:
	@echo "Dylan - local preview at http://localhost:$(PORT)"
	PORT=$(PORT) python3 scripts/preview.py

clean:
	@echo "No generated site assets to clean."
