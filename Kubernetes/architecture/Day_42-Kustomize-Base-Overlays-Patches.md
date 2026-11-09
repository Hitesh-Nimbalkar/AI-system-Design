# Kustomize — Base, Overlays, Transformers & Patches (Day 42)

> Source: Day 42 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: **Kustomize** — managing one application across many environments with a shared **base**, per-environment **overlays**, **transformers**, and the three **patch** styles.
> Prerequisite: Day 11 (three-tier / microservices — where the object count comes from), Day 14 (namespaces), Day 27 (`imagePullPolicy`/tags), Day 36 (RBAC objects you might also template).
> Next: **Helm** (Day 43) — the templating approach.

---

## 1) The Problem: 36 Manifests, Three Environments

An ordinary application, drawn honestly:

```
app-one
├── dev    ─┐
├── stage  ─┼──►  three tiers each (frontend, backend, database)
└── prod   ─┘
```

| Scope | Objects |
|---|---|
| **Per environment** | **12** Kubernetes resources |
| **Total (3 environments)** | **36** objects |

> **The list is indicative, not exhaustive.** A real app adds `Role`, `RoleBinding`, `ClusterRole`, `ClusterRoleBinding`, **custom resources**, `NetworkPolicy`, `ServiceAccount`, `ConfigMap`, `Secret`, `PVC`, HPA… **and microservices multiply it further** (frontend split by platform, backend split into 5–10 services).

### Now the manager's request

> *"Add this label to **all** my Kubernetes manifests."*

You **can** edit 36 files by hand. But:

| Problem | Why it matters |
|---|---|
| **Humans make mistakes** | Miss one manifest → inconsistent cluster |
| **Humans forget** | *"Update the image version, and remember prod uses n-1"* — recall is not a control |
| **It doesn't scale** | Microservices turn 36 into 200 |
| **DevOps maturity** | Manual bulk editing is the opposite of automation |

### The other changes you'll be asked for

- Inject an **annotation** (cost tracking, security posture, **branch name**)
- **Change an image version** (patch release, rollback)
- Keep environment **version rules**: **dev = latest (n)**, **stage/prod = n-1 or n-2 stable**

> *"We humans are fantastic at automating tasks"* — so **automate this**.

### What's actually needed

> **A mechanism that makes multi-file, multi-resource updates structured, automated, and safe** — and avoids **environment-specific copies of the same YAML with minor differences**.

**The shape of the answer:**

```
        base           ← everything common
          │
   ┌──────┼──────┐
   ▼      ▼      ▼
 dev    stage   prod      ← overlays: only what differs
```

> **Base + overlay = final configuration.** Those are Kustomize's own terms.

---

## 2) What Is Kustomize?

> **A Kubernetes-native tool for customizing YAML manifests *without* using templates.**

| | |
|---|---|
| **Install** | **Built into `kubectl`** — *"you already have it"* |
| **Check** | `kubectl kustomize -h` |
| **Input** | **Plain YAML** — the syntax you already know |
| **Core components** | **Base** (shared) + **overlays** (environment-specific patches) |
| **Final config** | **base + overlay** |

### The required file

> **`kustomization.yaml`** — that exact lowercase name, in **both** the base and each overlay.

> If Kustomize doesn't find it, **the command errors out**. Nothing is "auto-detected."

---

## 3) Kustomize vs Helm

| | **Kustomize** | **Helm** |
|---|---|---|
| **Approach** | **Plain YAML overlays** | **Templating** — functions, variables, **Go** |
| **Abstraction** | *"Just deals with plain YAML"* | Programmable templates |
| **Role** | **Overlay tool** | **Package manager** (versioned charts) |
| **Release tracking** | ❌ none | ✅ **tracks releases** |
| **Hooks / rollbacks / dependencies** | ❌ | ✅ **feature-rich** |
| **Native to kubectl** | ✅ | ❌ third-party |
| **Complexity** | **Simple** | **Complex** — *"and because it is complex, it can achieve more"* |
| **Best for** | **Environment-specific configuration**, simple-to-moderate apps | **Complex, highly parameterised apps**; shipping software to others |

