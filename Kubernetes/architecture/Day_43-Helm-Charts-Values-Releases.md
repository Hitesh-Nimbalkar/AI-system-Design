# Helm — Charts, Values, Releases, Upgrades & Rollbacks (Day 43)

> Source: Day 43 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: **Helm** as a package manager for Kubernetes — charts, repositories, releases, Go templating, `values.yaml`, releases with revision history, one-command **upgrade and rollback**, and multi-environment deployments.
> Prerequisite: **Day 42** (Kustomize — same problem, different tool), Day 11 (three-tier apps), Day 10 (rolling updates/rollbacks — the concept Helm generalises).
> Next: **StatefulSets** (Day 44).

---

## 1) The Same Problem as Kustomize — but Helm's Answer Is Bigger

```
app-one
├── dev    ─┐
├── stage  ─┼──►  frontend, backend, database  (3 tiers each)
└── prod   ─┘
```

| Scope | Objects |
|---|---|
| Per environment | **12** |
| **Total** | **36** |

> And that's an **indicative** count — add NetworkPolicies, custom resources (Kyverno/OPA), `ClusterRole`/`ClusterRoleBinding`, `Role`/`RoleBinding`… **Applications are subjective.**

### The team structure matters too

The tiers are **decoupled for scaling** (scale backend without touching frontend) but **coupled for operation** — *"if my frontend is down, my backend is of no use."* And any tier may itself be **microservices**, multiplying manifests further.

### The manager's request (again)

> *"Add a label to all my Kubernetes resources."*

**"I already keep everything in one YAML file"** doesn't save you:

> *"How will you search that manifest? As your application grows… `Ctrl+F` will overwhelm you sooner or later."*

### The full list of challenges

| # | Challenge |
|---|---|
| 1 | **Add labels** for observability or compliance |
| 2 | **Inject annotations** |
| 3 | **Change image versions** — and remember *"dev = latest, stage/prod = stable"* |
| 4 | **Modify naming conventions** — *"if I see an object I should be able to identify the application, the environment, and the role"* |
| 5 | **Adjust replica counts or resource limits** |
| 6 | **Roll back** — *"if something goes wrong… with a single click"* |
| 7 | **A single source of truth** for details that change with release cycles |

### The rollback argument is the sharpest one

Day 10 taught you `kubectl rollout undo` for a **Deployment** — with a `change-cause` annotation, a single command back.

> **But that "single click" was limited to your Deployment.** *"It didn't understand your application as a whole"* — because your app is also a **Service**, a **ConfigMap**, a **ServiceAccount**…

> **What Kubernetes does natively for Deployments, Helm does for your entire application stack.**

---

## 2) Helm vs Kustomize

| | **Kustomize** | **Helm** |
|---|---|---|
| **Lifecycle tracking** | ❌ no releases | ✅ **applications tracked as releases**, with **versions** |
| **Rollback** | Manual (re-apply older overlays) | ✅ **one command, to a specific revision** |
| **Upgrade logic** | Re-apply updated overlays | ✅ proper upgrade with history |
| **Version history** | ❌ none | ✅ **complete revision timeline** |
| **Templating** | ❌ plain YAML overlays — no `if`/`range`/variables | ✅ **Go templates** — variables, conditionals, loops |
| **Packaging & distribution** | ❌ | ✅ **package as a chart and share it** |
| **Hooks & post-install guidance** | ❌ | ✅ **lifecycle hooks**, `NOTES.txt` |
| **Named templates** | ❌ | ✅ `_helpers.tpl` |

### How to choose

| Situation | Tool |
|---|---|
| **Simple** app — 20–30 resources, not YAML-heavy | **Kustomize** — *"customize is extremely simple"* |
| Need **hooks** (e.g. back up external RDS **before** upgrade) | **Helm** |
| Need **conditionals / named templates / distribution** | **Helm** |
| Stateful or stateless — doesn't matter; it's about **features needed** | — |

> *"Simple is subjective."* Learn both, then decide per application.

---

## 3) What Is Helm?

> **Helm is a package manager for Kubernetes applications.**

### The analogy that makes it click

| OS | Package manager | install | upgrade | remove |
|---|---|---|---|---|
| Ubuntu | **`apt`** | `apt install` | `apt upgrade` | `apt remove` |
| macOS | **Homebrew** | `brew install` | `brew upgrade` | `brew uninstall` |
| **Kubernetes** | **Helm** | **`helm install`** | **`helm upgrade`** | **`helm uninstall`** |

