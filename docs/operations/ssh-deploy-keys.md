---
title: SSH Deploy Key Setup for CI/CD
description: 'One-time setup for the SSH deploy key that lets CI/CD clone the private spec-kitty-events repository during builds: generating the keypair and registering the public key.'
doc_status: active
updated: '2026-01-29'
---
# SSH Deploy Key Setup for CI/CD

## Purpose

Spec-kitty depends on the private `spec-kitty-events` library. CI/CD (GitHub Actions) needs an SSH deploy key to clone this repository during builds.

## Setup Steps (One-Time)

### 1. Generate SSH Key Pair

```bash
ssh-keygen -t ed25519 -C "spec-kitty-ci-deploy-key" -f spec-kitty-events-deploy-key -N ""
```

This creates two files:
- `spec-kitty-events-deploy-key` (private key - for GitHub Actions secret)
- `spec-kitty-events-deploy-key.pub` (public key - for spec-kitty-events repo)

### 2. Add Public Key to spec-kitty-events Repository

1. Go to https://github.com/spec-kitty/spec-kitty-events/settings/keys
2. Click "Add deploy key"
3. Title: "spec-kitty CI/CD Read-Only"
4. Key: Paste contents of `spec-kitty-events-deploy-key.pub`
5. **Important**: Leave "Allow write access" UNCHECKED (read-only)
6. Click "Add key"

### 3. Add Private Key to spec-kitty Repository Secrets

1. Go to https://github.com/spec-kitty/spec-kitty/settings/secrets/actions
2. Click "New repository secret"
3. Name: `SPEC_KITTY_EVENTS_DEPLOY_KEY`
4. Value: Paste contents of `spec-kitty-events-deploy-key` (PRIVATE key, entire file)
5. Click "Add secret"

### 4. Delete Local Key Files (Security)

```bash
rm spec-kitty-events-deploy-key spec-kitty-events-deploy-key.pub
```

## Verification

After setup, GitHub Actions can access spec-kitty-events. Test by triggering a workflow run (see `.github/workflows/ci.yml`).

## Troubleshooting

**Error: "Permission denied (publickey)"**
- Check that public key was added to spec-kitty-events repo (Step 2)
- Check that private key secret name matches exactly: `SPEC_KITTY_EVENTS_DEPLOY_KEY`

**Error: "Could not read from remote repository"**
- Verify SSH URL in pyproject.toml uses `git+ssh://git@github.com/...` format
- Verify deploy key has read access to spec-kitty-events repository

## Key Rotation

**Rotate every 12 months or immediately if compromised.**

Follow the same steps above to generate new keys, then:
1. Add new public key to spec-kitty-events (don't remove old key yet)
2. Update secret in spec-kitty with new private key
3. Trigger a test build to verify new key works
4. Remove old public key from spec-kitty-events
