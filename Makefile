init:
	@python3 -m venv .venv
	@.venv/bin/pip install -r src/requirements.txt

run:
	@.venv/bin/streamlit run src/app.py