> `helm uninstall` removes **the whole application** — every object the chart created. That's the package-manager promise.

### What Helm is used for

| Use case | Examples |
|---|---|
| **Your own applications** | Three demos in this lecture build a chart **from scratch** |
| **Third-party tools** | **Prometheus**, **Grafana**, **cert-manager** — *"package your application because Helm is a package manager for applications deployed onto Kubernetes"* |
| **Operators** | Day 40 noted it: *"operators themselves are deployed as Helm charts"* |

> **Why third-party tools use Helm:** they need **many** resources, and hand-creating them is *"always a chance for errors."* A chart gives you `helm install` and the whole set appears correctly configured.

### The insight behind it

> **Kubernetes doesn't understand your application.** It's a container orchestrator — it doesn't know *"this Service belongs to app-one's dev environment"* or *"this ConfigMap is for prod."*

> **Helm considers your application as a single package** — so it can install, upgrade, and uninstall it **as a unit**.

---

## 4) The Three Core Components

| Component | Definition | Container-world analogue |
|---|---|---|
| **Chart** | The **blueprint** of your application | **Container image** |
| **Repository** | Where **charts are stored and shared** | **Image registry** |
| **Release** | A **running instance** of your chart | **Running container** |

> **Hierarchy: a repository contains charts; charts are installed as releases.**

### 4.1 Chart — the blueprint

> Contains **everything needed to deploy the application**: **templates**, **values**, and **metadata** — *"like a config bundle."*

- **Reusable and versioned** — the key property.
- **One chart, three environments:** *"you can use the same chart to create dev, stage and prod"* (Demo 3).

### 4.2 Repository — where charts live

- Stores and shares **versioned charts**.
- You can **add multiple repositories and search across them**.
- Popular ones: **Bitnami**, **TrueCharts**, **Grafana**.

> Searching every repository individually is painful — so **artifacthub.io** acts as *"a culmination of most of the popular repositories."*

**CLI verbs:** `helm repo add`, `list`, `remove`, `update`, `search`.

### 4.3 Release — a running instance

> Created by `helm install`. Each release has **its own configuration, history, and state**.

**Revisions** — the mechanism behind rollback:

```
Release "app-one"
├── Revision 1  ← app version 1.22   (install)
├── Revision 2  ← app version 1.23   (upgrade)
└── Revision 3  ← app version 1.22   (rollback to 1 — a NEW revision!)
```

> **Each revision is a snapshot of your application at a point in time.**

- **Upgrade, roll back, or uninstall** — all operate on the release.
- **The same chart can be installed multiple times** as different releases: `app-one-dev`, `app-one-prod`.
- **Rollback takes a revision number** — remember that, because it's the one thing you must specify.

---

## 5) CLI Walkthrough

```bash
helm version              # 3.18.3 in the lecture
helm -h                   # always start here — "you do not have to search the web"
helm repo -h              # add | index | list | remove | update
```

### Repositories

```bash
helm repo add my-bitnami https://charts.bitnami.com/bitnami
helm repo list
helm repo remove my-bitnami
```

> **Naming advice:** don't accept the default `bitnami` name — prefix it with something **project-specific** (`my-bitnami`). In a cluster hosting 20–30 apps, *"be extra careful with how you name things."*

> The provider tells you which repo to add — *"there is nothing written in stone."* Paid/enterprise tooling will give you their own repo URL.

### Search — and the subtlety about where it searches

```bash
helm search repo my-bitnami              # all charts in that repo
helm search repo my-bitnami/nginx        # filter
```

> ⚠️ **`helm search repo` is a LOCAL search.** It queries the **index** downloaded when you ran `helm repo add` (which is why that command took a moment). **No internet call at search time.**

```bash
helm search hub nginx                      # searches artifacthub.io (network)
helm search hub nginx --endpoint ...        # filter by repo
```

> **artifacthub.io** hosts ~**17,675 packages** with many releases. Open-source tooling: *"this is the place you'd visit to see whether there is a chart."* Paying customers get the repo from the vendor.

### Install / uninstall

```bash
helm install <release-name> <chart>          # chart = repo/chart or a local path
helm install my-nginx my-bitnami/nginx
helm uninstall my-nginx
```

