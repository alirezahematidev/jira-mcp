# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Hardcoded the Jira host to `https://works.digikala.com` and locked
  authentication to HTTP basic. Users now only provide `JIRA_EMAIL` and
  `JIRA_API_TOKEN`. Deployment defaults to Jira Cloud (override with
  `JIRA_IS_CLOUD=false`).

## [0.1.0]

### Added

- Initial release.
- MCP server (stdio transport) exposing 18 Jira tools: issue search (JQL),
  read/create/update/delete, comments, workflow transitions, assignment,
  worklogs, issue links, projects, users, and agile boards/sprints.
- Support for Jira Cloud (REST API v3 + ADF) and Jira Server / Data Center
  (REST API v2), selected automatically.
- Read-only mode via `JIRA_READ_ONLY`.
- Plain-text ↔ Atlassian Document Format conversion.

[Unreleased]: https://github.com/alirezahematidev/jira-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/alirezahematidev/jira-mcp/releases/tag/v0.1.0
