# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `add_worklog` now accepts `started` (the work date) and `new_remaining_estimate`,
  covering the full Jira worklog form (description, date, worked, remaining estimate).

### Changed

- Switched authentication to a bearer personal access token (PAT). Users now
  provide `JIRA_HOST` (required) and `JIRA_PAT`; removed `JIRA_EMAIL`,
  `JIRA_API_TOKEN`, and the hardcoded host default.
- Targeted self-hosted Jira (Server / Data Center) exclusively: REST API v2,
  plain-text rich-text fields, and username-based user references. Removed
  Jira Cloud support (REST v3, ADF, `accountId`, the `JIRA_IS_CLOUD` flag) and
  the ADF conversion module.

### Removed

- `jira_mcp.adf` module and Cloud-only code paths.

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