> **What appeared:** a Deployment **and** a `LoadBalancer` Service. Why a load balancer? *"nginx typically fronts your application"* — the chart's author decided that. **Charts encode opinions**, which is the point.

---

## 6) Chart Directory Structure

```bash
helm create my-chart
```

> Generates **4 directories and 10 files** — a working skeleton.

| Path | Purpose | Required? |
|---|---|---|
| **`Chart.yaml`** | **Metadata**: name, version, description, **appVersion**, `apiVersion: v2` | ✅ **required** |
| **`values.yaml`** | **All your customizations** — the equivalent of `kustomization.yaml` | ✅ effectively |
| **`templates/`** | Your manifests, **with Go templating** | ✅ **required** |
| `charts/` | **Chart dependencies** (charts your chart depends on) | optional |
| `_helpers.tpl` | **Reusable named templates** (DRY) | optional |
| `NOTES.txt` | **Post-install message** — app URL, credentials, next steps | optional |
| `tests/` | `helm test` hooks | optional |

> **Note the capitalisation:** **`Chart.yaml`** has an uppercase **C**; **`values.yaml`** has a lowercase **v**. Both matter.

### The essential trio

> *"The major part is **`Chart.yaml`**, then **`templates/`** because that's where all your YAML lives, then **`values.yaml`**."*
>
> Once the chart works, *"you will predominantly only be playing with `values.yaml`."*

### The two versions in `Chart.yaml`

| Field | Tracks | Bump when |
|---|---|---|
| **`version`** | The **chart** version | You change **chart config** — labels, annotations, requests/limits, templates |
| **`appVersion`** | The **application** version | You upgrade the **application** (image) |

> **The distinction:** adding a label doesn't change what the end user experiences — that's a **chart** change. Upgrading nginx 1.22→1.23 is an **application** change.

### `apiVersion: v2` — Helm 3

> Helm 3 (released **2019**) uses **`apiVersion: v2`**. *"No one asks about Helm 2 vs Helm 3 anymore"* — every environment runs Helm 3.

---

## 7) Demo 1 — Building a Chart from Scratch

The lecture strips `helm create`'s output down to what an nginx Deployment + NodePort Service needs:

```
app-one-chart/
├── Chart.yaml
├── charts/
├── templates/
│   ├── deploy.yaml
│   └── service.yaml
└── values.yaml
```

> *"The concepts remain the same even if you have multiple YAMLs."*

### `Chart.yaml`

```yaml
apiVersion: v2
name: app-one-chart
description: A Helm chart for app-one
type: application
version: 0.1.0            # CHART version
appVersion: "1.22"        # APPLICATION version
```

### `templates/deploy.yaml` — the templating

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-nginx-deploy
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-nginx
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-nginx
    spec:
      containers:
        - name: nginx
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: 80
```

### The two kinds of variable

| Syntax | Source | Example |
|---|---|---|
| **`{{ .Release.Name }}`** | **Built-in** — supplied by Helm at install | the release you name on the CLI |
| **`{{ .Values.replicaCount }}`** | **User-defined** — from `values.yaml` | whatever you put there |

> **Note the case-sensitivity:**
> - **`.Release.Name`** — built-in, **capital R** (you don't control the name)
> - **`.Values.replicaCount`** — yours, **lowercase r** (you do)

**Built-in objects** you can reference: `.Release.Name`, `.Release.Namespace`, `.Release.Revision`, `.Chart.Name`, `.Chart.Version`, `.Chart.AppVersion`, `.Capabilities`…

> **Why templatize the name?** So every release is **identifiable**: install `app-one` → `app-one-nginx-deploy`. Install `app-one-test` → `app-one-test-nginx-deploy`. **No name collision, obvious ownership.**

### `values.yaml`

```yaml
replicaCount: 1

image:
  repository: nginx
  tag: "1.22"
