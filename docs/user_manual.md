# **User Manual - Bioinformatics Pipeline Platform**

## **Basic Workflow**

1. **Register and Log In**: Create an account and sign in.
2. **Create a Project**: Organize your work into projects.
3. **Upload Files**: Upload input files (PDB, MSA, etc.).
4. **Create a Pipeline**: Define the stages and parameters.
5. **Run the Pipeline**: Start the execution and monitor its progress.
6. **Download Results**: Obtain the generated files.
7. **Export Reports**: Download summaries in `md` or `json` format.

## **Using the GUI**

By default, the web graphical interface is available at `http://localhost:5173`.

From this interface, users can register, log in, create projects, configure stage-based executions, monitor statuses, download files, and view reports without using command-line instructions.

### **Access and Log In**

1. Open the frontend in your browser.
2. If you do not have an account yet, select `Create account`.
3. Fill in `Username`, `Email`, `Password`, and `Confirm password`.
4. Return to the login page and sign in with your email and password.

After successful authentication, the application loads the main console. The sidebar displays the available sections:

- `Dashboard`
- `Projects`
- `My Files / Outputs`
- `Reports`
- `Documentation`
- `Tools`
- `Monitoring` (administrators only)
- `About Us`

### **Dashboard**

The `Dashboard` summarizes system activity. On this screen, you can:

- View KPIs for active pipelines, ongoing executions, recent failures, and available tools.
- Review the `Pipeline executions` table, which lists recent pipelines.
- Open a pipeline using the `Open` button.
- Review recent failures and imported tools.

For non-administrator users, some detailed observability data is displayed in a limited form and can be viewed in full from the admin view.

### **Projects**

The `Projects` screen lets you manage projects and pipelines.

To create a project:

1. Go to `Projects`.
2. In the `Create project` panel, enter a `Name` and, optionally, a `Description`.
3. Click `Create project`.

To create a pipeline within a project:

1. Find the project in `Project inventory`.
2. Enter a version in `Pipeline version`, for example, `v1`.
3. Click `Add pipeline`.
4. Open the pipeline from the list to view its details.

You can also delete a pipeline from `Project inventory`. The first click enables the confirmation step; clicking `Confirm delete` a second time performs the deletion.

### **Pipeline Details and Execution Composer**

When you open a pipeline, the `Pipeline #<id>` view appears. It contains the execution status, the stage composer, and the details for each stage.

#### **Reviewing the Status**

The `Pipeline state` section displays:

- The pipeline version.
- The current status (`pending`, `running`, `waiting_for_approval`, `completed`, or `failed`).
- Whether the execution pauses between stages.
- The list of completed or currently running stages.

Select a stage to view its information under `Execution detail`.

#### **Composing and Launching an Execution**

To launch a pipeline from the GUI:

1. Open the pipeline details.
2. In `Execution composer`, click `Add stage`.
3. Select the `Phase`: `Refinement`, `Docking`, `Interaction Optimization`, or another phase available based on the imported tools.
4. Select the corresponding `Tool`.
5. Fill in the main parameters. Advanced parameters are available under `Advanced parameters`.
6. For file-type parameters, select a previously uploaded file or use `Upload file` within the field. Directories must be uploaded as `.zip` files.
7. Click `Add stage` again to add any other required stages.
8. If you want to review the workflow manually between stages, enable `Pause between stages`.
9. Click `Launch execution`.

The `output_dir` parameter and other parameters marked as outputs do not need to be entered manually. The platform assigns them automatically. Some docking and interaction-optimization parameters are also resolved from previous outputs, such as the receptor, ligand, or intermediate scenario.

#### **Approving a Paused Stage**

If `Pause between stages` is enabled, the pipeline may enter the `waiting_for_approval` state.

1. Select the paused stage under `Pipeline state`.
2. Under `Execution detail`, review the available data and artifacts.
3. Click `Approve next stage`.

After approval, the platform continues with the next stage defined in the composer.

#### **Retrying a Stage**

