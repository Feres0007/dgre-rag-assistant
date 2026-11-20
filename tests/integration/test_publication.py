import sqlite3
import pytest
from dgre_rag.storage.database import initialize,publish,active_release,restore,backup


def test_idempotent_publication_and_failed_replacement(tmp_path,monkeypatch):
    monkeypatch.setenv('DGRE_ROOT',str(tmp_path))
    run=tmp_path/'data/runs/synthetic-test/database.sqlite'
    db=initialize(run)
    db.execute("INSERT INTO run_metadata VALUES ('validated','true')")
    db.commit();db.close()
    first=publish('synthetic-test','test')
    assert publish('synthetic-test','test')==first
    assert (backup()/ 'database.sqlite').exists()
    with sqlite3.connect(run) as db:
        # Inject a foreign-key violation only into the isolated synthetic fixture.
        db.execute("INSERT INTO entities VALUES ('e','synthetic','Synthetic')")
        db.execute("INSERT INTO entity_mentions VALUES ('m','e','missing-source','123','Synthetic','test')")
    with pytest.raises(ValueError,match='INTEGRITY'):publish('synthetic-test','invalid')
    assert active_release()==first
    restore(first)
    assert active_release()==first