```

> **There's no required format** — *"you can call this anything."* Use names that are **self-explanatory** so *"anyone who looks at your work can figure out what you were trying to do."*

> **Templatized three things:** the name, the replica count, and the image (`{{ .Values.image.repository }}:{{ .Values.image.tag }}`). *"That's the only concept here."*

### Verify before installing

```bash
helm lint app-one-chart
# 1 chart(s) linted, 0 chart(s) failed
```

> ⚠️ **`helm lint` validates YAML syntax — NOT Kubernetes schema.** The lecture proves it: add a stray space (breaking indentation) → *"unable to parse YAML: error converting YAML to JSON: line 11 has a problem."* Fix it and lint passes. It never checked whether `kind: Deployment` has valid fields.

```bash
helm template app-one ./app-one-chart
```

> **`template` = "render with this release name and show me the output."** Without a release name it would print the literal `{{ .Release.Name }}` — because **no release exists yet**.

Output confirms: `image: nginx:1.22`, `replicas: 1`, `name: app-one-nginx-deploy`.

### Deliberate breakage — for the error message

Remove a templating brace:

```bash
helm template app-one ./app-one-chart
# Error: parse error at (...): unexpected "-" in operand
# ... use --debug flag to render out invalid YAML
```

```bash
helm template app-one ./app-one-chart --debug    # shows exactly what broke, with line numbers
```

> **`--debug` is the templating debugger.** When a chart fails to render, this is the first flag to reach for.

### Install

```bash
helm install app-one ./app-one-chart --dry-run    # renders + simulates, NO cluster change
helm install app-one ./app-one-chart
```

```
NAME: app-one
LAST DEPLOYED: Thursday 10th 8:00
NAMESPACE: default
STATUS: deployed
REVISION: 1
TEST SUITE: None
```

| Command | Shows |
|---|---|
| **`helm list`** | All releases: name, namespace, revision, status, **chart version**, **app version** |
| **`helm status app-one`** | The same summary again |
| **`helm history app-one`** | **Every revision**, with time and description (`Install complete`) |

```bash
kubectl get pods,svc
# app-one-nginx-deploy-xxxxx   Running
# app-one-nginx-svc            NodePort   ← nodePort auto-assigned
```

### The parallel-environment trick

> *"A user says there's a problem with this version. I can't touch it — it's production. I want to **create a parallel infrastructure** and look at the problem from there."*

```bash
helm install app-one-test ./app-one-chart
```

**One command**, same chart, second release. `kubectl get pods` → `app-one-test-nginx-deploy`.

> **This only works because the names are templatized.** *"If you hadn't templatized this… the Helm command would have thrown an error: deployment already exists."*
>
> **That's why, in real production charts, the name is always templatized — no matter what.**

```bash
helm uninstall app-one-test
helm list                        # back to just app-one
```

---

## 8) Demo 2 — Upgrade and Rollback

**The scenario:** we're on nginx **1.22**, upgrading to **1.23**; then a bug is reported and we roll back.

> *"This is the exact workflow you'll deal with in production."*

### What changes (and what doesn't)

```yaml
# Chart.yaml
version: 0.1.0            # ← UNCHANGED: no chart change
appVersion: "1.23"        # ← CHANGED: application upgraded
```

```yaml
# values.yaml
image:
  tag: "1.23"             # ← CHANGED
```

> **This is the payoff of templating:** *"I do not have to go to my templates, I do not have to edit my YAML. I will just edit `values.yaml` and my application will be upgraded."*

```bash
helm template app-one ./app-one-chart        # verify: nginx:1.23
helm upgrade app-one ./app-one-chart
# REVISION: 2
```

```bash
helm list                 # REVISION 2, APP VERSION 1.23, CHART 0.1.0
helm history app-one
# REV 1   1.22   Install complete
# REV 2   1.23   Upgrade complete
kubectl get deploy -o wide        # image: nginx:1.23
```

### Roll back

```bash
helm rollback app-one 1
# Rollback was a success! Happy Helming!
```

```bash
helm history app-one
# REV 1   1.22   Install complete
# REV 2   1.23   Upgrade complete
# REV 3   1.22   Rollback to 1        ← a NEW revision!
```

> **The detail everyone gets wrong: a rollback is itself a new revision.** Helm records it as `Rollback to 1` — because *"Helm maintains a complete timeline of changes."* You never "delete" history by rolling back.

```bash
kubectl get deploy -o wide        # back to nginx:1.22
```

> *"With a single command we upgraded our application and with a single command we rolled it back."*
>
> **Kustomize couldn't do that** — you'd re-apply an older overlay. Simpler, but not the same as `helm rollback <release> <revision>`.

---

## 9) Demo 3 — Multi-Environment Deployments

**The requirement:** three production-like environments — `dev`, `stage`, `prod` — from **one chart**.

### Three values files

```
app-one-chart/
├── Chart.yaml
├── templates/{deploy.yaml,service.yaml}
├── values-dev.yaml
├── values-stage.yaml
└── values-prod.yaml
```

> **Helm looks for `values.yaml` by default.** With three environments you **must** have three files and pass them with `-f`. (Naming is free, but *"do sensible naming"* — `values-dev.yaml` etc.)

| | **dev** | **stage** | **prod** |
|---|---|---|---|
| `replicaCount` | **1** | **2** | **3** |
| `image.tag` | **1.23** (latest) | **1.22** | **1.22** |
| `namespace` | `dev` | `stage` | `prod` |

### `Chart.yaml` — which appVersion?

```yaml
version: 0.2.0            # bumped: the CHART changed (new namespace/container templating)
appVersion: "1.22"        # ← the PRODUCTION application version
```

> **The industry recommendation:** with multiple environments, **`appVersion` should always denote the production version.** Otherwise *"which version is production running?"* is unanswerable from the chart.
>
> That's why `helm list` will show **1.22** even for the dev release running 1.23 — **one chart, one `appVersion`**, and it means *production*.

### `templates/deploy.yaml` — two new templatizations

```yaml
metadata:
  name: {{ .Release.Name }}-nginx-deploy
  namespace: {{ .Values.namespace }}         # ← NEW: per-environment namespace
