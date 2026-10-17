# Atomic JSON writes

Restaurant writes and menu creation must preserve existing records, retain
stable IDs and leave valid data behind when a write fails.

Use a shared process lock around the entire read/modify/write transaction.
Validate persisted records and unique positive integer IDs before allocating
`max(id) + 1`. Write JSON to a temporary file in the same directory, flush and
sync it, then replace the target with `os.replace`. Readers see the old or new
document. Exceptions before replacement preserve the original; temporary
files are cleaned up.

Writing directly to the target risks truncation. Locking only replacement
allows duplicate IDs and lost updates. A database would support broader
concurrency but falls outside the course's JSON/CSV persistence requirement.

This choice supports one application process on a local filesystem. Multiple
workers and external writers require a shared cross-process locking strategy.
The directory entry is not synced, so power-loss durability is not guaranteed.
Restaurant creation/updates and menu creation reuse this transaction with
their own validation. Menu updates and deletions still require sequential
requests with all other menu writes; they do not yet use this transaction.
Product IDs use the stored maximum plus one, so deleting the highest ID can
allow reuse.

Isolated tests cover restart persistence, concurrent creation, malformed
storage, invalid IDs, and failures during serialization, sync and replacement.

Sources: [Python temporary files](https://docs.python.org/3/library/tempfile.html),
[os.replace and fsync](https://docs.python.org/3/library/os.html#os.replace),
[thread locks](https://docs.python.org/3/library/threading.html#lock-objects).
