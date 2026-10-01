# Atomic JSON writes for restaurant creation

Restaurant creation must preserve existing records, allocate stable IDs and
leave valid data behind when a write fails.

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
Future update and menu writes should reuse the transaction and supply their
own validation. Deletion and ID reuse policy remain future work.

Isolated tests cover restart persistence, concurrent creation, malformed
storage, invalid IDs, and failures during serialization, sync and replacement.

Sources: [Python temporary files](https://docs.python.org/3/library/tempfile.html),
[os.replace and fsync](https://docs.python.org/3/library/os.html#os.replace),
[thread locks](https://docs.python.org/3/library/threading.html#lock-objects).