spec:
  replicas: {{ .Values.replicaCount }}
  template:
    spec:
      containers:
        - name: {{ .Release.Name }}-container   # ← NEW: environment-aware container name
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
```

> **Why templatize the container name?** *"When you're collecting logs and doing monitoring, you want not only your pod names consistent but your container names to represent the environment too."*

### Verify per environment

```bash
helm lint app-one-chart -f app-one-chart/values-dev.yaml
# Error: values.yaml does not exist      ← without -f!

helm lint app-one-chart -f app-one-chart/values-dev.yaml
# 1 chart(s) linted, 0 chart(s) failed   ← with -f
```

> **The default `values.yaml` is required unless you pass `-f`.** A real "gotcha" with multi-file setups.

```bash
helm template app-one-dev ./app-one-chart -f ./app-one-chart/values-dev.yaml
# name: app-one-dev-nginx-deploy
# namespace: dev
# replicas: 1
# image: nginx:1.23
```

### Install — **and the namespace trap**

```bash
kubectl create ns dev && kubectl create ns stage && kubectl create ns prod

helm install app-one-dev  ./app-one-chart -f ./app-one-chart/values-dev.yaml   -n dev
helm install app-one-stage ./app-one-chart -f .../values-stage.yaml            -n stage
helm install app-one-prod  ./app-one-chart -f .../values-prod.yaml             -n prod
```

**Everything looks right:**

```bash
kubectl get deploy -A
# dev    app-one-dev-nginx-deploy    1/1
# stage  app-one-stage-nginx-deploy  2/2
# prod   app-one-prod-nginx-deploy   3/3

