"""Review-only local JSON records, outside every indexed corpus.

Atomic records and an OS file lock serialize review transitions. Terminal records
retain metadata, not content. A 'releasing' record is an approved, retryable
transition if indexing or final metadata persistence failed; it is never silently
reported as successful. No quarantine path is passed to any retrieval backend.
"""

import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.documents import PROJECT_ROOT
from backend.tracing import indexing_operation

QUARANTINE_DIR = PROJECT_ROOT / '.bakefix' / 'quarantine'


class QuarantineStateError(ValueError):
    """An item is not in a state that permits this review operation."""


def _root():
    from backend.documents import CORPUS_DIR
    from backend.retrieval import DATASET_DIRECTORIES
    from backend.graph_index import KESTREL_DOCS

    root = QUARANTINE_DIR.resolve()
    for corpus in [CORPUS_DIR, KESTREL_DOCS, *DATASET_DIRECTORIES.values()]:
        corpus = Path(corpus).resolve()
        if root.is_relative_to(corpus) or corpus.is_relative_to(root):
            raise ValueError('Quarantine must be separate from all indexed corpora')
    return root


def _path(identifier):
    if not isinstance(identifier, str) or re.fullmatch(r'[0-9a-f]{32}', identifier) is None:
        raise ValueError('Invalid quarantine ID')
    path = _root() / (identifier + '.json')
    if path.is_symlink():
        raise ValueError('Invalid quarantine record')
    return path


@contextmanager
def _locked():
    root = _root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(root / '.lock', flags, 0o600)
    try:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b'0')
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _write(record):
    path = _path(record['id'])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=_root(), suffix='.tmp', delete=False) as file:
            temporary = Path(file.name)
            json.dump(record, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read(identifier):
    path = _path(identifier)
    if not path.is_file():
        raise FileNotFoundError('Quarantine item not found')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('id') != identifier or record.get('status') not in {'quarantined', 'releasing', 'released', 'rejected'}:
        raise QuarantineStateError('Invalid quarantine record')
    return record


def _public(record):
    return {key: value for key, value in record.items() if key != 'content'}


def store_quarantined_document(source, content, findings, *, dataset, trace):
    with trace.span('quarantine_storage', attributes={'dataset': dataset, 'detection_count': len(findings)}):
        record = {
            'id': uuid4().hex, 'source': source, 'dataset': dataset,
            'status': 'quarantined', 'findings': findings, 'content': content,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'trace_id': trace.trace_id,
        }
        with _locked():
            _write(record)
    return {'status': 'quarantined', 'source': source, 'dataset': dataset,
            'quarantine_id': record['id'], 'findings': findings}


def list_quarantined_documents():
    root = _root()
    if not root.exists():
        return []
    with _locked():
        records = [_read(path.stem) for path in sorted(root.glob('*.json'))]
        return [_public(r) for r in records if r['status'] in {'quarantined', 'releasing'}]


def get_quarantined_document(identifier):
    _path(identifier)
    with _locked():
        return _public(_read(identifier))


@indexing_operation
def release_quarantined_document(identifier, *, approved=False, chunk_size=None, overlap=None, trace=None):
    from backend.documents import _publish_and_reindex, validate_new_document, dataset_directory
    from backend.retrieval import rebuild_index

    if approved is not True:
        raise QuarantineStateError('Explicit review approval is required')
    _path(identifier)
    with _locked(), trace.span('quarantine_release') as span:
        record = _read(identifier)
        if record['status'] not in {'quarantined', 'releasing'}:
            raise QuarantineStateError('Item has already been released or rejected')
        source, dataset, content = record['source'], record['dataset'], record['content']
        dataset_directory(dataset)
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Document cannot be empty')
        span.set_attribute('dataset', dataset)
        span.set_attribute('file_id', identifier)
        from backend.documents import resolve_document_path
        path = resolve_document_path(source, corpus_dir=dataset_directory(dataset))
        # Recovery after a crash or a failed terminal write never overwrites a file.
        resume = record['status'] == 'releasing' and path.is_file()
        if resume:
            if path.read_text(encoding='utf-8') != content:
                raise FileExistsError('Release destination contains a different document')
        else:
            validate_new_document(source, content, dataset=dataset)
        record['status'] = 'releasing'
        record['review_trace_id'] = trace.trace_id
        _write(record)  # Approval must be durable before publishing to the corpus.
        if resume:
            with trace.span('index_rebuild'):
                stats = rebuild_index(chunk_size=chunk_size, overlap=overlap, dataset=dataset, trace=trace)
        else:
            result = _publish_and_reindex(source, content, dataset=dataset,
                                          chunk_size=chunk_size, overlap=overlap, trace=trace)
            stats = result['index']
        terminal = {**record, 'status': 'released', 'review_trace_id': trace.trace_id}
        terminal.pop('content')
        _write(terminal)
        return {'status': 'indexed', 'quarantine_id': identifier, 'source': source,
                'dataset': dataset, 'findings': record['findings'], 'index': stats}


@indexing_operation
def reject_quarantined_document(identifier, *, trace=None):
    _path(identifier)
    with _locked(), trace.span('quarantine_rejection') as span:
        record = _read(identifier)
        if record['status'] != 'quarantined':
            raise QuarantineStateError('Only a quarantined item can be rejected')
        span.set_attribute('file_id', identifier)
        terminal = {**record, 'status': 'rejected', 'review_trace_id': trace.trace_id}
        terminal.pop('content')
        _write(terminal)
    return {'status': 'rejected', 'quarantine_id': identifier}
