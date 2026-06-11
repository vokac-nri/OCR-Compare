from app.engines.catalog import ENGINE_CATALOG


def get_spec(engine_id: str):
    return ENGINE_CATALOG[engine_id]


def all_specs():
    return list(ENGINE_CATALOG.values())