Under `Manual controls`, you can relaunch a stage with new parameters:

1. Select the stage under `Stage to retry`.
2. Enter new parameters if needed.

### **My Files / Outputs**

The `My Files / Outputs` screen centralizes uploaded inputs and generated outputs.

To upload input files:

1. Select the project under `Project scope`.
2. Click `Upload file`.
3. Select the local file.

Files uploaded from this screen are saved as shared project inputs (`shared_inputs`) and are made available in the composer's parameter forms.

To download input files:

1. Find the file under `Uploaded inputs`.
2. Click the item to download it.

To download outputs:

1. Under `Available outputs`, open the group for the desired pipeline and stage.
2. Click the artifact. The card displays the file type and size.

### **Reports**

The `Reports` screen lets you inspect and export reports.

1. Select the `Project`.
2. Select the `Pipeline`.
3. Review the project summary and pipeline summary.
4. Use `Download MD` or `Download JSON` under `Project report` or `Pipeline report`.

The view also includes:

- Comparisons between pipelines in the project.
- Key scientific indicators, such as the best docking energy or best TM-score, when available.
- Simple visualizations of duration, TM-score, output size, atom counts, and energy.
- A stage summary with status, tool, duration, artifacts, and extracted scientific metrics.

### **Documentation**

The `Documentation` screen lists documents served by the backend documentation module. From here, you can open or download the user manual and other references included in `docs`.

### **Tools**

The `Tools` screen displays tools imported from XML files:

- Tool name.
- Service type or phase.
- Version.
- Description.
- Runtime used.
- Available parameters and their data types.

Use this view to confirm that a tool has been loaded before using it in the execution composer.

### **Monitoring**

The `Monitoring` screen is available to administrator users. It displays available tools and active pipelines from a system-level perspective. Use it to review operational health and the overall status of executions.

### **Recommendations for Using the GUI**

- Upload input files first through `My Files / Outputs` or through the file field in the composer.
- Verify that the tools appear under `Tools` before creating an execution.
- Use `Pause between stages` when you need to inspect intermediate outputs before continuing.
- Download artifacts from `Execution detail` when reviewing a specific stage, or from `My Files / Outputs` to browse all project outputs.
- Review `Reports` when execution is complete to compare pipelines and export results.

## **Authentication**

### **Guest Access**

Select `Continue as guest` on the login page to use the shared guest workspace without registering. All guest sessions see the same guest-created projects, pipelines, uploads, and results. Guest accounts cannot manage groups or profile settings. Guest data is automatically removed after 90 days by default; the deployment operator can change this with `GUEST_DATA_RETENTION_DAYS`. Cleanup runs hourly by default and can be adjusted with `GUEST_CLEANUP_INTERVAL_SECONDS`. Active pipeline executions are retained until they finish.

### **Registration**

- Go to the web interface or use the CLI.
- Provide a username, email address, and password.

### **Log In**

- Use your email address and password.
- The JWT token is saved automatically for subsequent sessions.

### **CLI: Authentication**

```bash
bio-cli auth register
bio-cli auth login
bio-cli auth whoami
bio-cli auth logout
```

## **Project Management**

Projects organize your pipelines and files.

### **Create a Project**

- Web: Go to `Projects` > `Create`.
- CLI:

```bash
bio-cli projects create --name "My Project" --description "Optional description"
```

### **List Projects**

```bash
bio-cli projects list
```

### **View Project Details**

```bash
bio-cli projects show <project_id>
```

### **Delete a Project**

```bash
bio-cli projects delete <project_id> --yes
```

## **File Management**

### **Uploading Files**

- Web: In `My Files / Outputs`, use `Upload file`.
- CLI:

```bash
bio-cli files upload <project_id> ./inputs/receptor.pdb
bio-cli files upload <project_id> ./inputs/MSA.tsv --target-subdir shared_inputs
```

Files are stored by user and project. Common file types include:

- PDB files for molecular structures.
- MSA files for interaction optimization.
- Other tool-specific inputs.