> **Versioning:** Kustomize has no releases, *"but you can always version control your Kustomize YAML"* — which you're already doing for manifests.

**The instructor's lived comparison:** *"I have used both. Kustomize is extremely simple. If your application is not complex, not truly wired here and there, Kustomize will do the job."*

> The honest conclusion: **learn both, then judge for your app** — that's what Day 43 is for.

### One caution the lecture stresses

> **You do not need a three-tier design, or environments at all, to use Kustomize.** *"You can use it as long as your Kubernetes manifests use YAML — which they do."* The base/overlay split works for microservices, single apps, or anything else.

---

## 4) The Directory Structure

```
demo1/
├── base/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── kustomization.yaml      ← required
└── overlays/
    ├── dev/
    │   └── kustomization.yaml
    ├── stage/
    │   └── kustomization.yaml
    └── prod/
        └── kustomization.yaml
```

> **Is `base`/`overlays` mandatory? No. Should you use it? Yes.**
>
> *"This nomenclature is industry accepted… when a junior or senior admin refers to your work, they say: this person has structured it so anyone can understand what's happening."*

**Flexibility exists** (names per microservice, dev/prod nested inside), but **start with `base` + `overlays`**.

---

## 5) Demo 1 — The Base and a Name Suffix

### `base/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deploy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx
          ports:
            - containerPort: 80
```

### `base/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
spec:
  type: NodePort          # nodePort left unset → Kubernetes assigns one
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
```

### `base/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - deployment.yaml
  - service.yaml
```

> **`resources` is the manifest list.** *"If I had other files here that I did not mention, Kustomize will not take action on those files."* It only touches what's listed.

### `overlays/dev/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

nameSuffix: -dev

resources:
  - ../../base        # ← relative to THIS directory
```

| Line | Meaning |
|---|---|
| **`nameSuffix: -dev`** | Append `-dev` to **every** resource name |
| **`../../base`** | From `overlays/dev/`, two levels up → `demo1/`, then into `base/` |

> **The path is relative to where you are.** And whatever you call that directory, **it must contain a `kustomization.yaml`** — otherwise the command fails.

### Render it

```bash
cd demo1
kubectl kustomize base           # what the base produces
kubectl kustomize overlays/dev   # what the dev overlay produces
```

**In the dev output, look at the names:**

```yaml
metadata:
  name: nginx-deploy-dev      # ← suffix applied
...
metadata:
  name: nginx-svc-dev
```

> Same for `stage` (`-stage`) and `prod` (`-prod`) — **one line per environment**, applied to every resource listed in the base.

> **This scales:** if the base listed PVCs, ServiceAccounts, RBAC… the suffix would apply to all of them.

### Apply it

```yaml
# kubectl apply -k: "process a kustomization directory"
kubectl apply -k overlays/dev
```

| Flag | Use |
|---|---|
| **`-f`** | Apply a **file** (what you've used all along) |
| **`-k`** | Apply a **kustomization directory** |

```bash
kubectl create ns dev
kubectl create ns stage
kubectl create ns prod
kubectl apply -k overlays/dev
kubectl apply -k overlays/stage
kubectl apply -k overlays/prod
```

> **But note:** without a `namespace:` transformer, these all landed in **`default`** — the lecture creates the namespaces, applies, then re-applies with `-n dev` etc. **Demo 2 fixes this properly.**

### Three problems with this design

| # | Problem | Effect |
|---|---|---|
| 1 | **Not app-scoped naming** | `nginx-svc-dev` — *which application?* |
| 2 | **All environments have 2 replicas** | Dev fine; **prod/stage too small** |
| 3 | **All environments use `nginx:latest`** | **Prod should pin a stable version** |

> These three drive Demo 2.

---

## 6) Demo 2 — Transformers

> **Every entry in `kustomization.yaml` beyond `resources` is a *transformer* — it transforms your YAML.**

The built-ins (see the Kustomize **builtins** documentation page) include:

`namePrefix` · `nameSuffix` · `labels` · `commonAnnotations` · `images` · `namespace` · `replicas` · `configMapGenerator` · `secretGenerator` · `patches` · …

> **Don't memorise syntax** — the docs list each transformer **with examples**. *"You can always refer documentation."*

### `overlays/dev/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namePrefix: app1-
nameSuffix: -dev

