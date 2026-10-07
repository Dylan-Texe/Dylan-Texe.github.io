.PHONY: build dev clean

PORT ?= 8080

build:
	@echo "Static portfolio - nothing to compile."
	@test -f index.html
	@test -f css/site.css
	@test -f og-image.png
	@test -f og-image-v2.png
	@test -f ufo/index.html
	@test -f js/play-urls.js
	@test -f assets/vapor-sky.svg
	@test -f assets/vapor-sky-live.svg
	@test -f js/scene.js
	@test -f js/deck.js

dev:
	@echo "Dylan - local preview at http://localhost:$(PORT)"
	PORT=$(PORT) python3 scripts/preview.py

clean:
	@echo "No generated site assets to clean."
