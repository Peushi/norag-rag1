"""Generate BakeFix's AI-BOM (CycloneDX 1.6 JSON) from the code and lock files.

    python scripts/generate_aibom.py            # write aibom/bakefix.cdx.json
    python scripts/generate_aibom.py --check    # exit 1 if the file is out of date
    python scripts/generate_aibom.py --validate # also validate against the CycloneDX schema

Sources of truth (nothing below is typed in twice):
- aibom/ai-components.json: descriptions, licences, model cards, datasets
- backend/vector_store.py: embedding model name, repository, and revision
- backend/llm_service.py: default Gemini model name
- requirements.lock.txt: exact Python packages, incl. the spaCy model wheel + hash
- frontend/package-lock.json: exact npm packages
- git-tracked dataset files: SHA-256 of each bundled dataset

The output is deterministic (no timestamp, serial number derived from the
content), so --check can compare it byte for byte. Standard library only, so
it runs without loading the models or the app.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTS_FILE = ROOT / "aibom" / "ai-components.json"
OUTPUT_FILE = ROOT / "aibom" / "bakefix.cdx.json"
HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"


def read_constant(path: Path, name: str) -> str:
    """Read `NAME = "value"` (or a getenv default) from a Python file without importing it."""
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(rf'^{name}\s*=\s*(?:os\.getenv\("[A-Z_]+",\s*)?"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit(f"Could not find {name} in {path.relative_to(ROOT)}")
    return match.group(1)


def git_tracked_files(path: str, include: list[str] | None) -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--", path], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout
    files = sorted(Path(item) for item in output.split("\0") if item)
    if include:
        # Only files directly in the folder, e.g. evaluation/*.jsonl, not results/.
        files = [
            f for f in files
            if f.parent == Path(path) and any(fnmatch.fnmatch(f.name, p) for p in include)
        ]
    return files


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_hash(files: list[Path]) -> str:
    """One SHA-256 for a set of files: changes if any file is added, removed, or edited."""
    digest = hashlib.sha256()
    for relative in files:
        digest.update(f"{relative.as_posix()}\0{sha256_file(ROOT / relative)}\n".encode())
    return digest.hexdigest()


def python_packages() -> tuple[list[dict], dict]:
    """Components from requirements.lock.txt, plus the spaCy model wheel's details."""
    components, spacy_model = [], {}
    for line in (ROOT / "requirements.lock.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if " @ " in line:
            name, url = line.split(" @ ", 1)
            if name.strip() == "en_core_web_sm":
                version = re.search(r"en_core_web_sm-([\d.]+)-", url).group(1)
                sha = url.split("#sha256=", 1)[1] if "#sha256=" in url else None
                spacy_model = {"version": version, "url": url.split("#", 1)[0], "sha256": sha}
            continue
        name, version = line.split("==", 1)
        normalised = re.sub(r"[-_.]+", "-", name).lower()
        components.append({
            "type": "library",
            "bom-ref": f"pkg:pypi/{normalised}@{version}",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{normalised}@{version}",
        })
    return components, spacy_model


def npm_packages() -> list[dict]:
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text())
    components = {}
    for path, info in lock["packages"].items():
        if not path or "version" not in info:
            continue
        name = info.get("name") or path.split("node_modules/")[-1]
        purl_name = name.replace("@", "%40", 1) if name.startswith("@") else name
        ref = f"pkg:npm/{purl_name}@{info['version']}"
        component = {
            "type": "library",
            "bom-ref": ref,
            "name": name,
            "version": info["version"],
            "purl": ref,
            # Build tools (Vite, TypeScript) are not shipped to the browser.
            "scope": "excluded" if info.get("dev") else "required",
        }
        if info.get("integrity", "").startswith("sha512-"):
            import base64
            component["hashes"] = [{
                "alg": "SHA-512",
                "content": base64.b64decode(info["integrity"][7:]).hex(),
            }]
        components[ref] = component
    return sorted(components.values(), key=lambda c: c["bom-ref"])


