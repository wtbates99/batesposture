#!/usr/bin/env python

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import argparse
import re
import sys
from pathlib import Path

COMMIT_TYPES = {
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
}
COMMIT_PATTERN = re.compile(r"^([a-z]+)(?:\(([^\)]*)\))?!?: (.+)$")
COMPONENT_PATTERN = re.compile(r"^[a-zA-Z0-9_/\-\.]+$")


def _validate_components(root: Path, components: str | None) -> list[str]:
    if components is None:
        return []
    if not components.strip():
        return ["Invalid components: must not be empty"]

    reasons = []
    for component in components.split(","):
        if component != component.strip():
            reasons.append(
                f"Invalid component: must have no trailing space: {component}"
            )
        elif not COMPONENT_PATTERN.fullmatch(component):
            reasons.append(
                f"Invalid component: must be alphanumeric plus [.-/]: {component}"
            )
        elif component != "format" and not (root / component).exists():
            reasons.append(
                f"Invalid component: must reference a file or directory: {component}"
            )
    return reasons


def _validate_subject(subject: str) -> list[str]:
    reasons = []
    if subject.strip() != subject:
        reasons.append(f"Invalid subject: must have no trailing space: {subject}")
    if subject.strip().endswith("."):
        reasons.append(f"Invalid subject: must not end in a period: {subject}")
    return reasons


def matches_commit_format(root: Path, title: str) -> list[str]:
    """Check a title and return a list of reasons why it's invalid."""
    if not root.is_dir():
        return [f"Invalid root: must be a directory: {root}"]

    m = COMMIT_PATTERN.match(title)
    if m is None:
        return [
            "Format is incorrect, see https://www.conventionalcommits.org/en/v1.0.0/"
        ]

    reasons = []
    commit_type = m.group(1)
    if commit_type not in COMMIT_TYPES:
        reasons.append(f"Invalid commit type: {commit_type}")

    reasons.extend(_validate_components(root, m.group(2)))
    reasons.extend(_validate_subject(m.group(3)))
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="The root of the repository")
    parser.add_argument("title", help="The PR title to check")

    args = parser.parse_args()

    print(f'PR title: "{args.title}"')

    reasons = matches_commit_format(args.root, args.title)
    if not reasons:
        print("Title is valid")
        return 0

    print("Title is invalid:")
    for reason in reasons:
        print("-", reason)
    return 1


if __name__ == "__main__":
    sys.exit(main())