labels:
  - pairs:
      environment: dev
    includeSelectors: true

images:
  - name: nginx
    newTag: "latest"          # explicit for readability

commonAnnotations:
  branch: dev
  support-contact: devops@example.com

namespace: dev

replicas:
  - name: nginx-deploy
    count: 2

resources:
  - ../../base
```

### Field by field

#### `namePrefix` / `nameSuffix`

> Result: **`app1-nginx-deploy-dev`** — **app identity is now visible in the name**. Problem 1 solved.

#### `labels` with `includeSelectors`

```yaml
labels:
  - pairs:
      environment: dev
    includeSelectors: true
```

> **`includeSelectors: true`** does three things:
> 1. adds the label to the **object's metadata**,
> 2. adds it to the **`spec.selector`** (for Deployments/Services),
> 3. adds it to the **pod template labels** → **the pods** get the label too.

**`includeSelectors: false`** → the label goes **only on the object**, **not** on selectors or pods.

> **Why does it matter?** A label on the object alone **cannot be used to select pods**. And changing a **selector** changes the Deployment's `.spec.selector`, which is **immutable** — so `includeSelectors: true` on a **running** Deployment can cause an update to fail. Choose deliberately.

**Decision rule:**

| Want the label on pods / selectable | `includeSelectors: true` |
|---|---|
| Want an object-level marker only (billing, ownership) | `includeSelectors: false` |

#### `images`

```yaml
images:
  - name: nginx             # the IMAGE name, not the container name
    newTag: "latest"
```

> **`name` matches the image, not `containers[].name`.** Don't confuse them.

**For prod — a stable tag, quoted:**

```yaml
images:
  - name: nginx
    newTag: "1.22"          # ← double quotes!
```

> *"Ensure you write this tag in double quotes, especially if it is numerical."* YAML may parse an unquoted `1.22` as a **float** — `1.2` — and you'd ship the wrong image.

#### `commonAnnotations`

```yaml
commonAnnotations:
  branch: dev
  support-contact: devops@example.com
```

> Cross-cutting metadata: **which branch**, **who to call** when it breaks. Applied to **every** resource.

#### `namespace`

```yaml
namespace: dev
```

> **No more `-n dev` on the apply.** The namespace is now part of the rendered output — a real fix for Demo 1's mess.

#### `replicas`

```yaml
replicas:
  - name: nginx-deploy
    count: 2
```

> **Targeted by resource name**, so you set a different count per overlay.

### The three overlays, side by side

| | **dev** | **stage** | **prod** |
|---|---|---|---|
| `namePrefix` | `app1-` | `app1-` | `app1-` |
| `nameSuffix` | `-dev` | `-stage` | `-prod` |
| `environment` label | `dev` | `stage` | `prod` |
| `namespace` | `dev` | `stage` | `prod` |
| **`replicas`** | **2** | **3** | **5** |
| **`images.newTag`** | **`"latest"`** | **`"1.22"`** | **`"1.22"`** |

> *"Understand we are adding these things on top of the base."* Anything **not** overridden comes **from the base** — the whole point.

### Render and verify

```bash
kubectl kustomize overlays/dev
```

Look for: annotations added · `environment: dev` on the object **and** selector **and** pods · `namespace: dev` · replicas `2` · image `nginx:latest`.

```bash
kubectl kustomize overlays/prod
```

Look for: **replicas `5`** · `branch: prod` · **`nginx:1.22`**.

### Apply

```bash
kubectl apply -k overlays/dev
kubectl apply -k overlays/stage
kubectl apply -k overlays/prod

