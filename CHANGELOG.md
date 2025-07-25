# Changelog

All notable changes to this project will be documented in this file.

This project follows the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) principles.

The full changelog is maintained in [changelogs/changelog.yml](./changelogs/changelog.yml).

## [1.0.0] - Initial Release

### Added
- Initial release of the `ravendb.ravendb` Ansible Collection.
- Added `ravendb_node` role for setting up RavenDB servers.
- Added `ravendb_python_client_prerequisites` role for managing Python dependencies.
- Added modules:
  - `ravendb.ravendb.database` for managing RavenDB databases.
  - `ravendb.ravendb.index` for managing RavenDB indexes and index modes.
  - `ravendb.ravendb.node` for adding nodes to a RavenDB cluster.

## [1.0.1] - 2025-07-15

### Fixed
- `galaxy.yml` now points to the collection repo's issue tracker.
- Removed broken external changelog link in `CHANGELOG.md`.
- Added `attributes:` with `check_mode` support to all modules.
- Replaced partial module names in roles/playbooks with full FQCNs.
- Removed leftover files: `ansible.cfg`, `inventories/`, etc.
- CI matrix now includes `stable-2.18`, `stable-2.19`, and Python 2.7 testing.
