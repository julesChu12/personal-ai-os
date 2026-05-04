# Security Policy

## Supported Versions

This project is currently in alpha. Security fixes are applied to the default branch until the first stable release process is defined.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately to the maintainers. Do not open a public issue that includes exploit details, secrets, private logs, or user data.

Until a formal security contact is published, use the repository owner's preferred private contact channel. Include:

- Affected version or commit.
- Reproduction steps.
- Expected impact.
- Relevant logs with secrets redacted.

## Secret Handling

Never commit `.env`, API keys, database URLs with credentials, Obsidian vault data, Qdrant storage, PostgreSQL data, or generated runtime caches.

Diagnostics and error responses must not expose API keys, database passwords, complete connection strings, or provider response bodies that may contain sensitive data.

