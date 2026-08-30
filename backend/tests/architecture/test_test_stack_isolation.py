from pathlib import Path
import pytest
import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
PROD_COMPOSE_PATH = PROJECT_ROOT / "compose.yaml"
TEST_COMPOSE_PATH = PROJECT_ROOT / "infra" / "test" / "compose.test.yaml"


def load_yaml(path: Path) -> dict:
    assert path.exists(), f"Compose file does not exist: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def test_test_stack_service_names_do_not_collide_with_production():
    prod_compose = load_yaml(PROD_COMPOSE_PATH)
    test_compose = load_yaml(TEST_COMPOSE_PATH)

    prod_services = set(prod_compose.get("services", {}).keys())
    test_services = set(test_compose.get("services", {}).keys())

    assert prod_services, "Production compose must define services"
    assert test_services, "Test compose must define services"

    colliding_services = prod_services.intersection(test_services)
    assert not colliding_services, (
        f"Test compose services collide with production services: {colliding_services}. "
        "Test services must use unique names (e.g. testbackend, testfrontend, testworker, testdb, testredis)."
    )
    # NOTA / EXCEPTIE EXPLICITA:
    # Serviciul `testbackend` defineste pe reteaua interna aliasul `backend` (aliases: [backend]).
    # Acest alias este STRICT INTERN retelei izolate a casei de proba si este necesar pentru ca
    # apelurile de proxy/SSR din testfrontend (Next.js server-side) sa rezolve `backend` fara EAI_AGAIN.
    # Numele serviciului ramane `testbackend` (fara coliziune de container/serviciu compose).


def test_test_stack_declares_no_external_networks():
    test_compose = load_yaml(TEST_COMPOSE_PATH)
    networks = test_compose.get("networks", {})

    for net_name, net_config in networks.items():
        if isinstance(net_config, dict):
            assert not net_config.get("external", False), (
                f"Test compose network '{net_name}' is declared as external. "
                "Test stack must be completely isolated on its own internal network."
            )


def test_test_stack_traefik_routers_prefixed_with_codytest():
    test_compose = load_yaml(TEST_COMPOSE_PATH)
    services = test_compose.get("services", {})

    for service_name, service_cfg in services.items():
        labels = service_cfg.get("labels", {})
        if isinstance(labels, dict):
            for label_key in labels.keys():
                if label_key.startswith("traefik.http.routers."):
                    # e.g. traefik.http.routers.codytest-api.rule
                    parts = label_key.split(".")
                    router_name = parts[3]
                    assert router_name.startswith("codytest-"), (
                        f"Traefik router '{router_name}' in service '{service_name}' does not start with 'codytest-'. "
                        "All test stack routers must start with 'codytest-' to avoid production route conflicts."
                    )
        elif isinstance(labels, list):
            for label in labels:
                if label.startswith("traefik.http.routers."):
                    parts = label.split("=")[0].split(".")
                    router_name = parts[3]
                    assert router_name.startswith("codytest-"), (
                        f"Traefik router '{router_name}' in service '{service_name}' does not start with 'codytest-'."
                    )


# Singurul serviciu din casa de probă care are voie să publice porturi pe gazdă
# este intrarea proprie de trafic. Orice altceva publicat pe gazdă e o scurgere.
ALLOWED_PUBLISHED_PORTS = {"testtraefik": {"80:80", "443:443"}}


def test_test_stack_declares_no_published_ports():
    test_compose = load_yaml(TEST_COMPOSE_PATH)
    services = test_compose.get("services", {})

    for service_name, service_cfg in services.items():
        ports = service_cfg.get("ports", [])
        if not ports:
            continue
        allowed = ALLOWED_PUBLISHED_PORTS.get(service_name)
        assert allowed is not None, (
            f"Service '{service_name}' in test compose defines published ports: {ports}. "
            "Only 'testtraefik' may publish host ports; everything else routes internally."
        )
        declared = {str(p) for p in ports}
        assert declared <= allowed, (
            f"Service '{service_name}' publishes {declared - allowed}, "
            f"outside the allowed set {allowed}."
        )


def test_test_stack_frontend_configures_internal_api_base_url():
    test_compose = load_yaml(TEST_COMPOSE_PATH)
    testfrontend_env = test_compose.get("services", {}).get("testfrontend", {}).get("environment", {})
    assert "INTERNAL_API_BASE_URL" in testfrontend_env, (
        "testfrontend must define INTERNAL_API_BASE_URL so server-side page rendering calls testbackend instead of backend"
    )
    val = testfrontend_env["INTERNAL_API_BASE_URL"]
    assert "testbackend" in str(val), (
        f"INTERNAL_API_BASE_URL must target testbackend, got: {val}"
    )

