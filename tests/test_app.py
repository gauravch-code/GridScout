"""Streamlit application checks; no API key or network access needed."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from gridscout.settings import ROOT


@pytest.mark.skipif(not (ROOT/"data/demo/candidates.parquet").exists(),reason="Generate synthetic demo first")
def test_app_reranks_and_writes_no_api_memo():
    app = AppTest.from_file(str(ROOT/"app.py"),default_timeout=60).run()
    assert not app.exception
    assert len(app.slider) == 4
    app.slider[0].set_value(.8).run()
    assert not app.exception
    app.selectbox[-1].select_index(1).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["memo_agent"].calls == 0
    assert any("Why it looks promising" in item.value for item in app.markdown)


@pytest.mark.skipif(not (ROOT/"data/demo/candidates.parquet").exists(),reason="Generate synthetic demo first")
def test_app_handles_all_zero_weights():
    app = AppTest.from_file(str(ROOT/"app.py"),default_timeout=60).run()
    for slider in app.slider:
        slider.set_value(0)
    app.run()
    assert not app.exception
    assert any("positive weight" in item.value for item in app.warning)
