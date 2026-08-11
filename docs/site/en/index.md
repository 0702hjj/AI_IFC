---
layout: home

hero:
  name: AI_IFC
  text: Two peer logic legs + optional Agent workflow
  tagline: Self-hosted, open-source AI generation platform — AI-generated IFC and AI-generated CAD each form a closed loop (skill + diff + editing API); frontend and PostgreSQL optional. Reusability-first, interfaces callable or portable on their own.
  actions:
    - theme: brand
      text: Get Started
      link: /en/guide/quickstart
    - theme: alt
      text: GitHub
      link: https://github.com/0702hjj/AI_IFC

features:
  - icon: ✏️
    title: Script Editing
    details: Every web edit rewrites the build script — locate an element's callsite, change it via the PARAMS form or script editor, sandbox-validated and staged; each save is an immutable big version.
  - icon: 🔍
    title: Semantic Version Diff
    details: Attribute-level diffs keyed by GlobalId with added/removed/modified highlighting and old → new details, without geometric noise.
  - icon: 📜
    title: Script as Source of Truth
    details: Python build scripts are the single source of truth for IFC — sandboxed execution, paired major-version snapshots, and two-level script diffs.
  - icon: 🤖
    title: One API for Humans & AI
    details: Humans and AI share the same REST editing API, distinguished by provenance; the OpenAPI tool catalog can be fed directly to an LLM.
  - icon: 🔌
    title: MCP Integration
    details: An MCP server thinly wraps the editing API (stdio) and can parse user-modified IFC/DXF files, tagging them with USER provenance.
  - icon: 🏠
    title: Self-Hosted
    details: Four local processes run the whole platform; file storage works with zero dependencies, PostgreSQL optional. AGPL-3.0 open source.
---

## What is AI_IFC

AI_IFC is a self-hosted, open-source AI generation platform with two peer logic legs:

- **AI-generated IFC** (delivered): the `aiifc` skill lets AI write IfcOpenShell code to generate/modify models; `services/ifc` (edit-service) provides script sandbox execution, version snapshots, semantic diffs, and the script-as-source editing API — review models in 3D, file issues, edit the build script (PARAMS form / script editor), save big versions, and compare versions with diffs. Humans and AI agents edit through the same API.
- **AI-generated CAD** (skill domain delivered; diff/editing API to build): the `aidxfv` skill lets AI generate/validate DXF with ezdxf; `services/cad` will be the peer of `services/ifc`.
- **Agent workflow control** (recommended, optional): orchestrator + event bus (`aiifc://` event URIs), removable.

Reusability-first: two skills, two business-logic cores, optional frontend, optional PostgreSQL, interfaces callable or portable on their own. Framework spec: `docs/superpowers/specs/2026-08-11-platform-framework-design.md`.

Typical workflow: upload an IFC → review in 3D once conversion finishes → file issues on elements → select an element to locate its script callsite, edit PARAMS/script → sandbox-validated save as a big version → use Diff to compare versions. See the [project introduction](/en/guide/project-intro) for positioning and the four-component architecture.

## Screenshots

![3D viewer](/screenshots/viewer.png)

| Model library | Property editing | Version diff | AI chat |
|---|---|---|---|
| ![Model library](/screenshots/library.png) | ![Property editing](/screenshots/properties.png) | ![Version diff](/screenshots/diff.png) | ![AI chat](/screenshots/chat.png) |

## Getting started

1. [Environment & local deployment](/en/guide/quickstart) — install dependencies and start all components in four terminals.
2. [Upload your first IFC](/en/guide/first-ifc) — run through review → issues → editing → diff with the bundled sample.
3. [AI integration](/en/reference/ai) — expose the same editing API to AI agents.

## Links

- [GitHub repository](https://github.com/0702hjj/AI_IFC) — source code, issues and PRs
- [Changelog](/en/project/changelog) — version history (currently v0.1.0)
- [Roadmap](/project/roadmap) (Chinese) · [Contributing](/en/project/contributing)
