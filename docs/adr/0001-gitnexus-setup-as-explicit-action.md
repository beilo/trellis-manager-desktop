# ADR 0001: Keep GitNexus setup as an explicit desktop action

## Status

Accepted

## Context

Trellis Manager Desktop has project actions for applying Trellis behavior to business projects. `Init` handles first-time Trellis onboarding, and `Update` manually synchronizes Trellis-managed files.

GitNexus setup is different: it invokes `npx --yes gitnexus setup`, belongs to an external integration, and can create files that are not Trellis-managed templates.

## Decision

Expose `GitNexus Setup` as a separate, explicit project action.

Manager will not fold GitNexus setup into `Init` or `Update`. It will not detect whether GitNexus has already been set up. It will ask for confirmation before running the command, warn when the project is dirty, run `npx --yes gitnexus setup`, and record the operation result in the normal log.

## Consequences

- Users can tell Trellis project lifecycle actions apart from external integration installation.
- `Init` and `Update` remain predictable Trellis actions.
- Dirty projects are allowed for GitNexus setup because the side effects belong to GitNexus and the user explicitly confirms the action.
- Manager only records this setup attempt. It does not become the source of truth for GitNexus installation state.
