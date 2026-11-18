# Bioinformatics Pipelines Platform

A system for composing, running, and monitoring staged bioinformatics pipelines. The platform integrates a FastAPI API, a React/Vite web interface, a Typer CLI, PostgreSQL, RabbitMQ, Celery workers, and isolated scientific runtimes in Docker.

## Repository Modules

- [api](api/README.md): FastAPI backend, models, routers, authentication, and orchestration.
- [frontend](frontend/README.md): web console built with React + Vite.
- [CLI](CLI/README.md): command-line client.
- [workers](workers/README.md): Celery workers for each scientific stage.
- [docs/user_manual.md](docs/user_manual.md): platform user manual.
- [email-notifier](email-notifier/): internal service for email notifications.
- [observability](observability/): auxiliary observability components.
- Docker-managed `persistent_storage` volume: uploads, runs, outputs, reports, and generated scenarios.

## Architecture

Main services defined in [docker-compose.yml](docker-compose.yml):

| Service | Responsibility |
| --- | --- |
| `db` | PostgreSQL 15 for application data. |
| `broker` | RabbitMQ with management UI. |
| `api` | REST API, authentication, CRUD, orchestrator, and documentation. |
| `frontend` | React/Vite web interface. |
| `refinement-worker` | Runs `gnn_refine`. |
| `docking-worker` | Runs `gramm`. |
| `interaction-optimization-worker` | Runs `protein_ea`. |
| `gnnrefine-runtime` | Scientific image for refinement. |
| `gramm-runtime` | Scientific image for docking. |
| `protein-ea-runtime` | Scientific image for interaction optimization. |
| `email-notifier` | Internal delivery of notifications. |
| `pgadmin` | Visual administration of PostgreSQL. |

Workers do not query PostgreSQL directly. They receive a `tool_contract` from the API, prepare a workspace in `persistent_storage/runs`, execute the corresponding Docker runtime, publish outputs to `persistent_storage/outputs`, and report the result back to the API through internal callbacks.

## Execution Flow

1. The API starts, creates the current tables, and imports XML tools from [api/examples](api/examples/).
2. The user registers or logs in.
3. The user creates a project.
4. The user creates a pipeline and defines the `stage_order`.
5. The orchestrator creates `StageExecution` records and dispatches each stage to its Celery queue.
6. Each worker runs its scientific runtime and publishes artifacts.
7. If the pipeline uses `pause_between_stages`, it stays in `waiting_for_approval` before advancing.
8. When the pipeline completes, outputs and reports are available from the web interface and the CLI.

## Imported Tools

The resources for each tool can be configured in these documents.

- [gnnrefine.xml](api/examples/gnnrefine.xml): `gnn_refine`
- [gramm.xml](api/examples/gramm.xml): `gramm`
- [protein_ea.xml](api/examples/protein_ea.xml): `protein_ea`
- [atomrefine.xml](api/examples/atomrefine.xml): `atom_refine`

## Requirements

- Docker installed and Docker Compose v2 available as the `docker compose` command (included in Docker Desktop or installable as a plugin in Docker Engine).
- Free ports: `5432`, `5672`, `8000`, `5173`, `15672`, and `5050`.

## Getting Started

```bash
docker compose up --build
```

### Persistent Storage and Linux Permissions

The API and workers share the Docker-managed `persistent_storage` volume at `/persistent_storage`; Docker manages its ownership. On the first startup, `storage-init` imports existing files from the repository's `persistent_storage/` directory into the volume. Later runs use the Docker volume, so new files are no longer written into the repository directory. The volume survives `docker compose down`; `docker compose down -v` removes it and deletes stored data, so do not use `-v` unless you intend to erase the database, broker, and file storage volumes.

### Bootstrap Administrator

On startup, the API creates a superuser account if one does not already exist. The default credentials are:

- Username: `admin`
- Email: `admin@example.com`
- Password: `example1234`

These defaults are for local/example use only. Configure the account before starting the stack by setting `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` in the environment or in a root `.env` file. For example, use your own email and a strong password, and do not commit real credentials to version control. The administrator account and its values can be configured by the user.

### Guest Access and Data Retention

The login page offers `Continuar como invitado`. Guest sessions use one shared guest workspace: projects and pipelines created there, along with their files and results, are visible to every guest. Guest access cannot manage user accounts or groups. Guest projects and pipelines are automatically removed after the configured retention period; uploaded files and generated reports are also cleaned up when they expire. The default is 90 days. Set `GUEST_DATA_RETENTION_DAYS` in the environment or root `.env` to change it. The API checks for expired guest data hourly by default; configure `GUEST_CLEANUP_INTERVAL_SECONDS` to change the sweep interval. Active pipelines are left intact until they stop running.

### Email Notifications

The `email-notifier` container starts with example SMTP credentials, so email delivery will not work until you replace `SMTP_USER` and `SMTP_PASSWORD` in the `email-notifier` service in the root `docker-compose.yml` (or provide those variables in the root `.env`). For Gmail, use an app password rather than your regular account password. Set `SMTP_FROM` to an address permitted by your SMTP account, then recreate the service for the new settings to take effect.