kubectl get deploy -A -o wide
# dev   → nginx:1.23
# stage → nginx:1.22
# prod  → nginx:1.22
```

**But `helm list` shows `NAMESPACE: default`.**

### Why — the two-namespace rule

> **Templating `metadata.namespace` puts the *resources* in the right namespace. It does NOT tell Helm where to track the *release*.**

| Where | Controlled by |
|---|---|
| **Where the objects go** | `metadata.namespace` in the template **or** `-n` on install |
| **Where Helm stores the release record** | **Only `-n` on the install command** |

Omit `-n` and Helm records the release in **`default`** — so `helm list` (which defaults to the current namespace) shows nothing, and `helm uninstall app-one-dev` behaves confusingly.

**The fix — do both:**

```bash
helm install app-one-dev ./app-one-chart -f ./app-one-chart/values-dev.yaml -n dev
helm list -n dev        # now visible
helm list -A            # or ask for all namespaces
```

> **The instructor's rule:** *"specify the namespace in your manifest **and** specify the namespace when you run the command."* Helm then knows where to track; humans and tools know what belongs to what.

### Verify services too

```bash
kubectl get svc -A
# dev   app-one-dev-nginx-svc    NodePort   ...  <port>
# stage app-one-stage-nginx-svc  NodePort   ...  <port>
# prod  app-one-prod-nginx-svc   NodePort   ...  <port>
```

> Same chart, three environments, **different nodePorts auto-assigned** — no collisions.

### What `helm list -A` shows (and doesn't)

```
NAME            NAMESPACE   REVISION   CHART              APP VERSION
app-one-dev     dev         1          app-one-chart-0.2.0   1.22
app-one-stage   stage       1          app-one-chart-0.2.0   1.22
app-one-prod    prod        1          app-one-chart-0.2.0   1.22
```

> **`APP VERSION` reads 1.22 for all three — including dev, which is running 1.23.** That's by design: **`appVersion` means production**, as decided above.
>
> **Note the chart version `0.2.0`** — bumped from `0.1.0` because the **chart** changed (new namespace + container templating), even though the app didn't.

---

## 10) What This Lecture Did *Not* Cover

Helm has more: **functions, pipelines, conditionals, loops (`range`/`with`), `block`, named templates, chart hooks**.

> *"We have not discussed these because what we have discussed is sufficient for the CKA exam and to verify your production implementations. The concepts remain the same — with functions, named templates, chart hooks you get additional bells and whistles."*

**What you have is production-usable:** upgrades, rollbacks, and one chart with per-environment values files.

---

## 11) Key Takeaways

1. **Helm solves the same multi-environment problem as Kustomize, but with a package manager's lifecycle.**
2. **Helm tracks releases with versions and revision history** — Kustomize does not.
3. **One-command upgrade and rollback of the *entire application*** — not just a Deployment (Day 10's limitation).
4. **Helm adds Go templating** (variables, conditionals, loops), **packaging/distribution**, **hooks**, and **`NOTES.txt`** — none of which Kustomize has.
5. **Choose Kustomize for simple, not-YAML-heavy apps; Helm when you need hooks, conditionals, or distribution.**
6. **Helm = package manager for Kubernetes**, like `apt`/`brew`: install, upgrade, rollback, uninstall.
7. **Kubernetes doesn't understand your application; Helm treats it as one package.**
8. **Three components:** **chart** (blueprint ≈ image), **repository** (storage ≈ registry), **release** (running instance ≈ container).
9. **A chart is reusable and versioned** — one chart → dev, stage, prod.
10. **A release is a named instance** with its own config, history, and state; the **same chart can be installed many times** (`app-one-dev`, `app-one-prod`).
11. **Revisions are snapshots. Rollback targets a revision number — and creates a NEW revision.**
12. **`Chart.yaml` (capital C)** holds name, **`version`** (chart), **`appVersion`** (application), `apiVersion: v2` (Helm 3).
13. **`values.yaml` (lowercase v)** holds your customizations — *"the equivalent of `kustomization.yaml`"*.
14. **`templates/`** holds Go-templated YAML; **`charts/`** dependencies; **`_helpers.tpl`** reusable templates; **`NOTES.txt`** post-install message; **`tests/`** helm test hooks.
15. **Built-ins are capitalised (`.Release.Name`), your values are lowercase (`.Values.replicaCount`)`** — case-sensitivity bites.
16. **Templatize names** — otherwise a second release of the same chart fails with *"already exists."* *"In production the name is always templatized."*
17. **`helm lint` checks YAML syntax only** — not Kubernetes schema.
18. **`helm template <release> <chart>`** renders without a cluster; **`--debug`** shows exactly what broke.
19. **`helm install --dry-run`** renders and simulates without touching the cluster.
20. **`helm list` / `status` / `history`** — list releases, show one, show all revisions.
21. **`helm search repo` is local** (from the index downloaded by `repo add`); **`helm search hub`** queries **artifacthub.io**.
22. **Multi-environment = one chart + one values file per environment**, passed with **`-f`**.
23. **`helm lint`/`install` fail without `-f`** when the default `values.yaml` is absent.
24. **`appVersion` should mean the PRODUCTION version** when a chart serves multiple environments.
25. **Bump `version` when the chart changes, `appVersion` when the app changes.**
26. **Namespace appears in TWO places:** `metadata.namespace` drives the **objects**; the **`-n` flag** drives **release tracking**. Omit `-n` and `helm list` lies.
27. **`helm list -A`** to see releases across namespaces.

---

## 12) Essential Commands

