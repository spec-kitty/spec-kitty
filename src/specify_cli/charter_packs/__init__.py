"""Charter pack fetch and scaffold adapters.

The ``specify_cli`` side of the charter pack tooling (mission
``charter-pack-cutover-01M491G6``, FR-010 / OD-9): the fetch sources
(``sources``: git, HTTPS/Artifactory bundle, API), snapshot management
(``snapshot``) and the org pack template renderer (``template_render``).

The pack model and validation/assembly tooling live in
:mod:`charter.offering.packs` and are reached only through the
:mod:`charter.packs` and :mod:`charter.drg` facades; org charter composition
lives in :mod:`charter.activation.org_charter`. Import from the submodules;
this package re-exports nothing.
"""
