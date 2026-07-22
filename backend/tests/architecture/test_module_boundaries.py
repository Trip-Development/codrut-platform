import ast
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
MODULE_ROOT = BACKEND_ROOT / "src" / "codrut" / "modules"
BOUNDARY_DOCS = (
    MODULE_ROOT / "README.md",
    PROJECT_ROOT / "docs" / "contracts" / "module-boundaries.md",
)

DOCUMENTED_CROSS_MODULE_REPOSITORY_IMPORTS = {
    ("assignments", "companies", "service.py"),
    ("assignments", "forms", "service.py"),
    ("assignments", "scoring", "service.py"),
    ("companies", "communications", "service.py"),
    ("companies", "identity", "service.py"),
    ("scoring", "companies", "router.py"),
    ("scoring", "companies", "service.py"),
    ("scoring", "forms", "router.py"),
}

DOCUMENTED_ROUTER_REPOSITORY_IMPORTS = {
    ("scoring", "companies", "router.py"),
    ("scoring", "forms", "router.py"),
}

DOCUMENTED_ROUTER_SERVICE_IMPORTS = {
    ("assignments", "identity", "router.py"),
    ("assignments", "scoring", "router.py"),
}


@dataclass(frozen=True)
class ModuleImport:
    source_module: str
    source_file: Path
    imported_module: str
    imported_layer: str | None
    imported_name: str

    @property
    def source_layer(self) -> str:
        return self.source_file.name.removesuffix(".py")

    @property
    def source_file_name(self) -> str:
        return self.source_file.name


def iter_module_files() -> list[Path]:
    return sorted(path for path in MODULE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def source_module_for(path: Path) -> str:
    return path.relative_to(MODULE_ROOT).parts[0]


def module_import_from_name(source_file: Path, import_name: str) -> ModuleImport | None:
    prefix = "codrut.modules."
    if not import_name.startswith(prefix):
        return None

    relative_parts = import_name.removeprefix(prefix).split(".")
    imported_module = relative_parts[0]
    imported_layer = relative_parts[1] if len(relative_parts) > 1 else None

    return ModuleImport(
        source_module=source_module_for(source_file),
        source_file=source_file,
        imported_module=imported_module,
        imported_layer=imported_layer,
        imported_name=import_name,
    )


def iter_imports() -> list[ModuleImport]:
    imports: list[ModuleImport] = []
    for source_file in iter_module_files():
        tree = ast.parse(source_file.read_text(), filename=str(source_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(
                    import_record
                    for alias in node.names
                    if (import_record := module_import_from_name(source_file, alias.name))
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.extend(imports_from_node(source_file, node))
    return imports


def imports_from_node(source_file: Path, node: ast.ImportFrom) -> list[ModuleImport]:
    import_record = module_import_from_name(source_file, node.module)
    if import_record is None:
        return []

    if import_record.imported_layer is not None:
        return [import_record]

    return [
        ModuleImport(
            source_module=import_record.source_module,
            source_file=source_file,
            imported_module=import_record.imported_module,
            imported_layer=alias.name,
            imported_name=f"{node.module}.{alias.name}",
        )
        for alias in node.names
    ]


def format_imports(imports: list[ModuleImport]) -> list[str]:
    return [
        f"{item.source_file.relative_to(BACKEND_ROOT)} imports {item.imported_name}"
        for item in imports
    ]


def format_edge(source_module: str, imported_module: str, source_file: str, layer: str) -> str:
    source_layer = source_file.removesuffix(".py")
    return f"`{source_module}.{source_layer}` | `{imported_module}.{layer}`"


def missing_doc_entries(edges: set[tuple[str, str, str]], layer: str) -> list[str]:
    missing: list[str] = []
    for doc_path in BOUNDARY_DOCS:
        doc_text = doc_path.read_text()
        missing.extend(
            f"{doc_path.relative_to(PROJECT_ROOT)} missing {format_edge(*edge, layer)}"
            for edge in sorted(edges)
            if format_edge(*edge, layer) not in doc_text
        )
    return missing


def test_repository_modules_do_not_depend_on_services_or_routers() -> None:
    violations = [
        item
        for item in iter_imports()
        if item.source_layer == "repository" and item.imported_layer in {"router", "service"}
    ]

    assert format_imports(violations) == []


def test_policy_modules_do_not_depend_on_runtime_layers() -> None:
    violations = [
        item
        for item in iter_imports()
        if item.source_layer == "policies"
        and item.imported_layer in {"repository", "router", "service"}
    ]

    assert format_imports(violations) == []


def test_router_repository_imports_stay_documented() -> None:
    undocumented = [
        item
        for item in iter_imports()
        if item.source_layer == "router"
        and item.imported_layer == "repository"
        and (
            item.source_module,
            item.imported_module,
            item.source_file_name,
        )
        not in DOCUMENTED_ROUTER_REPOSITORY_IMPORTS
    ]

    assert format_imports(undocumented) == []


def test_router_service_imports_stay_local_or_documented() -> None:
    undocumented = [
        item
        for item in iter_imports()
        if item.source_layer == "router"
        and item.imported_layer == "service"
        and item.source_module != item.imported_module
        and (
            item.source_module,
            item.imported_module,
            item.source_file_name,
        )
        not in DOCUMENTED_ROUTER_SERVICE_IMPORTS
    ]

    assert format_imports(undocumented) == []


def test_service_modules_do_not_depend_on_routers() -> None:
    violations = [
        item
        for item in iter_imports()
        if item.source_layer == "service" and item.imported_layer == "router"
    ]

    assert format_imports(violations) == []


def test_cross_module_repository_imports_stay_documented() -> None:
    undocumented = [
        item
        for item in iter_imports()
        if item.source_module != item.imported_module
        and item.imported_layer == "repository"
        and (
            item.source_module,
            item.imported_module,
            item.source_file_name,
        )
        not in DOCUMENTED_CROSS_MODULE_REPOSITORY_IMPORTS
    ]

    assert format_imports(undocumented) == []


def test_documented_boundary_exceptions_are_reflected_in_docs() -> None:
    missing = [
        *missing_doc_entries(DOCUMENTED_CROSS_MODULE_REPOSITORY_IMPORTS, "repository"),
        *missing_doc_entries(DOCUMENTED_ROUTER_SERVICE_IMPORTS, "service"),
    ]

    assert missing == []
