"""pytest plugin: run the collected tests in reverse order (t24a order check)."""
import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(session, config, items):
    items.reverse()