kubectl get deploy,svc -A
```

```
NAMESPACE   NAME                     READY
dev         app1-nginx-deploy-dev    2/2
stage       app1-nginx-deploy-stage  3/3
prod        app1-nginx-deploy-prod   5/5
```

```bash
kubectl get deploy -A -o wide      # images
# dev   → nginx:latest
# stage → nginx:1.22
# prod  → nginx:1.22
```

> **All three problems solved** — naming, replicas, image versions — **without duplicating a single manifest.**

### Cleanup

```bash
kubectl delete -k overlays/dev
kubectl delete -k overlays/stage
kubectl delete -k overlays/prod
```

> `delete -k` mirrors `apply -k` — the same rendering, used to remove.

---

## 7) Why Patches At All?

The natural objection: *"Transformers did everything I needed."*

**They didn't.** Transformers are **bounded** — they operate on specific, predefined fields. Look at what they **cannot** do:

| Need | Why a transformer fails |
|---|---|
| **Different `resources.requests/limits` per environment** | No `resources` transformer — and none for a **block that doesn't exist in the base** |
| **Change `containerPort`** | No transformer for it |
| **Remove a field or a label** | Transformers **add/modify**, never remove |
| **Inject environment variables** | No env-var transformer |
| **Add volume mounts** | Nested structure, not covered |
| **Change/add probes** (`liveness`, `readiness`) | Not covered |
| **Add/change resources not in the base at all** | *"You cannot add or change a `resources` block"* |

> **The general rule:** transformers are for **well-known, common** changes. For **anything arbitrary and nested**, you need **patches**.

---

## 8) The Three Patch Types

| Type | Status |
|---|---|
| **`patches`** (generic) | ✅ **Recommended** |
| `patchesJson6902` | ⚠️ **Deprecated** |
| `patchesStrategicMerge` | ⚠️ **Deprecated** |

> **Both non-generic forms are deprecated** — but you'll still find them in the wild.

### Two perspectives on the deprecated forms

| Perspective | Guidance |
|---|---|
| **Production** | **Know all three** — you'll meet them, and you may be asked to **migrate** them to `patches` |
| **Exam** | *"I've heard about `patches`, but they can ask about these too"* — have a **high-level understanding**; the deprecated ones are easy once you know `patches` |

**Migration is trivial** — Section 11 shows the one-command path.

---

## 9) `patches` — Inline (the recommended style)

> **Patch logic lives in the same file** — no separate patch file needed.

```yaml
patches:
  - target:
      group: apps
      version: v1
      kind: Deployment
      name: app1-nginx-deploy-dev
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/env
        value:
          - name: BRANCH
            value: dev
      - op: replace
        path: /spec/template/spec/containers/0/resources
        value:
          requests: { cpu: 100m, memory: 128Mi }
          limits:   { cpu: 200m, memory: 256Mi }
      - op: remove
        path: /metadata/labels/unused
```

### `target` — which object gets patched

| Field | Meaning |
|---|---|
| **`group` / `version` / `kind`** | The object type (`apps` / `v1` / `Deployment`) |
| **`name`** | The object name — **remember: this is the *rendered* name** (`app1-nginx-deploy-dev`), after prefixes/suffixes |

> You can target **StatefulSets, DaemonSets, and even custom resources** — Kustomize doesn't restrict itself to built-ins.

### The three operations

> **`add`, `replace`, `remove`** — *"as DevOps engineers you will only be using these three."* (JSON Patch also defines `move`, `copy`, `test`.)

| `op` | Effect |
|---|---|
| **`add`** | Add a value at a path (or add to an array) |
| **`replace`** | Replace the value at a path |
| **`remove`** | Delete the value at a path |

### The path is a walk down the YAML tree

```
/spec/template/spec/containers/0/env
 └── spec → template → spec → containers → [first container] → env
