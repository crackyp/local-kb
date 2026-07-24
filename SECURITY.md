# Security Policy

Local KB is designed for local, personal use.

## Intended exposure

By default, the backend binds to `127.0.0.1` and the app assumes trusted local access. Do not expose the API or UI to the public internet unless you add authentication, authorization, TLS, and network-level access controls.

The app can:

- read files that you ingest into `kb/raw/`
- copy local paths you explicitly ingest
- fetch URLs you submit
- send wiki/output content to your configured local LLM and embedding endpoints

## Data handling

Generated knowledge-base data under `kb/raw/`, `kb/wiki/`, `kb/outputs/`, and `kb/index/` is ignored by git except for placeholder files. Keep it that way if your sources contain private material.

## Reporting issues

Please open a GitHub issue for security concerns that do not include sensitive details. If a report needs private coordination, say so in the issue and avoid posting secrets, tokens, private documents, or private URLs.
