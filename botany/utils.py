from pygbif import species


def unslugify(slug: str) -> str:
    return slug.replace("-", " ").title()


def resolve_gbif_id(identifier: str) -> int | None:
    """
    Accepts either a GBIF ID or a slug, and returns the resolved usageKey (GBIF ID).
    """
    if identifier is None:
        raise ValueError("No identifier provided")

    if identifier.isdigit():
        return int(identifier)

    name = unslugify(identifier)
    result = species.name_backbone(name)

    if result and result.get("usageKey"):
        return result["usageKey"]
    return None
