# Lattice Vault UI v2 (visual prototype)

Local, read-only web UI for a Lattice Vault SQLite DB. Python stdlib only (`http.server` + `sqlite3`), no build step.

This is the **v2 visual prototype**. The original v1 UI in `../lattice-vault-ui/` is untouched.

Reuses `vault.py` from a sibling `lattice-vault` or `lattice-vault-release` checkout (override with `VAULT_SRC`).

Visual tokens come from Brand Designer + Anti-Slop Critic (paper background, Source Serif 4 + IBM Plex Mono, ink accent, no SaaS chrome).

## Sibling layout

```sh
# folders must be siblings, e.g.:
#   lattice-vault/          (or lattice-vault-release/)  — provides vault.py
#   lattice-vault-ui-v2/    — this repo
```

`server.py` looks for `../lattice-vault/vault.py`, then `../lattice-vault-release/vault.py`. Override: `VAULT_SRC=/path/to/vault`.

## Clone

```sh
git clone https://github.com/keremtalhaoral/lattice-vault.git
git clone https://github.com/keremtalhaoral/lattice-vault-ui-v2.git
```

## Run

```sh
# seed a demo DB (uses sibling vault examples/seed.py)
python3 ../lattice-vault/examples/seed.py demo

VAULT_DB=demo/vault.db python3 server.py
# open http://127.0.0.1:8765/

python3 -m unittest test_api
```

- Binds `127.0.0.1` only; DB opened with `file:...?mode=ro` per request (never `vault.connect()`); POST → 405.
- `GET /api/events?status=&trust=&limit=&offset=` — newest first (HLC, then id). Status: `proposed|active|rejected|reverted`. Trust: `verified|agent|unverified`. Response: `{total, items:[{id,type,ts,source,status,trust,text_short,...}]}`.
- `GET /api/search?q=` — `vault.search()` (FTS5 + Turkish `tr_norm`).
- Encrypted payload fields show as `[encrypted]`, redacted as `[redacted]`.
- Approve is disabled in the UI: “Onay yalnızca CLI ile (adım 2).”
