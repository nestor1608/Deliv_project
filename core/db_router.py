class CatalogueRouter:
    """
    Database router for read replicas.
    Routes Vendor and Product reads to 'replica' database.
    All writes go to 'default'.
    """

    route_app_labels = {'vendors'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'replica'
        return None

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'replica':
            return False
        return None
