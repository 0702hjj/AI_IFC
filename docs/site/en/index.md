---
layout: home

hero:
  name: AI_IFC
  text: IFC review and editing platform
  tagline: Self-hosted and open-source. Review IFC models in the browser, really edit attributes, compare versions with semantic diffs, and expose the same editing API to humans and AI.
  actions:
    - theme: brand
      text: Quick Start
      link: /en/guide/project-intro
    - theme: alt
      text: Upload your first IFC
      link: /en/guide/first-ifc

features:
  - title: 3D Review
    details: Upload an IFC and get fast XKT rendering; model tree, property inspection, section planes, measurements and 3D issue pins are built in.
  - title: Real Editing
    details: Property overrides and a two-phase pending → commit edit flow that really modifies IFC; every commit creates an immutable version snapshot.
  - title: Semantic Version Diff
    details: Attribute-level diffs keyed by GlobalId with added/removed/modified highlighting and old → new details, without geometric noise.
  - title: Human / AI Dual Role
    details: Humans and AI share the same REST editing API, distinguished by provenance; the OpenAPI tool catalog can be fed directly to an LLM.
---

## What it does

AI_IFC is an IFC (Industry Foundation Classes) review and editing platform made of four components:

- **web**: React + xeokit browser client for the model library, 3D review, property inspection, issues, property editing and version diffing.
- **server**: Go backend for uploads, the conversion queue, the REST API and edit orchestration, with file or PostgreSQL storage.
- **converter**: Node converter that turns IFC into XKT geometry and semantic metadata.
- **edit-service**: Python (FastAPI + IfcOpenShell) editing service for real IFC edits, version snapshots and semantic diffs.

Typical workflow: upload an IFC → review it in 3D once conversion finishes → file issues on elements → edit attributes (override or real edit) → commit to create a version → use Diff to compare versions.

## Getting started

1. [Project introduction](/en/guide/project-intro) — positioning, capability boundaries and the four-component architecture.
2. [Environment and local deployment](/en/guide/quickstart) — install dependencies and start all components in four terminals.
3. [Upload your first IFC](/en/guide/first-ifc) — run through review → issues → editing → diff with the bundled sample.
4. [Viewer REST API](/en/reference/rest-api) and [IFC editing API](/en/reference/edit-api) — API contracts; [AI integration](/en/reference/ai) for agents.

## Project status

The platform is functional end-to-end (upload → convert → review → edit → commit → diff). The active product is `viewer/`; SimpleCADAPI (SCAD) code from the repository history is kept as an archive, see [License & third-party components](/project/license) (Chinese) and [Roadmap](/project/roadmap) (Chinese).
