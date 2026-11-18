from __future__ import annotations

import getpass
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCENARIO_ROOT = ROOT / "tests" / "scenarios" / "scenario 3 r+d+io"
PROTEIN_EA_DIR = SCENARIO_ROOT / "protein_ea_inputs"
TIMEOUT_SECONDS = 120
API_BASE_URL = "http://localhost:8000"


def api_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
) -> dict | list:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw_response = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"La API respondió HTTP {exc.code} en {path}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar con la API ({path}): {exc.reason}") from exc

    if not raw_response:
        return {}
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"La API devolvió una respuesta no JSON en {path}.") from exc


def json_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict | None = None,
) -> dict | list:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    return api_request(
        base_url,
        path,
        method=method,
        token=token,
        body=body,
        content_type="application/json" if body is not None else None,
    )


def upload_file(
    base_url: str, project_id: int, pipeline_id: int, file_path: Path, token: str
) -> dict:
    boundary = f"----Scenario3{uuid.uuid4().hex}"
    file_content = file_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="upload"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            file_content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    query = urllib.parse.urlencode({"target_subdir": f"pipeline_{pipeline_id}"})
    result = api_request(
        base_url,
        f"/projects/{project_id}/files/upload?{query}",
        method="POST",
        token=token,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    if not isinstance(result, dict) or "absolute_path" not in result:
        raise RuntimeError(f"Respuesta inesperada al subir {file_path.name}: {result}")
    return result


def make_protein_ea_archive() -> bytes:
    """Zip the scenario auxiliaries at archive root (without including a PDB)."""
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PROTEIN_EA_DIR.iterdir()):
            if path.is_file():
                archive.write(path, arcname=path.name)
    return memory_file.getvalue()


