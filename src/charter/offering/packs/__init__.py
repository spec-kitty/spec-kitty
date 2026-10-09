"""Charter pack model and tooling (offering tier).

Holds the pack descriptor, lineage, manifest, built-in manifest, validator,
assembler and the ``extends`` resolver. Nothing here imports
``charter.activation`` or ``specify_cli``; ``specify_cli`` reaches these modules
only through the :mod:`charter.packs` facade.
"""