```

> **`containers/0`** = the **first container** in the list (the nginx container here).

### Two behaviours worth noting

| Operation | If the target doesn't exist |
|---|---|
| **`remove`** | ❌ **Errors** — *"unable to remove non-existing key"* |
| **`replace`** | In the lecture's run, it **added the block** without error |

> **Technical note:** JSON-Patch specifies that `replace` requires an existing target. Behaviour has varied across Kustomize versions, so **if a field may be absent, use `add`** — it is unambiguous. The lecture uses `replace` deliberately to show it can create the block, then remarks on the asymmetry with `remove`.

---

## 10) Demo 3 — Inline Patches

### Setup

Base unchanged. Only the **overlay** changes (as in real life — *"you will typically be only modifying the overlays"*).

```yaml
# overlays/dev/kustomization.yaml  (transformers omitted here for brevity)
patches:
  - target:
      kind: Deployment
      name: app1-nginx-deploy-dev
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/env
        value:
          - name: BRANCH
            value: dev
      - op: replace
        path: /spec/template/spec/containers/0/resources
        value:
          requests: { cpu: 100m, memory: 128Mi }
          limits:   { cpu: 200m, memory: 256Mi }
      - op: remove
        path: /metadata/labels/unused
```

> **`patches` is plural** — you can patch several targets.

### First render → an error, on purpose

```bash
kubectl kustomize overlays/dev
# Error: unable to remove non-existing key: unused
```

> **The `remove` failed because `unused` doesn't exist in the base.** To make it work, add that label to the base — *"my base must have an `unused` label"* — and render again.

> **Lesson:** `remove` demands the key **exist**. That's the difference that makes `remove` predictable and `replace` forgiving.

### Second render → success

The output shows:

- **`resources` block present** on the container (added via `replace`)
- **`unused` label gone**
- **`BRANCH=dev` env var** on the first container
- **The Service unchanged** by patches — only the transformers (prefix, suffix, annotations, labels) touched it

> **This is a useful diagnostic habit:** if a service looks different from what you patched, check whether your `target` actually matched it.

### Apply

```bash
kubectl apply -k overlays/dev
kubectl get all -A                 # 2 pods (dev = 2 replicas)
kubectl get deploy -A -o wide      # nginx:latest
```

### Cleanup

```bash
kubectl delete -k overlays/dev
```

---

## 11) Demo 4 — `patchesJson6902` (deprecated) and Migration

### The deprecated style

```yaml
patchesJson6902:
  - target:
      group: apps
      version: v1
      kind: Deployment
      name: app1-nginx-deploy-dev
    path: patch-container.yaml        # relative to this kustomization
```

`patch-container.yaml`:

```yaml
- op: replace
  path: /spec/template/spec/containers/0/image
  value: nginx:1.22
- op: add
  path: /spec/template/spec/containers/0/env
  value:
    - name: ENV
      value: dev
```

> **Same JSON-Patch format as inline `patches`** — the **only difference is that it lives in a separate file**.

**A digression the instructor makes deliberately:** he pins **`nginx:1.22` in dev**, not `latest`.

> *"95% of the time you'd use the latest in dev. But to troubleshoot, your dev might run the **same version as prod** so you can test a change on top of it."*
>
> **Nothing is written in stone** about dev=latest / prod=n-1. It's **application-specific** — keep your imagination open.

### Apply → a deprecation warning

```bash
kubectl apply -k overlays/dev
# Warning: patchesJson6902 is deprecated, please use patches instead.
#          Run `kustomize edit fix` to update your kustomization automatically.
```

### The fix — and its catch

```bash
kustomize edit fix
```

> ⚠️ **This fails if you only have `kubectl`.** `kustomize` **is** built into `kubectl` for `build`/`apply -k`, but the **`edit` subcommand requires the standalone `kustomize` binary** — install it from the Kustomize releases page.

After installing, run it **inside the overlay directory**:

```bash
cd overlays/dev
kustomize edit fix
```

**What it does:** rewrites

```yaml
patchesJson6902:
  - target: {...}
    path: patch-container.yaml
```

into

```yaml
patches:
  - target: {...}
    path: patch-container.yaml      # ← same file, new key
```

> **The unified `patches` field supports `path:` too** — so migration is a **key rename**, nothing more. Re-apply: **no warnings**.

---

## 12) Demo 5 — `patchesStrategicMerge` and Its Migration

```yaml
# overlays/dev/kustomization.yaml
patchesStrategicMerge:
  - patch-container.yaml
