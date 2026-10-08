"""Streamlit application checks; no API key or network access needed."""
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from gridscout.settings import ROOT


@pytest.fixture
def demo_only_workspace(tmp_path,monkeypatch):
    """Mirror a fresh clone: demo files exist, public downloads and memo caches do not."""
    import gridscout.settings as settings
    if not (ROOT/"data/demo/candidates.parquet").exists():
        pytest.skip("Generate synthetic demo first")
    shutil.copytree(ROOT/"config",tmp_path/"config")
    shutil.copytree(ROOT/"data/demo",tmp_path/"data/demo")
    monkeypatch.setattr(settings,"ROOT",tmp_path)
    return tmp_path


@pytest.mark.skipif(not (ROOT/"data/demo/candidates.parquet").exists(),reason="Generate synthetic demo first")
def test_app_reranks_and_writes_no_api_memo(demo_only_workspace):
    app = AppTest.from_file(str(ROOT/"app.py"),default_timeout=60).run()
    assert not app.exception
    assert len(app.slider) == 4
    next(widget for widget in app.slider if widget.label=="Transmission proximity").set_value(.8).run()
    assert not app.exception
    next(widget for widget in app.selectbox if widget.label=="Select a top site").select_index(1).run()
    assert not app.exception
    next(widget for widget in app.button if widget.label=="Write this prospect’s memo").click().run()
    assert not app.exception
    assert app.session_state["memo_agent"].calls == 0
    assert any("Why it looks promising" in item.value for item in app.markdown)


@pytest.mark.skipif(not (ROOT/"data/demo/candidates.parquet").exists(),reason="Generate synthetic demo first")
def test_app_handles_all_zero_weights(demo_only_workspace):
    app = AppTest.from_file(str(ROOT/"app.py"),default_timeout=60).run()
    for slider in app.slider:
        slider.set_value(0)
    app.run()
    assert not app.exception
    assert any("positive weight" in item.value for item in app.warning)