### **View Uploaded Files**

```bash
bio-cli files list <project_id>
bio-cli files outputs <project_id>
```

### **Download a Project File**

```bash
bio-cli files download <project_id> shared_inputs/receptor.pdb --dest ./downloads
```

## **Creating and Running Pipelines**

### **Create a Pipeline**

```bash
bio-cli pipelines create <project_id> --version "v1.0" --parameters "{}"
```

### **Define Stages**

Stages run sequentially. Some parameters are resolved automatically from previous stages.

#### **Refinement**

- Input: PDB file uploaded to the project.
- Output: Refined PDB file.

#### **Docking**

- Input: Refined receptor and ligand.
- Note: `receptor_path` and `ligand_path` are resolved automatically if the preceding stage is refinement.

#### **Interaction Optimization**

- Input: Complex selected from docking, plus an MSA.
- Note: The intermediate scenario is generated automatically.

### **Run a Pipeline**

```bash
bio-cli pipelines run <project_id> <pipeline_id> --stage-order .\example_rde.json --watch
```

You can also provide the configuration inline:

```bash
bio-cli pipelines run <project_id> <pipeline_id> --stage-order "[{\"stage_name\":\"refinement\",\"tool_id\":1,\"tool\":\"gnn_refine\",
\"params\":{}}]"
```

### **Monitoring**

```bash
bio-cli pipelines status <pipeline_id> --watch
```

Common statuses:

- `pending`
- `running`
- `waiting_for_approval`
- `completed`
- `failed`

### **Approve the Next Stage**

If the pipeline was launched with pauses between stages:

```bash
bio-cli pipelines approve <pipeline_id>
```

### **Manually Retry a Stage**

```bash
bio-cli pipelines retry <pipeline_id> --stage-order-index 2 --new-params "{\"maxm\": 20000}"
```

## **Results and Downloads**

### **View Results**

```bash
bio-cli results show <pipeline_id>
bio-cli results stages <pipeline_id>
```

### **Download Outputs**

```bash
bio-cli results download <pipeline_id> --dest ./results
bio-cli results download <pipeline_id> --stage interaction_optimization --dest ./interaction_optimization
```

Outputs are generated in paths such as:

`/persistent_storage/outputs/<user>/<stage>/pipeline_<id>/stage_<order>`

## **Reports**

### **View the Project Summary**

```bash
bio-cli reports project <project_id>
```

### **View a Pipeline Summary**

```bash
bio-cli reports pipeline <project_id> <pipeline_id>
```

### **Download Reports**

```bash
bio-cli reports download-project <project_id> --format md --dest ./reports
bio-cli reports download-pipeline <project_id> <pipeline_id> --format json --dest ./reports
```

## **Advanced Usage**

### **Advanced Parameters**

- In the web interface, advanced parameters are grouped separately.
- In the CLI, they are included in the stage JSON or passed through `--new-params`.

### **Pauses Between Stages**

- Pauses allow for manual approval and intermediate review.

## **Test Data**

The repository includes sample input files and parameter fixtures for testing individual tools and end-to-end scenarios:

- [`tests/refinement`](../tests/refinement/): GNNRefine example inputs and parameters.
- [`tests/docking`](../tests/docking/): GRAMM example inputs and parameters.
- [`tests/interaction_optimization`](../tests/interaction_optimization/): ProteinEA scenario files and parameters.
- [`tests/scenarios`](../tests/scenarios/): documented workflows for refinement, refinement plus docking, and the complete refinement–docking–interaction optimization flow.


### **Logs and Debugging**

- The web interface displays a cleaner summary of the status.
- For deeper troubleshooting, check the API and worker logs.

## **Technical Notes**

- The platform uses Celery for asynchronous workers.
- Files are stored in `/persistent_storage`.
- The REST API is available by default at `http://localhost:8000`.
- The frontend is available by default at `http://localhost:5173`.
- The CLI requires Python 3.10+ and the dependencies to be installed.
