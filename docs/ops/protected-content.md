# Protected Content Operations

Official questionnaires, private scoring configuration, interpretations, and system email
templates must remain outside the implementation repository. The repository contains only the
package schema, import tooling, and synthetic fixtures.

Run package commands from the backend environment:

```bash
python -m codrut.tools.protected_content validate /secure/path/package.json
python -m codrut.tools.protected_content import /secure/path/package.json
python -m codrut.tools.protected_content activate /secure/path/package.json
```

Use `-` instead of a path to read from standard input. Import and activation are separate,
transactional operations. Import is duplicate-safe for an identical package ID and checksum.
Activation changes the active system version but never repoints existing assignments.

## Re-versioning

Older packages that contain private top-level `participant_schema.response` metadata can be
projected into a new immutable package:

```bash
python -m codrut.tools.protected_content reversion \
  /secure/path/source.json \
  /secure/path/destination.json \
  --package-id new-unique-package-id
```

Re-versioning increments questionnaire and template versions, removes `response` only from the
participant schema, retains private metadata in `private_config`, normalizes the public schema,
and calculates the checksum from the final serialized payload. The destination must not exist.

Always validate the destination before import. Do not activate a package in production until the
migration rehearsal, content-owner review, and release gate are approved.
