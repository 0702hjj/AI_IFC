from __future__ import annotations

import contextlib
import io
import importlib.util
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Sequence

from cadpy.catalog import (
    CAD_ROOT,
    REPO_ROOT,
    CadSource,
    StepImportOptions,
    iter_cad_sources,
    source_from_path,
)
from cadpy.cli_logging import CliLogger
from cadpy.file_metadata import text_to_cad_identity_metadata, write_dxf_text_to_cad_metadata
from cadpy.generation_status import GenerationOutput, track_generation_run
from cadpy.metadata import (
    DEFAULT_MESH_ANGULAR_TOLERANCE,
    DEFAULT_MESH_TOLERANCE,
    GeneratorMetadata,
    resolve_mesh_settings,
)
from cadpy.source_hash import python_source_hash


@dataclass(frozen=True)
class EntrySpec:
    source_ref: str
    cad_ref: str
    kind: str
    source_path: Path
    display_name: str
    source: str
    step_path: Path | None = None
    script_path: Path | None = None
    generator_metadata: GeneratorMetadata | None = None
    dxf_path: Path | None = None
    urdf_path: Path | None = None
    stl_path: Path | None = None
    three_mf_path: Path | None = None
    native_glb_path: Path | None = None
    sdf_path: Path | None = None
    mesh_tolerance: float = DEFAULT_MESH_TOLERANCE
    mesh_angular_tolerance: float = DEFAULT_MESH_ANGULAR_TOLERANCE
    mesh_tolerance_explicit: bool = False
    mesh_angular_tolerance_explicit: bool = False
    color: tuple[float, float, float, float] | None = None


@dataclass
class GeneratedStepResult:
    spec: EntrySpec
    scene: object | None
    selector_bundle: object | None = None


@dataclass(frozen=True)
class _CliTargetSpec:
    target: str
    output_path: Path | None = None


class InlineStatusBoard:
    def __init__(self, labels: Sequence[str], *, initial_status: str, stream: object | None = None) -> None:
        self._stream = stream or sys.stdout
        self._is_tty = getattr(self._stream, "isatty", lambda: False)()
        self._labels = list(labels)
        self._statuses = {label: initial_status for label in self._labels}
        self._rendered_rows = 0
        if self._labels and self._is_tty:
            self._render()
        else:
            for label in self._labels:
                print(self._row(label), file=self._stream)

    def set(self, label: str, status: str) -> None:
        previous = self._statuses.get(label)
        if previous == status:
            return
        if label not in self._statuses:
            self._labels.append(label)
        self._statuses[label] = status
        if self._is_tty:
            self._render()
        else:
            print(self._row(label), file=self._stream)

    def _row(self, label: str) -> str:
        width = max(len(item) for item in self._labels)
        return f"{label:<{width}} : {self._statuses.get(label, '')}"

    def _render(self) -> None:
        if not self._labels:
            return
        rows = [self._row(label) for label in self._labels]
        if self._rendered_rows:
            print(f"\x1b[{self._rendered_rows}F", end="", file=self._stream)
        for row in rows:
            print(f"\x1b[2K{row}", file=self._stream)
        if self._rendered_rows > len(rows):
            for _ in range(self._rendered_rows - len(rows)):
                print(f"\x1b[2K", file=self._stream)
            self._rendered_rows = len(rows)
        self._stream.flush()


def _display_name_for_path(path: Path) -> str:
    return path.stem


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def relative_to_directory(path: Path, base_dir: Path) -> str:
    return os.path.relpath(
        path.expanduser().resolve(),
        start=base_dir.expanduser().resolve(),
    ).replace(os.sep, "/")


def relative_to_file(path: Path, owner_path: Path) -> str:
    return relative_to_directory(path, owner_path.expanduser().resolve().parent)


def _resolve_cli_output_path(
    raw_output: str | Path | None,
    *,
    expected_suffixes: tuple[str, ...],
    tool_name: str,
    option_label: str = "--output",
) -> Path | None:
    if raw_output is None:
        return None
    value = str(raw_output).strip()
    if not value:
        raise ValueError(f"{tool_name} {option_label} must be a non-empty path")
    if "\\" in value:
        raise ValueError(f"{tool_name} {option_label} must use POSIX '/' separators")
    output_path = Path(value).expanduser()
    resolved = output_path.resolve() if output_path.is_absolute() else (Path.cwd() / output_path).resolve()
    if resolved.suffix.lower() not in expected_suffixes:
        joined = " or ".join(expected_suffixes)
        raise ValueError(f"{tool_name} {option_label} must end in {joined}")
    return resolved


