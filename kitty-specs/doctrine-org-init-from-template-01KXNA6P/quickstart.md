# Quickstart: Doctrine Org Init From Template

For operators who create their own doctrine.

## Minimal scaffold (unchanged)

```bash
spec-kitty doctrine org init ./my-org-pack
spec-kitty doctrine org validate ./my-org-pack
```

## Render from a local template

```bash
spec-kitty doctrine org init ./acme-doctrine \
  --template ~/projects/doctrine-template \
  --org-name acme-corp \
  --local-path pack
```

Omitting `--local-path` defaults it to `pack`.

## Render from a git template

```bash
# Branch via flag
spec-kitty doctrine org init ./acme-doctrine \
  --template git@github.com:example/doctrine-template.git \
  --branch main \
  --org-name acme-corp

# Branch via URL fragment
spec-kitty doctrine org init ./acme-doctrine \
  --template https://github.com/example/doctrine-template.git#main \
  --org-name acme-corp
```

## Expected result

- Destination `./acme-doctrine` contains the **full** template tree except
  paths listed in the template’s `.templateignore` (and never `.git/`).
- `{{ORG_NAME}}` / `{{LOCAL_PATH}}` are replaced throughout text files.
- Invalid org names (e.g. `Acme`, `doctrine-org`, `{{ORG_NAME}}`) fail with a
  clear rule error and do not leave a successful render.

## Overwrite

```bash
spec-kitty doctrine org init ./acme-doctrine --force --template … --org-name …
```