Once the stack is up:

| Service | Access from the host |
| --- | --- |
| API | [http://localhost:8000](http://localhost:8000) |
| Frontend | [http://localhost:5173](http://localhost:5173) |
| PostgreSQL | `localhost:5432` |
| RabbitMQ (AMQP) | `localhost:5672` |
| RabbitMQ Management UI | [http://localhost:15672](http://localhost:15672) |
| pgAdmin | [http://localhost:5050](http://localhost:5050) |

Ports `5432` and `5672` are database and messaging connections, respectively; they are not opened in a browser. 

To rebuild a single service:

```bash
docker compose build api
docker compose up -d api
```

## Launching a Platform Test

With the platform running and the `gnn_refine`, `gramm`, and `protein_ea` tools active, run the following from the repository root:

```bash
python launch_scenario3_test.py
```

The script prompts for the email and password of an existing account, creates a test project, and launches a repetition of the full workflow: two refinements, docking, and interaction optimization.

## Using the Web Interface

1. Open [http://localhost:5173](http://localhost:5173).
2. Create an account or log in.
3. Create a project in `Projects`.
4. Upload inputs from `My Files / Outputs` or from the composer.
5. Create a pipeline, add stages, and click `Launch execution`.
6. Check progress in the pipeline detail view.
7. Download artifacts from `Execution detail` or `My Files / Outputs`.
8. Export reports from `Reports`.

The full manual is at [docs/user_manual.md](docs/user_manual.md) and is also served from the `Documentation` section of the frontend.

## Using the CLI

The CLI lives in [CLI](CLI/README.md). Main commands:

```bash
cli auth register
cli auth login
cli projects list
cli projects create
cli files upload 1 ./inputs/receptor.pdb
cli files outputs 1
cli pipelines create 1
cli pipelines run 1 2 --stage-order ./stage_order.json --watch
cli pipelines approve 2
cli pipelines retry 2 --stage-order-index 2 --new-params "{\"maxm\": 20000}"
cli results show 2
cli results download 2 --dest ./resultados
cli reports download-pipeline 1 2 --format json --dest ./reportes
```

The `cli_URL` variable lets you change the base URL of the API. By default it points to [http://localhost:8000](http://localhost:8000).

## Test Data

The [tests](tests/) folder contains input files and configurations for testing the platform's tools and workflows. It is not an automated `pytest` suite: the files serve as fixtures for loading or running stages from the platform.

| Folder | Contents |
| --- | --- |
| [tests/refinement](tests/refinement/) | Hemoglobin structure `2HHB.pdb` and example parameters for GNNRefine. |
| [tests/docking](tests/docking/) | Receptor and ligand structures, plus example parameters for GRAMM. |
| [tests/interaction_optimization](tests/interaction_optimization/) | ProteinEA parameters and input scenario, including the interaction faces and the MSA matrix. |
| [tests/scenarios](tests/scenarios/) | Full-workflow cases with their structures and auxiliary files: refinement, refinement + docking, and refinement + docking + interaction optimization. Each scenario includes a README with its inputs and configuration. |

The `params.json` files contain internal container paths, so they may need adjustments when used in a different setup. For execution examples, see the README of each scenario and the guide in [CLI/README.md](CLI/README.md).

## Persistent Storage

The Docker-managed `persistent_storage` volume is mounted inside the containers as `/persistent_storage`. The repository's `persistent_storage/` directory is imported once at first startup; application data created afterwards is stored in the Docker volume.

```text
persistent_storage/
|-- uploads/     # inputs uploaded per user/project
|-- runs/        # temporary per-stage workspaces
|-- outputs/     # artifacts published per stage
|-- reports/     # exported reports
`-- generated/   # generated scenarios or intermediate files
```

Outputs follow a path similar to:

```text
/persistent_storage/outputs/<user>/<stage>/pipeline_<id>/stage_<order>
```

## Relevant Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `GET /projects/`
- `POST /projects/{project_id}/pipelines/{pipeline_id}/run`
- `GET /executions/{pipeline_id}`
- `GET /executions/{pipeline_id}/stages`
- `POST /executions/{pipeline_id}/approve`
- `POST /executions/{pipeline_id}/retry-stage`
- `GET /projects/{project_id}/files`
- `POST /projects/{project_id}/files/upload`
- `GET /projects/{project_id}/outputs`
- `GET /projects/{project_id}/reports/overview`
- `GET /projects/{project_id}/pipelines/{pipeline_id}/reports/overview`
- `GET /monitoring/summary`
- `GET /documentation/entries`

## Project Structure Overview

```text
.
|-- api/
|-- CLI/
|-- docs/
|-- email-notifier/
|-- frontend/
|-- observability/
|-- persistent_storage/
|-- tests/
|-- workers/
|-- docker-compose.yml
`-- README.md
```