def targets_include_output_pairs(targets: Sequence[str]) -> bool:
    return any("=" in str(target or "") for target in targets)


def _parse_cli_target_specs(
    targets: Sequence[str],
    *,
    expected_suffixes: tuple[str, ...],
    tool_name: str,
) -> list[_CliTargetSpec]:
    specs: list[_CliTargetSpec] = []
    for target in targets:
        target_text = str(target or "").strip()
        if "=" not in target_text:
            specs.append(_CliTargetSpec(target=target_text))
            continue
        raw_source, raw_output = target_text.split("=", 1)
        source = raw_source.strip()
        if not source:
            raise ValueError(f"{tool_name} output pair must use SOURCE=OUTPUT")
        output_path = _resolve_cli_output_path(
            raw_output,
            expected_suffixes=expected_suffixes,
            tool_name=tool_name,
            option_label="output pair",
        )
        if output_path is None:
            raise ValueError(f"{tool_name} output pair must use SOURCE=OUTPUT")
        specs.append(_CliTargetSpec(target=source, output_path=output_path))
    return specs


def _resolve_step_option_output_path(
    raw_output: str,
    *,
    base_step_path: Path,
    expected_suffixes: tuple[str, ...],
    field_name: str,
) -> Path:
    value = str(raw_output or "").strip()
    if not value:
        raise ValueError(f"{field_name} must be a non-empty path")
    if "\\" in value:
        raise ValueError(f"{field_name} must use POSIX '/' separators")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", "."} for part in pure.parts):
        raise ValueError(f"{field_name} must be relative")
    resolved = (base_step_path.resolve().parent / Path(*pure.parts)).resolve()
    if resolved.suffix.lower() not in expected_suffixes:
        joined = " or ".join(expected_suffixes)
        raise ValueError(f"{field_name} must end in {joined}")
    return resolved


def _apply_step_options_to_spec(spec: EntrySpec, step_options: StepImportOptions) -> EntrySpec:
    if not step_options.has_metadata or spec.step_path is None:
        return spec
    stl_path = spec.stl_path
    three_mf_path = spec.three_mf_path
    native_glb_path = spec.native_glb_path
    if step_options.stl is not None:
        stl_path = _resolve_step_option_output_path(
            step_options.stl,
            base_step_path=spec.step_path,
            expected_suffixes=(".stl",),
            field_name="stl",
        )
    if step_options.three_mf is not None:
        three_mf_path = _resolve_step_option_output_path(
            step_options.three_mf,
            base_step_path=spec.step_path,
            expected_suffixes=(".3mf",),
            field_name="3mf",
        )
    if step_options.glb is not None:
        native_glb_path = _resolve_step_option_output_path(
            step_options.glb,
            base_step_path=spec.step_path,
            expected_suffixes=(".glb",),
            field_name="glb",
        )
    return replace(
        spec,
        stl_path=stl_path,
        three_mf_path=three_mf_path,
        native_glb_path=native_glb_path,
        mesh_tolerance=step_options.mesh_tolerance if step_options.mesh_tolerance is not None else spec.mesh_tolerance,
        mesh_angular_tolerance=(
            step_options.mesh_angular_tolerance
            if step_options.mesh_angular_tolerance is not None
            else spec.mesh_angular_tolerance
        ),
        mesh_tolerance_explicit=spec.mesh_tolerance_explicit or step_options.mesh_tolerance is not None,
        mesh_angular_tolerance_explicit=(
            spec.mesh_angular_tolerance_explicit or step_options.mesh_angular_tolerance is not None
        ),
    )


def _spec_output_paths(spec: EntrySpec) -> tuple[Path, ...]:
    paths: list[Path] = []
    if spec.step_path is not None:
        paths.append(spec.step_path)
        from cadpy.render import part_glb_path

        paths.append(part_glb_path(spec.step_path))
    for path in (spec.dxf_path, spec.urdf_path, spec.sdf_path, spec.stl_path, spec.three_mf_path, spec.native_glb_path):
        if path is not None:
            paths.append(path)
    return tuple(path.resolve() for path in paths)


def _validate_cli_output_override(
    spec: EntrySpec,
    *,
    output_path: Path,
    all_specs: Sequence[EntrySpec],
    tool_name: str,
) -> None:
    resolved_output = output_path.resolve()
    for candidate in all_specs:
        if candidate.source_ref == spec.source_ref:
            continue
        if resolved_output in _spec_output_paths(candidate):
            raise ValueError(
                f"{tool_name} --output would overwrite another CAD output: "
                f"{_display_path(output_path)} belongs to {candidate.source_ref}"
            )


def _validate_duplicate_cli_output_overrides(
    output_paths: Sequence[Path | None],
    *,
    tool_name: str,
) -> None:
    seen: dict[Path, Path] = {}
    for output_path in output_paths:
        if output_path is None:
            continue
        resolved = output_path.resolve()
        previous = seen.get(resolved)
        if previous is not None:
            raise ValueError(f"{tool_name} output path is used more than once: {_display_path(output_path)}")
        seen[resolved] = output_path


def _apply_dxf_output_overrides(
    selected_specs: Sequence[EntrySpec],
    *,
    output_paths: Sequence[Path | None],
    all_specs: Sequence[EntrySpec],
    tool_name: str,
) -> list[EntrySpec]:
    if not any(output_path is not None for output_path in output_paths):
        return list(selected_specs)
    if len(output_paths) != len(selected_specs):
        raise ValueError(f"{tool_name} output override count must match target count")
    _validate_duplicate_cli_output_overrides(output_paths, tool_name=tool_name)
    updated_specs: list[EntrySpec] = []
    for spec, output_path in zip(selected_specs, output_paths, strict=True):
        if output_path is None:
            updated_specs.append(spec)
            continue
        if spec.source != "generated":
            raise ValueError(f"{tool_name} output pairs can only be used with generated Python targets")
        _validate_cli_output_override(spec, output_path=output_path, all_specs=all_specs, tool_name=tool_name)
        updated_specs.append(replace(spec, dxf_path=output_path))
    return updated_specs


def _apply_dxf_output_override(
    selected_specs: Sequence[EntrySpec],
    *,
    output_path: Path | None,
    all_specs: Sequence[EntrySpec],
    tool_name: str,
) -> list[EntrySpec]:
    if output_path is None:
        return list(selected_specs)
    if len(selected_specs) != 1:
        raise ValueError(f"{tool_name} --output can only be used with exactly one target")
    spec = selected_specs[0]
    if spec.source != "generated":
        raise ValueError(f"{tool_name} --output can only be used with generated Python targets")
    return _apply_dxf_output_overrides(
        selected_specs,
        output_paths=[output_path],
        all_specs=all_specs,
        tool_name=tool_name,
    )


def _entry_spec_from_source(source: CadSource) -> EntrySpec:
    generator_metadata = source.generator_metadata
    script_path = source.script_path
    kind = source.kind
    step_path = source.step_path
    mesh_settings = resolve_mesh_settings(
        cad_ref=source.cad_ref,
        generator_metadata=generator_metadata,
        mesh_tolerance=source.mesh_tolerance,
        mesh_angular_tolerance=source.mesh_angular_tolerance,
    )
    display_path = step_path if step_path is not None else source.source_path
    urdf_path = source.urdf_path

    return EntrySpec(
        source_ref=source.source_ref,
        cad_ref=source.cad_ref,
        kind=kind,
        source_path=source.source_path,
        display_name=(
            generator_metadata.display_name
            if generator_metadata is not None and generator_metadata.display_name
            else _display_name_for_path(display_path)
        ),
        source=source.source,
        step_path=step_path,
        script_path=script_path,
        generator_metadata=generator_metadata,
        dxf_path=source.dxf_path,
        urdf_path=urdf_path,
        sdf_path=source.sdf_path,
        stl_path=source.stl_path,
        three_mf_path=source.three_mf_path,
        native_glb_path=source.native_glb_path,
        mesh_tolerance=mesh_settings.tolerance,
        mesh_angular_tolerance=mesh_settings.angular_tolerance,
        mesh_tolerance_explicit=source.mesh_tolerance is not None,
        mesh_angular_tolerance_explicit=source.mesh_angular_tolerance is not None,
        color=source.color,
    )