def properties(**values) -> list[dict]:
    return [{"name": f"bakefix:{k}", "value": str(v)} for k, v in values.items() if v is not None]


def build_bom() -> dict:
    facts = json.loads(FACTS_FILE.read_text())
    app = facts["application"]
    vector_store = ROOT / "backend" / "vector_store.py"
    embedding_name = read_constant(vector_store, "EMBEDDING_MODEL")
    embedding_repo = read_constant(vector_store, "EMBEDDING_MODEL_REPO")
    embedding_revision = read_constant(vector_store, "EMBEDDING_MODEL_REVISION")
    gemini_model = read_constant(ROOT / "backend" / "llm_service.py", "MODEL")
    libraries, spacy_model = python_packages()
    if not spacy_model:
        raise SystemExit("en_core_web_sm is missing from requirements.lock.txt")

    embed = facts["embedding_model"]
    embedding_component = {
        "type": "machine-learning-model",
        "bom-ref": embed["bom_ref"],
        "group": embedding_repo.split("/")[0],
        "name": embedding_name,
        "version": embedding_revision,
        "description": embed["description"],
        "licenses": [{"license": {"id": embed["license"]}}],
        "purl": f"pkg:huggingface/{embedding_repo}@{embedding_revision}",
        "hashes": [{"alg": "SHA-256", "content": embed["weights_sha256"]}],
        "externalReferences": [{
            "type": "distribution",
            "url": f"https://huggingface.co/{embedding_repo}/tree/{embedding_revision}",
        }],
        "properties": properties(weights_file=embed["weights_file"], runs="locally"),
        "modelCard": embed["model_card"],
    }

    pii = facts["pii_model"]
    pii_component = {
        "type": "machine-learning-model",
        "bom-ref": pii["bom_ref"],
        "group": "spacy",
        "name": pii["name"],
        "version": spacy_model["version"],
        "description": pii["description"],
        "licenses": [{"license": {"id": pii["license"]}}],
        "purl": f"pkg:pypi/en-core-web-sm@{spacy_model['version']}",
        "externalReferences": [{"type": "distribution", "url": spacy_model["url"]}],
        "properties": properties(runs="locally", used_by="presidio-analyzer"),
        "modelCard": pii["model_card"],
    }
    if spacy_model["sha256"]:
        pii_component["hashes"] = [{"alg": "SHA-256", "content": spacy_model["sha256"]}]

    datasets = []
    for data in facts["datasets"]:
        files = git_tracked_files(data["path"], data.get("include"))
        if not files:
            raise SystemExit(f"No git-tracked files for dataset {data['bom_ref']} ({data['path']})")
        datasets.append({
            "type": "data",
            "bom-ref": data["bom_ref"],
            "name": data["name"],
            "description": data["description"],
            "hashes": [{"alg": "SHA-256", "content": dataset_hash(files)}],
            "data": [{
                "type": "dataset",
                "name": data["name"],
                "contents": {"url": data["path"]},
                "classification": "contains personal data" if data["contains_personal_data"] else "no personal data",
                "description": data.get("note", data["description"]),
            }],
            "properties": properties(origin=data["origin"], path=data["path"], file_count=len(files)),
        })

    llm_card = facts["llm_model"]
    gemini_model_component = {
        "type": "machine-learning-model",
        "bom-ref": llm_card["bom_ref"],
        "group": "google",
        "name": gemini_model,
        "version": gemini_model,
        "description": llm_card["description"],
        "externalReferences": [{"type": "documentation", "url": "https://ai.google.dev/gemini-api/docs/models"}],
        "properties": properties(runs="hosted by Google (see service:gemini)", pinned="by name only"),
        "modelCard": llm_card["model_card"],
    }

    llm = facts["llm_service"]
    gemini_service = {
        "bom-ref": llm["bom_ref"],
        "provider": {"name": llm["provider"]},
        "name": llm["name"],
        "version": gemini_model,
        "description": llm["description"],
        "endpoints": [llm["endpoint"]],
        "authenticated": True,
        "x-trust-boundary": True,
        "trustZone": "external",
        "data": [{
            "flow": "outbound",
            "classification": "question and document passages (redacted)",
            "description": llm["data_sent"],
        }, {
            "flow": "inbound",
            "classification": "model output",
            "description": "Answer, cited chunk IDs, and glossary as JSON; validated before it is shown.",
        }],
        "externalReferences": [{"type": "license", "url": llm["terms_url"]}],
        "properties": properties(default_model=gemini_model, limits=llm["limits"], offline_use=llm["used_offline_for"]),
    }

    ai_refs = [embedding_component["bom-ref"], pii_component["bom-ref"]] + [d["bom-ref"] for d in datasets]
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": "app:bakefix",
                "name": app["name"],
                "version": app["version"],
                "description": app["description"],
            },
            "tools": {"components": [{"type": "application", "name": "scripts/generate_aibom.py"}]},
            "properties": properties(
                scope="Bundled models, datasets, services, and pinned packages. Documents uploaded at runtime are not included.",
            ),
        },
        "components": [
            embedding_component, pii_component, gemini_model_component,
            *datasets, *libraries, *npm_packages(),
        ],
        "services": [gemini_service],
        "dependencies": [
            {"ref": "app:bakefix", "dependsOn": [*ai_refs, gemini_service["bom-ref"]]},
            {"ref": gemini_service["bom-ref"], "dependsOn": [gemini_model_component["bom-ref"]]},
            {"ref": "data:kestrel-graph", "dependsOn": ["data:kestrel-kb", gemini_service["bom-ref"]]},
        ],
    }
    content = json.dumps(bom, sort_keys=True).encode()
    bom["serialNumber"] = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, hashlib.sha256(content).hexdigest())}"
    return bom


