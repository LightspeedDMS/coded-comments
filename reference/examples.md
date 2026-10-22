# coded-comments: examples

Illustrative names. Placement in context; rules are in `what.md` and `how.md`.

Private helper: doc deleted (restated the name), one hidden rule kept.

```python
def _flush(self):
    # ^ order _flush before close; close drops _buf
    self._sink.write(self._buf)
```

Exported API (`__all__`): capped prose doc, no coded syntax inside it.

```python
def connect(url: str, timeout: float = 5.0) -> Conn:
    """Open a pooled connection.

    timeout: seconds per attempt, not total.
    """
```

Trailing line governs its own statement.

```ts
const MAX_BATCH = 500; // ^ external vendor batch API accepts <= 500 items; doc:vendor-api#limits
```

A run governs the declaration below it.

```go
// ^ coupled Status values with web/src/status.ts:STATUS_LABELS
// ^ hazard reordering iota => stored ints change meaning; #88
const (
```

```sql
-- ^ invariant column order = (tenant_id, created_at); matches orders_by_tenant query
CREATE INDEX ix_orders_tenant ON orders (tenant_id, created_at);
```

```pascal
// ^ invariant FCount <= Length(FItems); Grow keeps it
procedure TList.Add(const Item: TItem);
```

Delete, write nothing: `// Increment the counter` (restates), `// Added for story #312` (history),
`// ===== Helpers =====` (banner), `// Now validate the input` (narrates).
