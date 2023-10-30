.DEFAULT_GOAL := run

venv:
	python3.12 -m venv .venv
	
install:
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/python src/power_aware_iot.py

clean:
	rm -rf .venv