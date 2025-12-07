from __future__ import annotations

from django.conf import settings


class ReadReplicaRouter:
    """
    Directs read queries to a replica when DATABASE_REPLICA_URL is configured.
    Write operations always go to the primary.
    """

    replica_alias = "replica"

    def _has_replica(self) -> bool:
        return self.replica_alias in getattr(settings, "DATABASES", {})

    def db_for_read(self, model, **hints):
        if self._has_replica():
            return self.replica_alias
        return None

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == self.replica_alias:
            # Migrations must run only on primary.
            return False
        return True
