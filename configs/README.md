# Configuration

`protocol.yaml` defines ordered experiment steps. Each `expects` mapping is
matched against relational interaction event fields such as `object` and
`state`; no absolute position is used. `debounce_frames` controls consecutive
matching events, `pending_window_s` is reserved for ambiguous evidence, and
`lookback_window_s` bounds retroactive step recovery.
