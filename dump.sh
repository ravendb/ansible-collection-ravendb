#!/bin/bash

OUT="dump.txt"
> "$OUT"

paths=(
  "plugins/doc_fragments/ravendb.py"
  "plugins/module_utils/core/client.py"
  "plugins/module_utils/core/configuration.py"
  "plugins/module_utils/core/errors.py"
  "plugins/module_utils/core/messages.py"
  "plugins/module_utils/core/result.py"
  "plugins/module_utils/core/tls.py"
  "plugins/module_utils/core/validation.py"
  "plugins/module_utils/dto/database.py"
  "plugins/module_utils/dto/index.py"
  "plugins/module_utils/dto/node.py"
  "plugins/module_utils/reconcilers/base.py"
  "plugins/module_utils/reconcilers/database_reconciler.py"
  "plugins/module_utils/reconcilers/index_reconciler.py"
  "plugins/module_utils/reconcilers/node_reconciler.py"
  "plugins/module_utils/services/cluster_service.py"
  "plugins/module_utils/services/database_service.py"
  "plugins/module_utils/services/db_settings_service.py"
  "plugins/module_utils/services/encryption_service.py"
  "plugins/module_utils/services/index_config_service.py"
  "plugins/module_utils/services/index_service.py"
  "plugins/module_utils/services/node_service.py"
  "plugins/modules/database.py"
  "plugins/modules/index.py"
  "plugins/modules/node.py"
)

# paths=(
#   "tests/unit/test_cluster.py"
#   "tests/unit/test_database.py"
#   "tests/unit/test_index.py"
#   "tests/unit/test_index_modes.py"
# )


# paths=(
# "roles/ravendb_node/molecule/unsecured/converge.yml"
# "roles/ravendb_node/molecule/unsecured/molecule.yml"
# "roles/ravendb_node/molecule/unsecured/verify.yml"
# "playbooks/databases/ravendb_create_database_custom_settings.yml"
# "playbooks/databases/ravendb_create_database.yml"
# "playbooks/databases/ravendb_delete_database.yml"
# "playbooks/databases/ravendb_update_database.yml"
# "playbooks/indexes/ravendb_create_index.yml"
# "playbooks/indexes/ravendb_disable_index.yml"
# )

for file in "${paths[@]}"; do
  if [ -f "$file" ]; then
    echo "### $file" >> "$OUT"
    echo "" >> "$OUT"
    cat "$file" >> "$OUT"
    echo -e "\n\n--- END OF $file ---\n\n" >> "$OUT"
  else
    echo "### $file - NOT FOUND" >> "$OUT"
    echo "" >> "$OUT"
  fi
done

echo "Dump complete to $OUT"
