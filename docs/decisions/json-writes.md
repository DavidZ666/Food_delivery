# Atomic JSON writes

Restaurant and menu writes must preserve existing records, retain
stable IDs and leave valid data behind when a write fails.

Use a shared process lock around the entire read/modify/write transaction.
Validate persisted records and unique positive integer IDs before allocating
new IDs (using the persistent high-water mark for products). Write JSON to a
temporary file in the same directory, flush and
sync it, then replace the target with `os.replace`. Readers see the old or new
document. Exceptions before replacement preserve the original; temporary
files are cleaned up.

Writing directly to the target risks truncation. Locking only replacement
allows duplicate IDs and lost updates. A database would support broader
concurrency but falls outside the course's JSON/CSV persistence requirement.

This choice supports one application process on a local filesystem. Multiple
workers and external writers require a shared cross-process locking strategy.
The directory entry is not synced, so power-loss durability is not guaranteed.
Restaurant and menu creation, updates and deletion reuse this transaction with
their own validation. All menu mutations share the same lock.
Product IDs come from a persistent high-water mark in `product_ids.json`, saved
under the same reentrant storage lock before creation or deletion changes the
products file. Deleted IDs are never reissued while this history is preserved;
a failed product write can skip an ID. Without a counter, migration seeds it
from live products and references in existing carts and orders; malformed
references fail closed. IDs erased before migration and absent everywhere cannot
be recovered. Keep the counter with backups rather than resetting it.

Checkout and cart mutations share a per-cart lock, acquired before the storage
lock. Checkout atomically appends the order and an internal `cart_consumption`
receipt (`cart_id`, `generation`) to `orders.json`. Repository cart reads apply
that receipt as an empty cart, under the storage lock. No cart file write or
rollback is needed: failed order replacement leaves cart bytes unchanged and
readers never see a transient clear. The next successful cart mutation starts
empty and persists the next `checkout_generation`; legacy carts default to 0.
These fields are internal; public cart/order response shapes are unchanged.

Raw cart files can retain purchased items until that mutation. Access carts only
through the repository and back up/restore carts and orders together. Atomic
replacement commits one file, not a general transaction across files.

Isolated tests cover restart persistence, concurrent creation, malformed
storage, invalid IDs, and failures during serialization, sync and replacement.

Implementation: [shared transaction](../../app/repositories/json_store.py),
[restaurant writes](../../app/repositories/restaurant_repo.py) and
[menu writes](../../app/repositories/product_repo.py). Services check the selected
restaurant; repositories enforce product IDs, ownership and persisted field rules.

Evidence: [transaction failures and concurrency](../../tests/test_json_writes.py),
[menu creation](../../tests/test_menu_creation.py),
[mixed partial updates](../../tests/test_menu_update_transaction.py),
[mixed deletion](../../tests/test_menu_delete_transaction.py),
[restart persistence](../../tests/test_m1_acceptance.py),
[checkout integrity](../../tests/test_checkout_integrity.py),
[checkout commit failures](../../tests/test_checkout_atomicity.py) and
[identity migration](../../tests/test_product_identity_migration.py). These tests use temporary
data.

Sources: [Python temporary files](https://docs.python.org/3/library/tempfile.html),
[os.replace and fsync](https://docs.python.org/3/library/os.html#os.replace),
[reentrant locks](https://docs.python.org/3/library/threading.html#rlock-objects).
The replacement and reentrant-lock references were retrieved with Exa.