```bash
# --- Version and help ---
helm version
helm -h
helm repo -h
helm install -h

# --- Repositories ---
helm repo add my-bitnami https://charts.bitnami.com/bitnami
helm repo list
helm repo remove my-bitnami
helm repo update

# --- Search ---
helm search repo my-bitnami              # LOCAL index
helm search repo my-bitnami/nginx
helm search hub nginx                    # artifacthub.io (network)

# --- Install / uninstall ---
helm install <release> <chart>                       # e.g. my-nginx my-bitnami/nginx
helm install app-one ./app-one-chart
helm install app-one ./app-one-chart --dry-run
helm install app-one-test ./app-one-chart            # second release from the same chart
helm uninstall app-one

# --- Inspect ---
helm list
helm list -A
helm status app-one
helm history app-one

# --- Upgrade / rollback ---
helm upgrade app-one ./app-one-chart
helm rollback app-one 1

# --- Build / validate ---
helm create my-chart
helm lint app-one-chart
helm lint app-one-chart -f app-one-chart/values-dev.yaml
helm template app-one ./app-one-chart
helm template app-one ./app-one-chart --debug
helm template app-one-dev ./app-one-chart -f ./app-one-chart/values-dev.yaml

# --- Multi-environment ---
kubectl create ns dev && kubectl create ns stage && kubectl create ns prod
helm install app-one-dev ./app-one-chart -f ./app-one-chart/values-dev.yaml -n dev
helm list -A
kubectl get deploy,svc -A
kubectl get deploy -A -o wide            # image versions per environment
```

### `Chart.yaml`

```yaml
apiVersion: v2
name: app-one-chart
description: A Helm chart for app-one
type: application
version: 0.2.0            # chart version
appVersion: "1.22"        # application version (production)
```

### `values-dev.yaml` / `values-stage.yaml` / `values-prod.yaml`

```yaml
# values-dev.yaml
replicaCount: 1
image:
  repository: nginx
  tag: "1.23"
namespace: dev
```
```yaml
# values-stage.yaml
replicaCount: 2
image:
  repository: nginx
  tag: "1.22"
namespace: stage
```
```yaml
# values-prod.yaml
replicaCount: 3
image:
  repository: nginx
  tag: "1.22"
namespace: prod
```

### `templates/deploy.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-nginx-deploy
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}-nginx
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-nginx
    spec:
      containers:
        - name: {{ .Release.Name }}-container
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          ports:
            - containerPort: 80
```

---

## 13) Quick Self-Check

1. Why doesn't "keep everything in one YAML file" solve the 36-manifest problem?
2. List five of the changes you're asked to make across environments.
3. What exactly does `kubectl rollout undo` *not* cover, and how does Helm fix it?
4. Give five capabilities Helm has that Kustomize doesn't.
5. When would you still choose Kustomize?
6. Define chart, repository, and release, and give the container-world analogue for each.
7. What makes a chart *reusable*? Give the concrete multi-environment example.
8. What is a **revision**, and what does rollback create?
9. What's the difference between `version` and `appVersion` in `Chart.yaml`? When do you bump each?
10. Which `Chart.yaml` field is `v2`, and why?
11. Name the three essential parts of a chart and what each holds.
12. What is `_helpers.tpl` for? `NOTES.txt`? `charts/`?
13. Distinguish `.Release.Name` from `.Values.replicaCount` — including case.
14. Why must names be templatized? What error appears if they aren't?
15. What does `helm lint` actually validate — and what does it *not*?
16. What's the difference between `helm template`, `--dry-run`, and a real `install`?
17. What does `--debug` give you when a template fails?
18. Why is `helm search repo` fast, and what is it searching?
19. How do you install one chart into three environments? What carries the differences?
20. What happens if you omit `-f` when `values.yaml` doesn't exist?
21. Which value should `appVersion` hold in a multi-environment chart, and why?
22. `helm list` shows `NAMESPACE: default` but your pods are in `dev`. Explain and fix.
23. Why does `helm list -A` show `1.22` for a dev release running `1.23`?
24. How do you see a release's whole timeline?
25. What Helm features were deliberately left out of this lecture, and why is that acceptable for the CKA?

---

## What's Next (Day 44)

- **StatefulSets** — the workload type for stateful applications: stable identity, ordered startup, and per-pod storage (the Day 40 problem, finally solved properly).

---

*End of Day 43 notes.*