```

`patch-container.yaml` — **a YAML fragment, not JSON Patch:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app1-nginx-deploy-dev
spec:
  template:
    spec:
      containers:
        - name: nginx
          env:
            - name: ENV
              value: dev
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 200m, memory: 256Mi }
```

> **Strategic merge = "the whole YAML, containing only what you want to change."** No `op`/`path` — just the shape, and Kubernetes' merge semantics apply (lists merge **by key**, e.g. containers by `name`).

### Apply → same deprecation warning

```bash
kubectl apply -k overlays/dev
# Warning: patchesStrategicMerge is deprecated ...
```

### Fix

```bash
cd overlays/dev
kustomize edit fix
```

Result:

```yaml
patches:
  - path: patch-container.yaml
```

> **Note the difference:** `patchesStrategicMerge` has **no `target`** — the object is identified **by the fragment's `metadata.name`**. After migration it becomes a bare `patches:` entry with only a `path`.

### The end state

> **Everything lives under `patches:`.** No `patchesJson6902`, no `patchesStrategicMerge`.

**Then choose your style:**

| Style | When |
|---|---|
| **Inline** (`patch: \|-`) | *"This is what I prefer"* — **everything in one file**, easiest to review |
| **Separate file** (`path:`) | Patches are long; you want per-concern files |

> **The instructor's preference is inline**, precisely because *"you can look at one file and see everything we're doing"* — which is also why he stuck with `patches` even before the deprecations.

---

## 13) Key Takeaways

1. **Real applications have many objects per environment** (36+ for three tiers × three environments), and **microservices multiply it**.
2. **Manual bulk edits are error-prone** — labels, annotations, branch names, image tags, replica counts.
3. **The need:** structured, automated, safe updates that **avoid environment-specific copies** of nearly identical YAML.
4. **Kustomize = base + overlays**, using **plain YAML, no templates**.
5. **`kustomization.yaml`** is required (exact name, lowercase) in the base **and** every overlay.
6. **`resources:` lists the manifests** Kustomize will act on — **unlisted files are ignored**.
7. **`base`/`overlays` isn't mandatory but is the industry-accepted layout** — use it.
8. **`kubectl kustomize <dir>`** renders; **`kubectl apply -k <dir>`** applies; **`kubectl delete -k <dir>`** removes.
9. **`-f` = file, `-k` = kustomization directory.**
10. **Overlay paths are relative to the overlay** (`../../base`).
11. **Transformers** are the well-known field-level customizations: `namePrefix`, `nameSuffix`, `labels`, `commonAnnotations`, `images`, `namespace`, `replicas`, `configMapGenerator`, `secretGenerator`…
12. **`includeSelectors: true`** puts a label on the object **and** the selector **and** the pods; `false` puts it **only on the object**.
13. **`images[].name` is the image name**, not the container name.
14. **Quote numeric image tags** (`"1.22"`) or YAML may parse them as floats.
15. **`namespace:` transformer** removes the need for `-n` on every apply.
16. **`replicas:`** sets a per-environment count by **resource name**.
17. **Transformers can't do everything:** no arbitrary nested edits, no removals, no `resources` blocks, no env vars, no probes, no volume mounts.
18. **Patches handle the arbitrary cases** — and there are **three styles**: **`patches`** (recommended), `patchesJson6902` (deprecated), `patchesStrategicMerge` (deprecated).
19. **`patches` supports inline (`patch:`) or a separate file (`path:`)**, and **both JSON-Patch and strategic-merge payloads**.
20. **`target`** (group/version/kind/name) selects the object — **name is the rendered name**, after prefix/suffix.
21. **The three ops: `add`, `replace`, `remove`**; paths walk the YAML tree (`containers/0` = first container).
22. **`remove` errors if the key is absent**; **`replace` may create the block** (behaviour varies — prefer `add` when a field may not exist).
23. **`kustomize edit fix`** migrates both deprecated forms to `patches` — but requires the **standalone `kustomize` binary**, not just `kubectl`.
24. **`patchesStrategicMerge` identifies objects by the fragment's `metadata.name`** (no `target`), which is why its migration drops `target`.
25. **Version policy is not dogma** — dev=latest / prod=stable is common, **not universal**; test cases invert it legitimately.
26. **Kustomize vs Helm:** overlay tool vs package manager; plain YAML vs Go templating; simple vs feature-rich; **learn both, then choose**.

