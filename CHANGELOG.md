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

## [1.0.2] - 2025-07-29

### Changed
- Flattened arguments in the `ravendb.ravendb.node` module for clarity (removed nested `node:` dict).
- Reorganized common module arguments (`url`, `database_name`, `certification_path`, `ca_cert_path`) into `module_utils` and `doc_fragments`.

### Fixed
- Ensured all modules correctly import and expose shared argument definitions.


## [1.0.3] - 2025-08-19

### Added
- Support for encrypted databases in `ravendb.ravendb.database`:
  - Generate or read encryption keys.
  - Distribute keys across all cluster nodes.
  - Create databases with encryption enabled.
- Ability to manage database settings via the `ravendb.ravendb.database` module.
- Joining Let's Encrypt–secured nodes into existing RavenDB clusters.


## [1.0.4] - 2025-09-04

### Added
- Database placement on specific nodes via `topology_members` in `ravendb.ravendb.database`.
- Index deployment mode support (`rolling`, `parallel`) in `ravendb.ravendb.index`.
- Per-index configuration reconciliation via `index_configuration` in `ravendb.ravendb.index`.
- New `ravendb.ravendb.healthcheck` module:
  - Available checks: `node_alive`, `cluster_connectivity`, `db_groups_available`, `db_groups_available_excluding_target`.
  - TLS parameters: `validate_certificate`, `certificate_path`, `ca_cert_path`.
  - Timing/behavior: `max_time_to_wait`, `retry_interval_seconds`, `db_retry_interval_seconds`, `on_db_timeout`.
  - Safety: auto-disables validation for IP hosts on node/cluster checks, read-only (no changes).
- New `ravendb.ravendb.connection_string` module:
  - Providers: `RAVEN`, `SQL`, `OLAP`, `ELASTIC_SEARCH`, `QUEUE` (Kafka, RabbitMQ, AzureQueueStorage, AmazonSQS), `SNOWFLAKE`, `AI`.
  - All secrets parameters are treated as literal strings, If you need to load a secret from disk or the environment, use Ansible lookups.
  - Check mode support for connection strings.
### Changed
- Modularized the project internals for clearer responsibilities and easier maintenance.


## [1.1.0] - 2026-09-22

### Added
- RavenDB Cloud control-plane support via six new modules that talk to the RavenDB Cloud API (X-Api-Key auth).
- `ravendb.ravendb.cloud_account_info` - read account info.
- `ravendb.ravendb.cloud_metadata_info` - discover release channels, per-provider regions, and per-region instance types (aws, azure, gcp).
- `ravendb.ravendb.cloud_product_info` - list or filter cloud products by id or name, with optional detailed enrichment.
- `ravendb.ravendb.cloud_product` - create, terminate, and reconcile drift on a cloud product (storage size/type/iops/throughput and instance_type). Immutable fields (tier, cloud_provider, region, subdomain) and fields with no change endpoint (allowed_ips, release_channel) fail loud on drift. `state=absent` is gated behind `confirm_destroy=true`.
- `ravendb.ravendb.cloud_node` - add, remove, and restart individual nodes on multi-node cloud products (PB and P instance types).
- `ravendb.ravendb.cloud_certificate` - download the product client PKCS12 certificate. Idempotent by byte-equality; writes with 0o600 and refuses to follow symlinks.
- Documentation fragments `ravendb_cloud` (api_key/api_url/check_mode) and `ravendb_cloud_wait` (wait/wait_timeout).
- Live-test suite `tests/live/cloud_*.yml` (manual only, not in CI) and unit tests `tests/unit/test_cloud.py`.
