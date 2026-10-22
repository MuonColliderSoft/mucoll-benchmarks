#!/usr/bin/env python3
"""Aggregate object-study JSON fragments and run provenance into one report."""

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys


SCHEMA_VERSION = 1
FRAGMENT_SCHEMA_VERSION = 1


def sha256(path):
    path = pathlib.Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path, description="JSON file"):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except (OSError, ValueError) as error:
        raise RuntimeError("could not read {} {}: {}".format(description, path, error))


def production_metadata(input_path, metadata_path=None):
    """Load the chain submission record accompanying the RECO input, if any."""
    path = (
        pathlib.Path(metadata_path)
        if metadata_path
        else input_path.parent / "submission.json"
    )
    if not path.is_file():
        return None
    return {
        "name": path.name,
        "sha256": sha256(path),
        "metadata": load_json(path, "production metadata"),
    }


def repository_metadata(repository):
    """Return the benchmark source revision when running from a Git checkout."""
    repository = pathlib.Path(repository)
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            universal_newlines=True,
        ).strip()
        dirty = bool(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(repository),
                    "status",
                    "--porcelain",
                    "--untracked-files=normal",
                ],
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {"revision": revision, "dirty": dirty}


def github_metadata(environment=None):
    """Collect stable GitHub Actions identifiers without recording the host."""
    environment = os.environ if environment is None else environment
    mapping = {
        "repository": "GITHUB_REPOSITORY",
        "workflow": "GITHUB_WORKFLOW",
        "job": "GITHUB_JOB",
        "run_id": "GITHUB_RUN_ID",
        "run_attempt": "GITHUB_RUN_ATTEMPT",
        "sha": "GITHUB_SHA",
        "ref": "GITHUB_REF",
    }
    result = {
        key: environment[source]
        for key, source in mapping.items()
        if environment.get(source)
    }
    return result or None


def load_fragments(paths, input_path, expected_events=None):
    """Validate fragments for one input and return them keyed by study name."""
    studies = {}
    total_events = None
    input_path = input_path.resolve()
    input_bytes = input_path.stat().st_size
    for path in paths:
        path = pathlib.Path(path)
        fragment = load_json(path, "metrics fragment")
        if fragment.get("schema_version") != FRAGMENT_SCHEMA_VERSION:
            raise RuntimeError("{} has unsupported fragment schema version".format(path))
        study = fragment.get("study")
        if not study:
            raise RuntimeError("{} has no study name".format(path))
        if study in studies:
            raise RuntimeError("duplicate metrics fragment for study '{}'".format(study))
        fragment_input = fragment.get("input", {})
        if pathlib.Path(fragment_input.get("path", "")).resolve() != input_path:
            raise RuntimeError("{} was produced from a different input".format(path))
        if fragment_input.get("bytes") != input_bytes:
            raise RuntimeError("{} input size does not match {}".format(path, input_path))
        events = fragment.get("events", {})
        fragment_total = events.get("total")
        if not isinstance(fragment_total, int) or fragment_total < 0:
            raise RuntimeError("{} has an invalid total event count".format(path))
        selected = events.get("selected")
        if not isinstance(selected, int) or not 0 <= selected <= fragment_total:
            raise RuntimeError("{} has an invalid selected event count".format(path))
        if total_events is None:
            total_events = fragment_total
        elif fragment_total != total_events:
            raise RuntimeError("study fragments disagree on the total event count")
        studies[study] = {
            "fragment": {"name": path.name, "sha256": sha256(path)},
            "producer": fragment.get("producer"),
            "selected_event_count": selected,
            "configuration": fragment.get("configuration", {}),
            "metrics": fragment.get("metrics", {}),
        }
    if not studies:
        raise RuntimeError("at least one metrics fragment is required")
    if expected_events is not None and total_events != expected_events:
        raise RuntimeError(
            "expected {} events, found {}".format(expected_events, total_events)
        )
    return total_events, studies


def build_report(
    label,
    input_path,
    fragment_paths,
    expected_events=None,
    metadata_path=None,
    stack_version=None,
    environment=None,
):
    input_path = pathlib.Path(input_path).expanduser().resolve()
    if not input_path.is_file():
        raise RuntimeError("RECO input not found: {}".format(input_path))
    total_events, studies = load_fragments(fragment_paths, input_path, expected_events)
    script_path = pathlib.Path(__file__).resolve()
    repository = script_path.parents[2]
    environment = os.environ if environment is None else environment
    stack_version = stack_version or environment.get("MUCOLL_RELEASE_VERSION")
    if not stack_version:
        raise RuntimeError(
            "mucoll-stack version unavailable; source /opt/setup_mucoll.sh or "
            "pass --mucoll-stack-version"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "software": {"mucoll_stack_version": stack_version},
        "provenance": {
            "aggregator": {"name": script_path.name, "sha256": sha256(script_path)},
            "benchmark_repository": repository_metadata(repository),
            "production": production_metadata(input_path, metadata_path),
            "github_actions": github_metadata(environment),
        },
        "samples": {
            label: {
                "label": label,
                "event_count": total_events,
                "input": {
                    "name": input_path.name,
                    "bytes": input_path.stat().st_size,
                    "sha256": sha256(input_path),
                },
                "studies": studies,
            }
        },
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-label", required=True)
    parser.add_argument("--input", required=True, type=pathlib.Path)
    parser.add_argument(
        "--fragment",
        action="append",
        required=True,
        type=pathlib.Path,
        help="study JSON fragment; repeat for each available study",
    )
    parser.add_argument("--expected-events", type=int)
    parser.add_argument("--production-metadata", type=pathlib.Path)
    parser.add_argument("--mucoll-stack-version")
    parser.add_argument("--output", required=True, type=pathlib.Path)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        report = build_report(
            label=args.sample_label,
            input_path=args.input,
            fragment_paths=args.fragment,
            expected_events=args.expected_events,
            metadata_path=args.production_metadata,
            stack_version=args.mucoll_stack_version,
        )
    except RuntimeError as error:
        raise SystemExit(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, allow_nan=False, indent=2, sort_keys=True) + "\n"
    )
    print("Wrote {}".format(args.output), file=sys.stderr)


if __name__ == "__main__":
    main()
