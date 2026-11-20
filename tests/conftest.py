"""Run the existing suite against a candidate without changing active.json."""
def pytest_addoption(parser):
    parser.addoption('--release-id',default=None,help='Immutable candidate release to test')


def pytest_configure(config):
    release=config.getoption('--release-id')
    if not release:return
    from dgre_rag.storage import database
    from dgre_rag.config import root
    database.release_path(release)
    original=database.active_release
    workspace=root()
    def selected():
        # Synthetic publication tests select their own isolated DGRE_ROOT.
        return release if root()==workspace else original()
    database.active_release=selected
    config._dgre_original_active_release=original


def pytest_unconfigure(config):
    if hasattr(config,'_dgre_original_active_release'):
        from dgre_rag.storage import database
        database.active_release=config._dgre_original_active_release