def _load_generator_module(script_path: Path) -> object:
    resolved_script_path = script_path.resolve()
    module_name = (
        "_cad_tool_"
        + _display_path(resolved_script_path).replace("/", "_").replace("\\", "_").replace("-", "_").replace(".", "_")
    )
    module_spec = importlib.util.spec_from_file_location(module_name, resolved_script_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Failed to load generator module from {_display_path(resolved_script_path)}")

    module = importlib.util.module_from_spec(module_spec)
    original_sys_path = list(sys.path)
    search_paths = [
        str(REPO_ROOT),
        str(CAD_ROOT),
        str(resolved_script_path.parent),
    ]
    for parent in resolved_script_path.parents:
        if parent == REPO_ROOT.parent:
            break
    for candidate in reversed(search_paths):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    try:
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path

    return module


def _normalize_dxf_payload(result: object, *, script_path: Path) -> dict[str, object]:
    if isinstance(result, dict):
        allowed_fields = {"document"}
        extra_fields = sorted(str(key) for key in result if key not in allowed_fields)
        if extra_fields:
            joined = ", ".join(extra_fields)
            raise TypeError(f"{_display_path(script_path)} gen_dxf() envelope has unsupported field(s): {joined}")
        if "document" not in result:
            raise TypeError(f"{_display_path(script_path)} gen_dxf() envelope must define 'document'")
        return {"document": result["document"]}
    return {"document": result}


def _write_dxf_payload(
    envelope: dict[str, object],
    *,
    output_path: Path,
    script_path: Path,
    logger: CliLogger,
) -> None:
    document = envelope.get("document")
    saveas = getattr(document, "saveas", None)
    if not callable(saveas):
        raise TypeError(
            f"{_display_path(script_path)} gen_dxf() envelope field 'document' must be a DXF document, "
            f"got {type(document).__name__}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    saveas(str(output_path))
    source_identity = python_source_hash(script_path)
    write_dxf_text_to_cad_metadata(
        output_path,
        text_to_cad_identity_metadata(
            source_path=relative_to_file(script_path, output_path),
            source_hash=source_identity.source_hash,
        ),
    )
    logger.debug(f"wrote DXF: {_display_path(output_path)}")


def run_script_generator(
    spec: EntrySpec,
    generator_name: str,
    *,
    logger: CliLogger | None = None,
) -> object | None:
    logger = logger or CliLogger("dxf")
    if generator_name != "gen_dxf":
        raise RuntimeError(f"Unsupported generator in DXF-only runtime: {generator_name}")
    if spec.script_path is None or spec.generator_metadata is None:
        raise ValueError(f"{spec.source_ref} is not a generated Python CAD source")
    with _track_spec_generation(spec, generator_name):
        return _run_script_generator_inner(spec, generator_name, logger=logger)


def _run_script_generator_inner(
    spec: EntrySpec,
    generator_name: str,
    *,
    logger: CliLogger,
) -> object | None:
    with logger.timed(f"load generator {spec.source_ref}"):
        module = _load_generator_module(spec.script_path)
    generator = getattr(module, generator_name, None)
    if not callable(generator):
        raise RuntimeError(f"{_display_path(spec.script_path)} does not define callable {generator_name}()")
    with logger.timed(f"run {generator_name} {spec.source_ref}"):
        raw_payload = generator()

    envelope = _normalize_dxf_payload(raw_payload, script_path=spec.script_path)
    if spec.dxf_path is None:
        raise RuntimeError(f"{spec.source_ref} has no configured DXF output")
    _write_dxf_payload(envelope, output_path=spec.dxf_path, script_path=spec.script_path, logger=logger)
    if spec.dxf_path is not None and not spec.dxf_path.exists():
        raise RuntimeError(
            f"{_display_path(spec.script_path)} did not write {_display_path(spec.dxf_path)}"
        )
    return None


def _selected_specs_for_targets(
    targets: Sequence[str],
    *,
    direct_step_kind: str = "part",
    step_options: StepImportOptions | None = None,
    expected_output_suffixes: tuple[str, ...] | None = None,
    tool_name: str = "CAD",
    include_output_paths: bool = False,
) -> tuple[list[EntrySpec], list[EntrySpec]] | tuple[list[EntrySpec], list[EntrySpec], list[Path | None]]:
    step_options = step_options or StepImportOptions()
    target_specs = (
        _parse_cli_target_specs(
            targets,
            expected_suffixes=expected_output_suffixes,
            tool_name=tool_name,
        )
        if expected_output_suffixes is not None
        else [_CliTargetSpec(target=str(target or "").strip()) for target in targets]
    )
    explicit_specs: list[EntrySpec] = []
    output_paths: list[Path | None] = []
    unresolved_targets: list[str] = []
    for target_spec in target_specs:
        target_text = target_spec.target
        target_path = Path(target_text)
        resolved = target_path.resolve() if target_path.is_absolute() else (Path.cwd() / target_path).resolve()
        source = (
            source_from_path(
                resolved,
                step_kind=direct_step_kind,
                step_options=step_options,
            )
            if resolved.exists()
            else None
        )
        if source is None:
            unresolved_targets.append(target_text)
            continue
        explicit_specs.append(_apply_step_options_to_spec(_entry_spec_from_source(source), step_options))
        output_paths.append(target_spec.output_path)

    if not unresolved_targets:
        expanded_specs = _expand_specs_with_file_dependencies(explicit_specs)
        if include_output_paths:
            return expanded_specs, explicit_specs, output_paths
        return expanded_specs, explicit_specs

    unresolved = ", ".join(unresolved_targets)
    raise FileNotFoundError(
        "CAD target path not found or not a supported source file: "
        f"{unresolved}. Pass a Python generator or STEP/STP file path."
    )


def _expand_specs_with_file_dependencies(specs: Sequence[EntrySpec]) -> list[EntrySpec]:
    expanded: list[EntrySpec] = list(specs)
    seen_step_paths = {
        spec.step_path.resolve()
        for spec in expanded
        if spec.step_path is not None
    }
    seen_source_refs = {spec.source_ref for spec in expanded}
    queue = list(expanded)
    source_cache: dict[Path, CadSource | None] = {}
    discovered_sources_by_path: dict[Path, CadSource] | None = None

    def source_for_path(path: Path) -> CadSource | None:
        nonlocal discovered_sources_by_path
        resolved = path.resolve()
        if resolved in source_cache:
            return source_cache[resolved]
        if discovered_sources_by_path is None:
            discovered_sources_by_path = _source_lookup_by_path()
        source = discovered_sources_by_path.get(resolved)
        if source is None:
            source = source_from_path(resolved)
        source_cache[resolved] = source
        return source

    while queue:
        spec = queue.pop(0)
        if spec.kind != "assembly" or spec.source_path is None:
            continue
        try:
            from cadpy.assembly_spec import read_assembly_spec

            assembly_spec = read_assembly_spec(spec.source_path)
        except Exception:
            continue
        # Walk the flattened leaf view rather than top-level children. Compound
        # grouping nodes have no source_path, but every flattened instance does.
        for instance in assembly_spec.instances:
            if instance.source_path.resolve() in seen_step_paths:
                continue
            source = source_for_path(instance.source_path)
            if source is None:
                continue
            child_spec = _entry_spec_from_source(source)
            if child_spec.source_ref in seen_source_refs:
                continue
            expanded.append(child_spec)
            queue.append(child_spec)
            seen_source_refs.add(child_spec.source_ref)
            if child_spec.step_path is not None:
                seen_step_paths.add(child_spec.step_path.resolve())
    return expanded


def _source_lookup_by_path() -> dict[Path, CadSource]:
    sources_by_path: dict[Path, CadSource] = {}
    for source in iter_cad_sources():
        candidates = [
            source.source_path,
            source.origin_path,
            source.script_path,
            source.step_path,
            source.dxf_path,
            source.urdf_path,
            source.sdf_path,
            source.stl_path,
            source.three_mf_path,
            source.native_glb_path,
            *source.generated_paths,
        ]
        for candidate in candidates:
            if candidate is not None:
                sources_by_path.setdefault(candidate.resolve(), source)
    return sources_by_path


def _validate_dxf_target(spec: EntrySpec) -> None:
    metadata = spec.generator_metadata
    if spec.source != "generated" or spec.script_path is None or metadata is None:
        raise ValueError(f"dxf expected a generated Python source target: {spec.source_ref}")
    if not metadata.has_gen_dxf:
        raise ValueError(f"dxf target does not define gen_dxf(): {spec.source_ref}")
    if spec.dxf_path is None:
        raise ValueError(f"dxf target has no configured DXF output: {spec.source_ref}")


def _generated_output_summary(spec: EntrySpec) -> str:
    if spec.step_path is not None:
        return f"generated {spec.kind} STEP: {_display_path(spec.step_path)}"
    return f"processed: {spec.source_ref}"


def _generated_dxf_summary(spec: EntrySpec) -> str:
    if spec.dxf_path is not None:
        return f"generated DXF: {_display_path(spec.dxf_path)}"
    return f"processed: {spec.source_ref}"


def _generation_outputs_for_spec(spec: EntrySpec, generator_name: str) -> tuple[GenerationOutput, ...]:
    outputs: list[GenerationOutput] = []
    if generator_name == "gen_step" and spec.step_path is not None:
        outputs.append(GenerationOutput(spec.step_path, "step"))
        from cadpy.render import part_glb_path

        outputs.append(GenerationOutput(part_glb_path(spec.step_path), "glb"))
        if spec.stl_path is not None:
            outputs.append(GenerationOutput(spec.stl_path, "stl"))
        if spec.three_mf_path is not None:
            outputs.append(GenerationOutput(spec.three_mf_path, "3mf"))
        if spec.native_glb_path is not None:
            outputs.append(GenerationOutput(spec.native_glb_path, "glb"))
    elif generator_name == "gen_dxf" and spec.dxf_path is not None:
        outputs.append(GenerationOutput(spec.dxf_path, "dxf"))
    return tuple(outputs)


def _track_spec_generation(spec: EntrySpec, generator_name: str) -> contextlib.AbstractContextManager[None]:
    return track_generation_run(
        source_path=spec.script_path or spec.source_path,
        generator=generator_name,
        outputs=_generation_outputs_for_spec(spec, generator_name),
        repo_root=REPO_ROOT,
    )


def _run_with_spec_generation_status(
    spec: EntrySpec,
    generator_name: str,
    action: Callable[[EntrySpec], object],
) -> object:
    with _track_spec_generation(spec, generator_name):
        return action(spec)


def _run_selected_specs(
    selected_specs: Sequence[EntrySpec],
    *,
    initial_status: str = "Queued",
    action_status: str = "Generating...",
    done_status: str = "Generated",
    action: Callable[[EntrySpec], object],
    quiet: bool = False,
    status_stream: object | None = None,
    action_stdout: object | None = None,
    logger: CliLogger | None = None,
    success_message: Callable[[EntrySpec], str] | None = _generated_output_summary,
) -> list[object]:
    results: list[object] = []
    if quiet:
        for spec in selected_specs:
            with contextlib.redirect_stdout(io.StringIO()):
                results.append(action(spec))
        return results
    if logger is not None:
        for spec in selected_specs:
            logger.debug(f"{action_status} {spec.source_ref}")
            with logger.timed(f"{done_status.lower()} {spec.source_ref}"):
                if action_stdout is None:
                    result = action(spec)
                else:
                    with contextlib.redirect_stdout(action_stdout):
                        result = action(spec)
            results.append(result)
            if success_message is not None:
                message_spec = result.spec if isinstance(result, GeneratedStepResult) else spec
                logger.info(success_message(message_spec))
        return results
    status_board = InlineStatusBoard(
        [spec.source_ref for spec in selected_specs],
        initial_status=initial_status,
        stream=status_stream,
    )
    for spec in selected_specs:
        status_board.set(spec.source_ref, action_status)
        if action_stdout is None:
            result = action(spec)
        else:
            with contextlib.redirect_stdout(action_stdout):
                result = action(spec)
        results.append(result)
        status_board.set(spec.source_ref, done_status)
    return results


def generate_dxf_targets(
    targets: Sequence[str],
    *,
    output: str | Path | None = None,
    verbose: bool = False,
) -> int:
    tool_name = "dxf"
    logger = CliLogger("scripts/dxf", verbose=verbose)
    if output is not None and targets_include_output_pairs(targets):
        raise ValueError(f"{tool_name} --output cannot be combined with SOURCE=OUTPUT targets")
    output_path = _resolve_cli_output_path(output, expected_suffixes=(".dxf",), tool_name=tool_name)
    all_specs, selected_specs, target_output_paths = _selected_specs_for_targets(
        targets,
        expected_output_suffixes=(".dxf",),
        tool_name=tool_name,
        include_output_paths=True,
    )
    for spec in selected_specs:
        _validate_dxf_target(spec)
    selected_specs = _apply_dxf_output_override(
        selected_specs,
        output_path=output_path,
        all_specs=all_specs,
        tool_name=tool_name,
    )
    selected_specs = _apply_dxf_output_overrides(
        selected_specs,
        output_paths=target_output_paths,
        all_specs=all_specs,
        tool_name=tool_name,
    )
    _run_selected_specs(
        selected_specs,
        action=lambda spec: _run_with_spec_generation_status(
            spec,
            "gen_dxf",
            lambda tracked_spec: run_script_generator(tracked_spec, "gen_dxf", logger=logger),
        ),
        logger=logger,
        success_message=_generated_dxf_summary,
    )
    logger.total()
    return 0