---

## 14) Essential Commands

```bash
# --- Check it's available (it's built into kubectl) ---
kubectl kustomize -h

# --- Structure ---
#   base/{deployment.yaml,service.yaml,kustomization.yaml}
#   overlays/{dev,stage,prod}/kustomization.yaml

# --- Render (dry-run view) ---
kubectl kustomize base
kubectl kustomize overlays/dev
kubectl kustomize overlays/prod

# --- Apply / delete ---
kubectl create ns dev
kubectl apply -k overlays/dev
kubectl apply -k overlays/stage
kubectl apply -k overlays/prod

kubectl delete -k overlays/dev

# --- Alternative: render then pipe ---
kubectl kustomize overlays/dev | kubectl apply -f -

# --- Inspect results ---
kubectl get deploy,svc -A
kubectl get deploy -A -o wide            # images

# --- Migrate deprecated patch styles (needs standalone kustomize) ---
cd overlays/dev
kustomize edit fix
```

### Base kustomization

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
```

### Full overlay with transformers + inline patch

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namePrefix: app1-
nameSuffix: -dev

labels:
  - pairs:
      environment: dev
    includeSelectors: true

images:
  - name: nginx
    newTag: "latest"

commonAnnotations:
  branch: dev
  support-contact: devops@example.com

namespace: dev

replicas:
  - name: nginx-deploy
    count: 2

resources:
  - ../../base

patches:
  - target:
      group: apps
      version: v1
      kind: Deployment
      name: app1-nginx-deploy-dev
    patch: |-
      - op: add
        path: /spec/template/spec/containers/0/env
        value:
          - name: BRANCH
            value: dev
      - op: add
        path: /spec/template/spec/containers/0/resources
        value:
          requests: { cpu: 100m, memory: 128Mi }
          limits:   { cpu: 200m, memory: 256Mi }
      - op: remove
        path: /metadata/labels/unused
```

---

## 15) Quick Self-Check

1. Why does an application with three tiers and three environments produce 36 manifests?
2. Give four changes you'd be asked to make across all environments, and why manual edits fail.
3. What mechanism does Kustomize use instead of templates?
4. What are the two core components, and what do they combine into?
5. Which file must exist in every Kustomize directory, and what happens if it's missing?
6. What does `resources:` do — and what happens to files not listed?
7. Is the `base`/`overlays` layout required? Why use it anyway?
8. Difference between `-f` and `-k`?
9. How do you *preview* what Kustomize will produce without applying it?
10. Why is `../../base` correct from `overlays/dev/`, and what must that directory contain?
11. Name six transformers and what each changes.
12. What does `includeSelectors: true` do that `false` doesn't? When would you choose each?
13. In `images:`, what does `name:` refer to — the container or the image?
14. Why must `newTag: "1.22"` be quoted?
15. How does the `namespace:` transformer change your apply commands?
16. In Demo 1, what three problems did Demo 2 fix?
17. Give five things transformers cannot do, and the mechanism that can.
18. Name the three patch styles and which are deprecated.
19. In `patches`, what does `target` contain, and why must `name` be the *rendered* name?
20. What are the three JSON-Patch operations, and what does `containers/0` mean?
21. Which op errors on a missing key? Which one may create the block?
22. Why did the first `kustomize` render in Demo 3 fail, and how was it fixed?
23. What does `kustomize edit fix` do, and why does it fail on a `kubectl`-only machine?
24. Why does migrating `patchesStrategicMerge` drop the `target` field?
25. Inline vs separate patch file — which does the instructor prefer, and why?
26. Is "dev runs latest, prod runs n-1" a rule? What's the counter-example?
27. Give three differences between Kustomize and Helm.

---

## What's Next (Day 43)

- **Helm** — the **templating-based** approach to Kubernetes configuration, and the head-to-head comparison that lets you choose.

---

*End of Day 42 notes.*