def check_cached_weights(bom: dict) -> str | None:
    """If the pinned model is in the local Hugging Face cache, its weights must match the BOM."""
    model = next(c for c in bom["components"] if c["bom-ref"] == "model:all-MiniLM-L6-v2")
    repo = f"models--{model['group']}--{model['name']}"
    weights = HF_CACHE / repo / "snapshots" / model["version"] / "model.safetensors"
    if not weights.exists():
        return None
    actual = sha256_file(weights.resolve())
    expected = model["hashes"][0]["content"]
    return None if actual == expected else f"Cached weights {actual} differ from the BOM's {expected}"


def render(bom: dict) -> str:
    return json.dumps(bom, indent=2, ensure_ascii=False) + "\n"


def validate(text: str) -> list[str]:
    try:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator
    except ImportError:
        return ["Install the dev tools first: pip install -r requirements-dev.txt"]
    error = JsonStrictValidator(SchemaVersion.V1_6).validate_str(text)
    return [str(error)] if error else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if the committed BOM is out of date")
    parser.add_argument("--validate", action="store_true", help="validate against the CycloneDX 1.6 schema")
    args = parser.parse_args()

    bom = build_bom()
    text = render(bom)
    problems = []
    if weights_problem := check_cached_weights(bom):
        problems.append(weights_problem)
    if args.validate:
        problems += validate(text)

    if args.check:
        current = OUTPUT_FILE.read_text() if OUTPUT_FILE.exists() else ""
        if current != text:
            problems.append("aibom/bakefix.cdx.json is out of date: run python scripts/generate_aibom.py")
    else:
        OUTPUT_FILE.write_text(text)
        counts = {}
        for component in bom["components"]:
            counts[component["type"]] = counts.get(component["type"], 0) + 1
        print(f"Wrote {OUTPUT_FILE.relative_to(ROOT)}: {counts}, services: {len(bom['services'])}")

    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