def upload_bytes(
    base_url: str,
    project_id: int,
    pipeline_id: int,
    filename: str,
    content: bytes,
    token: str,
) -> dict:
    boundary = f"----Scenario3{uuid.uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="upload"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: application/zip\r\n\r\n",
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    query = urllib.parse.urlencode({"target_subdir": f"pipeline_{pipeline_id}"})
    result = api_request(
        base_url,
        f"/projects/{project_id}/files/upload?{query}",
        method="POST",
        token=token,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    if not isinstance(result, dict) or "absolute_path" not in result:
        raise RuntimeError(f"Respuesta inesperada al subir {filename}: {result}")
    return result


def validate_inputs() -> str:
    required = [
        SCENARIO_ROOT / "barnase_A.pdb",
        SCENARIO_ROOT / "barstar_A.pdb",
        PROTEIN_EA_DIR / "faceA.txt",
        PROTEIN_EA_DIR / "faceB.txt",
        PROTEIN_EA_DIR / "MSA_matrix.tsv",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Faltan archivos de entrada:\n- " + "\n- ".join(missing))
    if any(path.suffix.lower() == ".pdb" for path in PROTEIN_EA_DIR.iterdir() if path.is_file()):
        raise RuntimeError(
            "protein_ea_inputs no debe incluir PDB: ProteinEA debe usar el complejo generado por GRAMM."
        )
    return "faceB.txt"


def find_active_tool(tools: list[dict], name: str) -> dict:
    for tool in tools:
        if tool.get("name") == name and tool.get("active"):
            return tool
    raise RuntimeError(f"No se encontró la herramienta activa '{name}' en la plataforma.")


def main() -> int:
    face2_name = validate_inputs()
    email = input("Correo de la cuenta de la plataforma: ").strip()
    password = getpass.getpass("Contraseña: ")
    if not email or not password:
        raise RuntimeError("Se requieren correo y contraseña para iniciar sesión.")

    login_data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    login = api_request(
        API_BASE_URL,
        "/auth/login",
        method="POST",
        body=login_data,
        content_type="application/x-www-form-urlencoded",
    )
    token = login.get("access_token") if isinstance(login, dict) else None
    if not token:
        raise RuntimeError("La API no devolvió access_token al iniciar sesión.")

    tools = json_request(API_BASE_URL, "/tools/", token=token)
    if not isinstance(tools, list):
        raise RuntimeError("Respuesta inesperada al consultar las herramientas.")
    gnn = find_active_tool(tools, "gnn_refine")
    gramm = find_active_tool(tools, "gramm")
    protein_ea_tool = find_active_tool(tools, "protein_ea")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    project_name = f"scenario3-smoke-test-{timestamp}"
    project = json_request(
        API_BASE_URL,
        "/projects/",
        method="POST",
        token=token,
        payload={
            "name": project_name,
            "description": "Prueba de funcionamiento de una repetición del escenario 3 barnasa-barstar.",
        },
    )
    project_id = project["id"]
    print(f"Proyecto de prueba creado: {project_id} ({project_name})")

    pipeline = json_request(
        API_BASE_URL,
        f"/projects/{project_id}/pipelines/",
        method="POST",
        token=token,
        payload={
            "version": "scenario3-smoke-test",
            "parameters": {
                "benchmark_repetition": 1,
                "biological_model": "barnase-barstar",
                "receptor_source": "1A2P chain A",
                "ligand_source": "1A19 chain A",
                "reference_complex": "1BRS",
            },
        },
    )
    pipeline_id = pipeline["id"]

    barnase = upload_file(
        API_BASE_URL, project_id, pipeline_id, SCENARIO_ROOT / "barnase_A.pdb", token
    )
    barstar = upload_file(
        API_BASE_URL, project_id, pipeline_id, SCENARIO_ROOT / "barstar_A.pdb", token
    )
    protein_ea_archive = make_protein_ea_archive()
    protein_ea_upload = upload_bytes(
        API_BASE_URL,
        project_id,
        pipeline_id,
        "protein_ea_inputs.zip",
        protein_ea_archive,
        token,
    )

    def stage(stage_name: str, tool: dict, params: dict) -> dict:
        return {
            "stage_name": stage_name,
            "tool_id": tool["id"],
            "tool": tool["name"],
            "tool_version": tool.get("version"),
            "params": params,
        }

    refinement_params = {
        "n_decoy": 1,
        "n_proc": 1,
        "device_id": -1,
        "save_qa": False,
        "save_le_decoy": False,
        "save_all_decoy": False,
        "only_pred_dist": False,
    }
    stage_order = [
        stage(
            "refinement",
            gnn,
            {"input": barnase["absolute_path"], **refinement_params},
        ),
        stage(
            "refinement",
            gnn,
            {"input": barstar["absolute_path"], **refinement_params},
        ),
        stage(
            "docking",
            gramm,
            {
                "receptor_id": "barnase",
                "ligand_id": "barstar",
                "mmode": "docking",
                "eta": 3.5,
                "ro": 9,
                "fr": 0.0,
                "crang": "grid_step",
                "ccti": "gray",
                "crep": "all",
                "maxm": 30000,
                "ai": 10,
                "mtch_l": 20000,
                "scovdw": 0,
                "scosta": 0,
                "ctr": 0,
                "rclusl": 10,
                "mbak": 0,
                "maxmch": 100,
                "sejo": "joint",
            },
        ),
        stage(
            "interaction_optimization",
            protein_ea_tool,
            {
                "scenario_path": protein_ea_upload["absolute_path"],
                "algorithm": "sea",
                "partners": "A_B",
                "ligand_chain": "B",
                "gen": 1,
                "popsize": 1,
                "mutp": 1,
                "fitness_idxs": "2,3",
                "fitness_weights": "-1,1",
                "checkpoint": False,
                "checks": 2,
                "mobj": False,
                "randomseed": 15,
                "face1_file_name": "faceA.txt",
                "face2_file_name": face2_name,
                "msa_matrix": "MSA_matrix.tsv",
            },
        ),
    ]
    result = json_request(
        API_BASE_URL,
        f"/projects/{project_id}/pipelines/{pipeline_id}/run",
        method="POST",
        token=token,
        payload={"stage_order": stage_order, "pause_between_stages": False},
    )

    print("Repetición única del escenario 3 enviada a la plataforma.")
    print(f"Proyecto: {project_id} ({project_name})")
    print(f"Pipeline: {pipeline_id}")
    if isinstance(result, dict):
        print(f"Estado inicial: {result.get('status', 'no informado')}")
    print(f"Consulta el progreso desde la web o con la CLI: bio-cli pipelines status {pipeline_id} --watch")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, KeyError, OSError, urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc