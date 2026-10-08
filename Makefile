.PHONY: setup demo data app test sources memos
PYTHON ?= python
setup:
	$(PYTHON) -m pip install -r requirements.txt
demo:
	$(PYTHON) -m gridscout demo
data:
	$(PYTHON) -m gridscout pipeline --download
	$(PYTHON) -m gridscout features
app:
	$(PYTHON) -m streamlit run app.py
test:
	$(PYTHON) -m pytest -q
sources:
	$(PYTHON) -m gridscout verify-sources
memos:
	$(PYTHON) -m gridscout memos --top 3
