# ConfigMaps & Secrets — Incremental Learning Notes (Day 28)

> Source: Day 28 of a Certified Kubernetes Administrator (CKA) 2025 course.
> Topic: Decoupling configuration and sensitive data from container images — **ConfigMaps** and **Secrets**.
> How to use: read one chunk at a time, answer the recall questions **before** scrolling to the next chunk, then do the small practice task. Do not read all 14 chunks in one sitting — that defeats the method.
> Companion: this is the **incremental** version. Days 21–27 in this folder are single-pass complete notes; say the word if you also want a complete-notes pass for Day 28.

---

## 1) Incremental Learning Prompt (Copy/Paste)

```text
Act as my incremental Kubernetes tutor for a CKA course.

Source material: Day 28 lecture on ConfigMaps and Secrets — why we decouple configuration
from container images, how ConfigMaps inject env vars and config files, dynamic updates
via mounted volumes, items and subpath, base64 encoding vs encryption, and how Secrets
are consumed as environment variables and as mounted files.

Teach me incrementally, not all at once.

Rules:
1. Break the lecture into small chunks (5–10 minutes each).
2. For each chunk, give:
   - Learning goal
   - Simple explanation
   - Key terms/definitions
   - One analogy
   - 2–3 active-recall questions
   - One small practice/thinking task
3. Wait for my answer before moving to the next chunk.
4. Track progress with a checklist.
5. Correct my misconceptions gently.
6. Use beginner-friendly language and connect ideas to real CKA/DevOps work.
7. Start by giving me the roadmap, then teach only Chunk 1.

Topic: ConfigMaps and Secrets from Day 28 of a CKA course.
```

---

## 2) Progress Tracker

- [ ] Chunk 1: Why ConfigMaps — decoupling and the hardcoded URL
- [ ] Chunk 2: Portability across environments
- [ ] Chunk 3: What a ConfigMap actually is
- [ ] Chunk 4: Environment variables — the foundation
- [ ] Chunk 5: ConfigMap as environment variables
- [ ] Chunk 6: Why a ConfigMap change does not restart your pod
- [ ] Chunk 7: ConfigMap as a volume — keys become files
- [ ] Chunk 8: Dynamic updates — the volume advantage
- [ ] Chunk 9: `items` and `subpath` — mounting less than everything
- [ ] Chunk 10: Why Secrets, and what base64 really is
- [ ] Chunk 11: base64 encode/decode by hand
- [ ] Chunk 12: Secrets as environment variables
- [ ] Chunk 13: Secrets as mounted files
- [ ] Chunk 14: ConfigMap vs Secret — choosing, and staying secure

---

## Chunk 1: Why ConfigMaps — decoupling and the hardcoded URL

**Learning goal:** Understand the concrete problem ConfigMaps solve, using the course's own application example.

### The theme you have heard since Day 01

Decoupling. It has driven every architectural decision in this course.

| Day | What got decoupled |
|---|---|
| **Day 11** | **Monolith → tiered** — web tier, application tier, data tier, optional **middleware** |
| **Day 11** | **Tiered → microservices** — web and middleware split into smaller services |
| **Day 12** | **Frontend → backend** via a Kubernetes **Service** |
| **Day 21** | **Main container → helper containers** (sidecar, ambassador, adapter) |
| **Day 28** | **Configuration → container image** ← today |

### The Day 11 recap in one paragraph

Monolith = one codebase on one server. Then a **tiered architecture**: web tier serves web requests, application tier holds business logic, data tier stores data, and **middleware** handles everything that is *not* core logic — authentication, logging, caching, API communication, service coordination.

Why bother? Because in the monolith, **touching the web tier meant modifying the entire codebase**. In the tiered design you touched one tier. Microservices went further: split each tier into independent services, so **if the wishlist service dies, browsing and ordering still work**.

### Now the Kubernetes version of the question

Day 12's setup:

```
frontend-deploy  ──►  backend-svc  ──►  backend-deploy (any available pod)
```

The frontend pods reach the backend through `backend-svc`. **How do the frontend pods know that URL?**

> Because you **embedded it in the core logic of the application**. Hardcoded.

And that contradicts everything we've said: *the application should hold only its business logic.* Authentication, authorization, configuration data — all of it should live somewhere else.

**Configuration is data.** The backend Service URL is configuration. It should not be compiled into the image.

### The analogy

A **printed phone book** baked into a phone. The number changes → you must buy a new phone. What you actually want is an **address book you can edit**: the phone looks up the number each time it dials.

The ConfigMap is that address book. The app says *"look it up in the file"* instead of *"the number is 555-0100."*

### Key takeaway

> ConfigMaps exist to **move configuration out of the container image** and inject it at runtime — the same decoupling principle applied to config rather than code.

### Active recall

1. In the Day 12 example, what exactly was hardcoded, and where?
2. Why does hardcoding a backend Service URL violate the "application holds only business logic" rule?
3. Which earlier lecture introduced this decoupling theme first?

### Practice task

List three pieces of *configuration* (not code) your last application or project needed. For each, decide whether the application currently reads it from code, a file, or an environment variable.

---

## Chunk 2: Portability — the second reason

**Learning goal:** See why hardcoded config breaks across environments, and how a ConfigMap fixes it.

### The environment explosion

You don't have one cluster. You have:

```
dev  →  QA  →  staging  →  production
```

And in each one, the backend Service may be named differently:

| Environment | Service name |
|---|---|
| Production | `backend-prod` |
| Development | `backend-dev` |
| Staging | `backend-staging` |

If the URL is in the code, deploying to dev means:

1. **Change the application code** (or build a different image).
2. Rebuild, re-tag, re-push.
3. And again for QA.
4. And again for staging.

> **How many times will you rebuild the image?** That's not a deployment problem — that's a design problem.

Even the *same* name (`backend-svc`) doesn't save you, because the name appears in several manifests across several environments, and any rename ripples through the image.

### The fix

Move that value into a ConfigMap:

```
application  ──►  "read the config file"  ──►  config file (injected)
                                                     │
                                          production: backend-prod
                                          dev:        backend-dev
```

The application logic is **identical everywhere**. Only the injected data differs.

| Without ConfigMaps | With ConfigMaps |
|---|---|
| Code change per environment | **No** code change |
| New image per environment | **Same image** everywhere |
| Environment knowledge in code | Environment knowledge in **cluster config** |
| Risky, drift-prone | **Portable** |

### Key takeaway

> ConfigMaps give you **one image, many environments** — decoupling *and* portability.

### Active recall

1. Name the four environments discussed, and what differs between them.
2. What is the concrete cost of hardcoding a Service name per environment?
3. What is injected, and what stays identical, once a ConfigMap is used?

### Practice task

Write the "before" and "after" in one line each: before = the app "knows" `backend-prod`; after = the app "knows" _______.

---

## Chunk 3: What a ConfigMap actually is

**Learning goal:** Know the object's shape, scope, and stated limits.

### Definition

> **A ConfigMap stores non-confidential key/value configuration data.**

Three things in that sentence:

- **non-confidential** — nothing secret belongs here
- **key/value** — it's a dictionary, not a file server
- **configuration** — the settings, not the application

### The critical limitation

> **ConfigMaps do not provide encryption or secrecy. Everything in a ConfigMap is plain text.**

Anyone who can read the object (or read the mounted file) sees the value. If you need secrecy, you need a **Secret** (Chunk 10).

### The API shape

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-cm
data:
  app: frontend
  environment: production
```

Everything in YAML is key/value — and `data` is itself a key whose value is a map.

### It is namespaced

```bash
kubectl api-resources | Select-String configmap
# configmaps   cm   v1   true   ConfigMap
```

- Short name **`cm`** → `kubectl get cm`
- **Namespaced = true** → a ConfigMap lives in **one namespace**
- **Pods in `app1` can only use ConfigMaps in `app1`.** A ConfigMap is not cluster-wide shared config.

### Three ways pods consume it

| Mode | Typical use |
|---|---|
| **Environment variables** | Small scalar settings (URLs, flags, log levels) |
| **Command-line arguments** | Less common |
| **Mounted volumes (files)** | Config **files** — nginx.conf, application.yml, certificates |

The lecture demos the first and third. The second is real but rare.

### Key takeaway

> ConfigMap = **namespaced, plain-text, key/value** configuration. Never secrets. Consumed as env vars, args, or files.

### Active recall

1. Can a ConfigMap hold a database password safely? Why not?
2. Is a ConfigMap namespaced or cluster-scoped? What does that imply for a pod in another namespace?
3. Which consumption mode would you use for a full `nginx.conf`?

### Practice task

Write a ConfigMap named `web-cm` in the `default` namespace with `log-level: debug` and `api-timeout: 30s`. Which of the three consumption modes fits each key?

---

## Chunk 4: Environment variables — the foundation

**Learning goal:** Understand env vars *before* ConfigMaps, so the indirection makes sense.

### What they are

> Environment variables are **key/value pairs** the container runtime supplies to the process, which the application reads by key.

The container's process sees them; your app reads them; nothing is baked into the image.

### The YAML

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend-deploy
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: nginx
          image: nginx
          env:                        # a LIST
            - name: APP
              value: frontend
            - name: ENVIRONMENT
              value: production
```

Important details:

- **`env` sits under a specific container** — so each container in a multi-container pod has its **own** env list.
- **`env` is a list** — you can declare many variables.
- `name` = the key, `value` = the value.

### Verifying from inside

```bash
kubectl exec -it deploy/frontend-deploy -- printenv
```

```
APP=frontend
ENVIRONMENT=production
...
```

Or in a shell:

```bash
kubectl exec -it <pod> -- bash
echo $APP            # frontend
```

Different languages read them differently (`process.env.APP` in Node, `os.environ["APP"]` in Python, `$APP` in shell) — but it's the same mechanism.

### The uppercase convention

Uppercase is **not required**. It is a **widely accepted industry convention**. `APP` and `app` both work; pick uppercase and stay consistent.

### Key takeaway

> Env vars = `env:` list under a container, read by key. The **value** is what we're about to stop hardcoding.

### Active recall

1. Where in the manifest does `env` live, and why does that matter in a multi-container pod?
2. Is uppercase mandatory? What is it, then?
3. Which command prints a pod's environment variables?

### Practice task

Add a third env var `LOG_LEVEL=debug` to the manifest above, apply it, and confirm it with `printenv`. Then predict what `kubectl get pods` shows for `AGE`.

---

## Chunk 5: ConfigMap as environment variables

**Learning goal:** Replace hardcoded values with `configMapKeyRef`, and understand the two-key indirection.

### The ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-cm
data:
  app_name: frontend          # note: underscore, deliberately different
  environment: production
```

### The Deployment

```yaml
          env:
            - name: APP                       # env var name INSIDE the container
              valueFrom:
                configMapKeyRef:
                  name: frontend-cm           # which ConfigMap
                  key: app_name               # which key INSIDE that ConfigMap
            - name: ENVIRONMENT
              valueFrom:
                configMapKeyRef:
                  name: frontend-cm
                  key: environment
```

### The two names most people confuse

There are **two separate names**, and they do not have to match:

| Layer | Field | Meaning |
|---|---|---|
| Inside the container | `env[].name` | the **variable name** the app reads |
| Inside the ConfigMap | `configMapKeyRef.key` | the **key** whose value gets injected |

So `name: APP` + `key: app_name` produces:

```
APP=frontend      ← the container sees APP, the value came from app_name
```

The lecture uses different names on purpose, precisely so this distinction is visible. In real manifests you'd usually keep them identical for readability.

### Why bother, vs writing `value:` directly?

Because a ConfigMap can hold **dozens** of values, and this deployment YAML now contains **zero configuration data** — only references. Change the ConfigMap, and every referencing workload gets new values (after a restart — Chunk 6).

### Apply order matters

```bash
kubectl apply -f cm1.yaml               # 1. the ConfigMap FIRST
kubectl apply -f frontend-cm1.yaml      # 2. then the Deployment
```

The Deployment **references** the ConfigMap. If the ConfigMap is missing, the container cannot start (you'll see `CreateContainerConfigError` in practice).

### Inspecting

```bash
kubectl get cm
kubectl describe cm frontend-cm
```

`describe` prints the keys and values **in plain text** — again, no secrecy.

### Key takeaway

> `valueFrom.configMapKeyRef{name, key}` binds an env var to a ConfigMap key. **ConfigMap first, workload second.**

### Active recall

1. In `configMapKeyRef`, what does `name` refer to, and what does `key` refer to?
2. Can the env var name differ from the ConfigMap key? Does it matter functionally?
3. What happens if you apply the Deployment before its ConfigMap exists?

### Practice task

Given a ConfigMap with `db_host: mysql.default.svc` and `db_port: "3306"`, write the `env` block that exposes them as `DB_HOST` and `DB_PORT`.

---

## Chunk 6: Why a ConfigMap change does not restart your pod

**Learning goal:** Learn the single most testable behaviour difference between inline env and ConfigMap-backed env.

### Experiment A — inline env (Chunk 4 manifest)

```bash
kubectl get pods
# frontend-deploy-xxxxx   1/1   Running   0   2m7s      ← age 2m
```

Now edit the Deployment's `value: frontend` → `value: backend`, then `kubectl apply`.

```bash
kubectl get pods
# frontend-deploy-yyyyy   1/1   Running   0   49s       ← age 49s
```

**The pod was replaced.** Why? Because you changed the **pod template**, and a Deployment responds to template changes with a **rolling restart**.

The env var did update — but at the cost of **unplanned, uncontrolled churn** every time someone edits a config value.

### Experiment B — ConfigMap-backed env

```bash
kubectl get pods
# frontend-deploy-zzzzz   1/1   Running   0   2m         ← age 2m

# edit the ConfigMap: app: frontend → app: backend
kubectl apply -f cm1.yaml        # configmap/backend-cm configured

kubectl get pods
# frontend-deploy-zzzzz   1/1   Running   0   2m         ← age STILL 2m — same pod!
```

**No restart.** And now the awkward part:

```bash
kubectl exec -it <pod> -- printenv
APP=frontend          ← still the OLD value
```

The ConfigMap changed, but the running container still has the old env var.

> **Why?** Env vars are resolved **once, when the container starts**. Nothing re-reads them afterwards.

### Making the change take effect

```bash
kubectl rollout restart deployment frontend-deploy
kubectl get pods                       # age 7s — new pod
kubectl exec -it <pod> -- printenv
APP=backend                            # updated
```

Or let the next natural rollout pick it up (a new image, a replica change) — the value is read at each container start.

### The lesson in one table

| Change | Pod restarted automatically? |
|---|---|
| Deployment **pod template** (inline `value:`) | **Yes** — rolling restart |
| **ConfigMap** referenced by env vars | **No** — and the running pod keeps the old value |

> This is both a feature and a trap. Feature: config edits don't nuke your workloads. Trap: your env vars are **stale** until you deliberately roll.

### Key takeaway

> **ConfigMap edits do not restart pods.** Env vars are frozen at container start; use `kubectl rollout restart` to apply them.

### Active recall

1. Why did editing the inline `value:` restart the pod, while editing the ConfigMap did not?
2. After editing a ConfigMap, what does the running pod report for that env var?
3. Which command forces pods to pick up the new values?

### Practice task

Predict the output of `kubectl get pods` (specifically the AGE column) in each of these three cases, then explain each: (a) `kubectl apply` on a ConfigMap used for env vars; (b) `kubectl rollout restart deployment x`; (c) `kubectl apply` on the Deployment after editing an inline `value:`.

---

## Chunk 7: ConfigMap as a volume — keys become files

**Learning goal:** Learn how a ConfigMap becomes a directory of files, and the directory-vs-file rule.

### The ConfigMap (with a whole HTML file inside)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: frontend-cm
data:
  app: frontend
  environment: production
  index.html: |
    <html>
      <title>Welcome</title>
      <h1>This page is served by nginx</h1>
      <p>Welcome to Cloud with Varun</p>
    </html>
```

**Why the `|`?** It's a YAML **literal block scalar** — it preserves formatting (newlines, indentation) exactly. For HTML, JSON, YAML, or shell scripts stored in a ConfigMap or Secret, the pipe is what keeps the file readable and valid. Without it, a multi-line value collapses in confusing ways.

### The Deployment

```yaml
spec:
  volumes:
    - name: html-volume
      configMap:
        name: frontend-cm         # the same "type slot" as emptyDir / hostPath
  containers:
    - name: nginx
      image: nginx
      volumeMounts:
        - name: html-volume
          mountPath: /usr/share/nginx/html
          readOnly: true
```

Notice the **identical foundation** from Days 26–27:

```
1. give a volume to the POD        → spec.volumes (with a type)
2. mount it into the CONTAINERS    → volumeMounts
```

Only the **type key** changed: `emptyDir:` → `hostPath:` → `persistentVolumeClaim:` → **`configMap:`**.

### What actually appears in the container

```bash
kubectl exec -it <pod> -- bash
cd /usr/share/nginx/html
ls
# app   environment   index.html
```

> **Every key in `data` becomes a file. The file's content is the value.**

- `app` file contains `frontend`
- `environment` file contains `production`
- `index.html` file contains the HTML

That's why nginx now serves the custom page at `localhost:31000` — we **replaced** its default `/usr/share/nginx/html/index.html` with ours. **No new image was built.** The configuration was outsourced.

### The directory rule

> **ConfigMaps are mounted as DIRECTORIES.**

If you set `mountPath` to a path that is a **file** (e.g. `.../html/index.html`) **without** `subpath`, the pod will fail — Kubernetes cannot mount a directory onto a file.

```yaml
  # ❌ fails: directory mount target that is a file
  mountPath: /usr/share/nginx/html/index.html
```

So mount at the **directory** level, and let the keys land as files inside it.

### Key takeaway

> A ConfigMap mounts as a **directory**; each `data` key becomes a **file**. Do not point `mountPath` at a file — use a directory (or `subpath`, Chunk 9).

### Active recall

1. In a mounted ConfigMap, what is the relationship between a key and a file?
2. Why does `|` matter for an HTML value?
3. Why can't you set `mountPath` directly to `index.html` here?

### Practice task

Sketch (in words) the resulting directory tree if a ConfigMap named `app-config` has keys: `nginx.conf`, `mime.types`, `log-level`, and it's mounted at `/etc/nginx/conf.d`.

---

## Chunk 8: Dynamic updates — the volume advantage

**Learning goal:** Learn where ConfigMap updates *do* take effect automatically, and where they don't.

### The experiment

With the ConfigMap mounted as a volume, edit it:

```yaml
data:
  app: backend                       # was frontend
  index.html: |
    ...
    <h2>Dark side of the moon!!</h2>  # newly added
```

```bash
kubectl apply -f cm2.yaml            # configured
kubectl get pods                     # SAME pod, same age, no restart
```

Now look inside:

```bash
kubectl exec -it <pod> -- bash

cd /usr/share/nginx/html
cat app                 # backend       ← CHANGED
cat index.html          # ...Dark side of the moon!!   ← CHANGED
```

**The files updated in place. No restart.**

Refresh the browser at `localhost:31000` → the new HTML appears.

### But the env vars from the *same* ConfigMap did not change

```bash
printenv | grep -i app
APP=frontend            # still the old value
```

Because:

| Consumption | How values arrive | Updates? |
|---|---|---|
| **Environment variables** | resolved **once** at container start | **No** — needs a restart |
| **Mounted volume** | kubelet **re-syncs** the files on the volume | **Yes** — dynamically |

> This is the single most important distinction in the whole ConfigMap story: **volume-mounted config is dynamic; env-var config is static.**

The sync isn't instant — kubelet reconciles periodically (commonly within about a minute), so don't expect a sub-second reaction.

### Why "most applications need dynamic"

The instructor's point: *"most of our applications require dynamic"* config. If your app reads a config file at request time (or watches it), the volume approach lets you change behaviour **without touching the pod**.

Contrast with env vars: perfect for values that are fixed for the container's life (a pod name, a region, a log level resolved at boot).

### Key takeaway

> **Volume-mounted ConfigMaps update automatically; env-var ConfigMaps do not.** Choose the mechanism by whether you need live updates.

### Active recall

1. Which consumption mode picked up the ConfigMap edit without a restart?
2. Why did the env var keep the old value even though it came from the same ConfigMap?
3. Roughly how fast do mounted files update, and why isn't it instant?

### Practice task

You need an nginx `nginx.conf` that ops can tune during an incident without restarting pods. Which mechanism do you choose, and what does that imply about the other settings in that ConfigMap?

---

## Chunk 9: `items` and `subpath` — mounting less than everything

**Learning goal:** Control *which* keys get mounted, and how to mount a single key as a file.

### Problem 1 — the whole ConfigMap is mounted, but you only wanted one key

With everything mounted at `/usr/share/nginx/html`, nginx's document root also contains `app` and `environment`. Usually harmless, but sloppy — and sometimes harmful (serving config as static files!).

### Fix — `items`

```yaml
  volumes:
    - name: html-volume
      configMap:
        name: frontend-cm
        items:
          - key: index.html      # key IN the ConfigMap
            path: index.html     # FILENAME created in the mounted directory
```

Result:

```bash
ls /usr/share/nginx/html
# index.html          ← only this file now
```

`items` is a whitelist. Keys not listed are **not** mounted.

> Note: changing `items` changes the volume definition → it changes the pod template → **pods restart automatically** on apply (unlike editing the ConfigMap's data).

### Problem 2 — I really want a single file, not a directory

Recall the directory rule. If `mountPath` must point at a file like `.../index.html`, plain mounting fails.

### Fix — `subpath`

```yaml
      volumeMounts:
        - name: html-volume
          mountPath: /usr/share/nginx/html/index.html
          subpath: index.html        # which FILE from the volume
          readOnly: true
```

Now `index.html` is mounted **as a file at a file path**. (In this configuration you'd typically drop `items`, since `subpath` already selects one key.)

### The `subpath` trade-off — the important one

> **`subpath` breaks dynamic updates.**

Test it: edit `index.html` in the ConfigMap, `kubectl apply`, then `cat` the file in the pod → **still the old content**. Nothing changes until the pod restarts.

| Setup | Appears as | Updates automatically? |
|---|---|---|
| Plain mount (+ optional `items`) | **directory** of files | **Yes** |
| **`subpath`** mount | **single file** | **No** |

Why? Because `subpath` takes a **snapshot** of that specific file at mount time instead of mounting the managed directory that kubelet re-syncs.

### Decision table

| Requirement | Use |
|---|---|
| Mount several config files, want live updates | plain mount at a directory |
| Mount **only** some keys (still a directory) | **`items`** |
| Mount **one key as one file** at a file path | **`subpath`** — accept losing dynamic updates |
| Live updates **and** a single file | Not possible directly — restructure the app/mount |

### Key takeaway

> **`items`** = which keys; **`subpath`** = mount one key as a file — but `subpath` sacrifices automatic updates.

### Active recall

1. What does `items` filter — keys, files, or namespaces?
2. When is `subpath` *required* rather than optional?
3. What do you lose by using `subpath`?

### Practice task

A ConfigMap has `nginx.conf` and `index.html`. You need nginx's config at `/etc/nginx/nginx.conf` (a file path) and the page at `/usr/share/nginx/html/` (a directory). Write the two `volumeMounts` entries.

---

## Chunk 10: Why Secrets, and what base64 really is

**Learning goal:** Know the use cases for Secrets and — crucially — that base64 is **not** encryption.

### What applications need to keep secret

| Sensitive data | Where it's used |
|---|---|
| **Database credentials** | username/password to connect to the DB |
| **API tokens** | authenticating to third-party services |
| **SSH private keys** | connecting to servers over SSH |
| **TLS certificates** | identity verification over HTTPS |

All of these were previously **in the container** — and Chunk 3 established that a ConfigMap is **plain text**.

### What a Secret is

> **A Secret stores and manages sensitive information. Secrets are base64-encoded.**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: frontend-secret
type: Opaque
data:
  db_user: ZnJvbnQtZW5kLXVzZXI=        # base64
  db_password: ZnJvbnQtZW5kLXBhc3M=
```

- **`type: Opaque`** = arbitrary key/value data (the default, generic type).
- `data` values must already be **base64-encoded**. (Secrets also accept `stringData` if you want to write plain text and let Kubernetes encode it — a convenience outside this lecture.)
- Same three consumption modes as ConfigMaps: env vars, args, files.

### Encoding vs encryption — get this right

| | **Encoding (base64)** | **Encryption** |
|---|---|---|
| Purpose | Represent data safely in text form | **Hide** data |
| Reversible by | **Anyone** — a website, `base64 -d`, any tool | Only the holder of the **key** |
| Protects against a reader? | **No** | **Yes** |
| Used by default Secrets | **Yes** | **No** |

> **Base64 is a representation, not a lock.** Anyone who can read the Secret object can decode it in one command. This is a very common interview/exam gotcha.

### So how do you actually secure them?

- **RBAC** — restrict *who* can `get`/`list` Secrets (the Security section of the course).
- **External secret managers** — **HashiCorp Vault**, **AWS Secrets Manager**, **Sealed Secrets** (the instructor's recommendation for going further).
- *(Beyond the lecture: etcd encryption at rest, and `Secret` types like `kubernetes.io/tls` and `kubernetes.io/dockerconfigjson` for specific shapes.)*

### Key takeaway

> Secrets are **base64-encoded, not encrypted**. Default protection comes from **RBAC**, not the encoding — use an external manager when you need real secrecy.

### Active recall

1. Name four kinds of sensitive data Secrets typically hold.
2. Is base64 encryption? What can any reader still do?
3. What gives Secrets their actual protection in a cluster?

### Practice task

Explain to a colleague — in two sentences — why "it's base64, so it's secure" is wrong, and what you'd do instead.

---

## Chunk 11: base64 encode/decode by hand

**Learning goal:** Be able to produce and verify a Secret's `data` values without guessing.

### Decode what's in the manifest

```bash
echo -n 'ZnJvbnQtZW5kLXVzZXI=' | base64 --decode
# front-end-user
```

### Encode a value you want to store

```bash
echo -n 'front-end-user' | base64
# ZnJvbnQtZW5kLXVzZXI=
```

Same string, round trip. That's the entire mechanic.

### Why `-n` matters

`echo` without `-n` appends a **newline**, and that newline gets encoded too:

```bash
echo 'front-end-user' | base64        # encodes "front-end-user\n"
echo -n 'front-end-user' | base64     # encodes "front-end-user"
```

The results differ, and the trailing `\n` can break a password, a token, or a TLS key. **Always `-n`.**

### On Windows PowerShell

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('front-end-user'))
```

`[Text.Encoding]::UTF8` avoids the newline problem by construction.

### Verifying from the cluster

```bash
kubectl get secret frontend-secret -o yaml
# data:
#   db_password: ZnJvbnQtZW5kLXBhc3M=
#   db_user: ZnJvbnQtZW5kLXVzZXI=
```

`-o yaml` shows the **encoded** values — the object stores base64.

But:

```bash
kubectl describe secret frontend-secret
# Data
# ====
# db_password:  14 bytes
# db_user:      14 bytes
```

`describe` **hides the values** and shows only byte counts. (`describe` is "safe"; `-o yaml` is "raw".)

### Key takeaway

> `echo -n '<value>' | base64` to encode, `| base64 --decode` to read. **`-n` always**, or you encode a newline.

### Active recall

1. What does omitting `-n` do to the encoded output?
2. Which command shows a Secret's raw encoded values, and which only shows byte counts?
3. Decode `cHJvZHVjdGlvbg==` in your head or with a tool — what is it?

### Practice task

Create the base64 for `S3cr3t-P@ss` and for the same string with a trailing newline. Compare the two outputs and note the difference in length.

---

## Chunk 12: Secrets as environment variables

**Learning goal:** Wire a Secret into a container and understand the decoding behaviour.

### The Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: frontend-secret
type: Opaque
data:
  db_user: ZnJvbnQtZW5kLXVzZXI=        # front-end-user
  db_password: ZnJvbnQtZW5kLXBhc3M=    # front-end-pass
```

### The Deployment

```yaml
          env:
            - name: DB_USER
              valueFrom:
                secretKeyRef:            # ← secretKeyRef, not configMapKeyRef
                  name: frontend-secret
                  key: db_user
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: frontend-secret
                  key: db_password
```

Structurally identical to Chunk 5 — only `configMapKeyRef` → **`secretKeyRef`**.

### The surprise worth memorising

```bash
kubectl exec -it <pod> -- printenv
```

```
DB_USER=front-end-user
DB_PASSWORD=front-end-pass
```

> **The Secret object stores base64. The container receives plain, decoded values.**

Kubernetes decodes on injection. Your application does **no** decoding — it reads `DB_USER` like any other env var. This is the detail candidates get wrong: base64 exists **in the API object**, not in the container.

### Apply order

```bash
kubectl apply -f secret-1.yaml                 # Secret first
kubectl apply -f frontend-secret-1.yaml        # then the Deployment
```

### The same staleness rule applies

Secret edits do **not** restart pods (identical to ConfigMap env vars — Chunk 6). `kubectl rollout restart deployment <name>` to pick up rotated credentials.

### Key takeaway

> `secretKeyRef` injects a **decoded** value as an env var. Base64 lives in the object; the container sees plaintext.

### Active recall

1. Which field replaces `configMapKeyRef` when using a Secret?
2. What does `printenv` show for a Secret-backed env var — encoded or decoded?
3. After rotating a Secret, what must you do for running pods to see it?

### Practice task

A Secret has `api_token` containing `dG9rZW4tMTIz`. Write the `env` entry that exposes it as `API_TOKEN`, and state exactly what `printenv` will print.

---

## Chunk 13: Secrets as mounted files

**Learning goal:** Mount a Secret as files — the pattern real TLS keys and certificates use.

### The manifest

```yaml
spec:
  volumes:
    - name: secret-volume
      secret:
        secretName: frontend-secret       # ← secret, not configMap
  containers:
    - name: nginx
      image: nginx
      volumeMounts:
        - name: secret-volume
          mountPath: /etc/secrets
          readOnly: true
```

### What you see inside

```bash
kubectl exec -it <pod> -- bash
cd /etc/secrets
ls
# db_password   db_user          ← each key is a file

cat db_user
# front-end-user                 ← DECODED
```

Same rules as ConfigMaps:

- Mount point is a **directory**; keys become **files**.
- File contents are **decoded** values.
- `items` and `subpath` work exactly as in Chunk 9 (including `subpath` killing dynamic updates).
- Default file mode is `0644`; Secrets also support `defaultMode: 0400` for tighter permissions.

### Why this is the production pattern

Certificates and private keys are **multi-line files**, not scalar settings:

```yaml
data:
  tls.crt: <base64 of the whole PEM certificate>
  tls.key: <base64 of the whole private key>
```

You mount them as files at the exact path the server expects (`/etc/nginx/certs/`) — an env var holding a PEM bundle would be unusable.

> Guidance from the lecture: **env vars for simple key/value pairs, mounted files for certificates/private keys/config files.** (Secret type `kubernetes.io/tls` exists for exactly the `tls.crt`/`tls.key` pair.)

### Key takeaway

> Secret + volume = **directory of decoded files**. This is how certificates, private keys, and multi-line credentials are delivered.

### Active recall

1. Which key in `spec.volumes` makes it a Secret volume?
2. Are the mounted file contents encoded or decoded?
3. Why are certificates delivered as files rather than env vars?

### Practice task

You have a PEM private key and a PEM certificate. Write the volume + volumeMount that puts them at `/etc/tls/tls.key` and `/etc/tls/tls.crt` — and say which Secret type you'd use.

---

## Chunk 14: ConfigMap vs Secret — choosing, and staying secure

**Learning goal:** Consolidate the comparison and the production rules.

### Side-by-side

| | **ConfigMap** | **Secret** |
|---|---|---|
| Purpose | Non-confidential config | Sensitive data |
| Stored as | **Plain text** | **base64-encoded** |
| Encryption | None | **None by default** (encoding ≠ encryption) |
| Key field | `data` | `data` (or `stringData` for convenience) |
| Type field | — | `type: Opaque` (default) |
| Env injection | `configMapKeyRef` | `secretKeyRef` |
| Volume injection | `configMap:` | `secret:` |
| Env updates | Require restart | Require restart |
| Volume updates | **Automatic** (unless `subpath`) | **Automatic** (unless `subpath`) |
| `describe` output | **Shows values** | **Hides values** (byte counts) |
| `-o yaml` output | Plain text | base64 |
| Scope | Namespaced | Namespaced |
| Real protection | n/a | **RBAC** + external managers |

> The two objects are **structurally identical** — same three consumption modes, same directory-of-files mounting, same staleness rules. Only the payload and the reference field change. Learn one, and you have learned both.

### Production rules worth memorising

1. **Never** put secrets in a ConfigMap — it's plain text in the object, in `describe`, and in `-o yaml`.
2. **Never** commit Secret manifests with real values to Git — use **Sealed Secrets** or an external manager.
3. **Restrict Secret access with RBAC** — `get`/`list` on Secrets is effectively decrypt access.
4. **Prefer mounted volumes** when you need live updates; prefer env vars for boot-time scalars.
5. **Beware `subpath`** — convenient for single files, but it silently disables updates.
6. **Roll after rotating** — `kubectl rollout restart` after changing env-var-backied config/credentials.
7. **Same namespace** — a pod cannot reference a ConfigMap or Secret from another namespace.
8. **Create config before workloads** — otherwise pods stall (`CreateContainerConfigError`).

### Key takeaway

> ConfigMap and Secret are the same machine with different payload and different reference fields. **The security comes from RBAC and external managers, not from base64.**

### Active recall

1. Give three differences and three similarities between ConfigMap and Secret.
2. Why does `kubectl describe secret` show byte counts instead of values?
3. List four production rules from the list above, from memory.

### Practice task

Design the config for an app needing: `DB_HOST` (non-sensitive), `DB_PASSWORD` (sensitive), and a multi-line `ca.crt`. State object(s), consumption mechanism for each, and whether updates will be live.

---

## 15) Recap & Final Check

### The one-line summary per chunk

| Chunk | In one line |
|---|---|
| 1 | Hardcoding config in the image breaks decoupling — ConfigMaps move it out |
| 2 | One image, many environments — configurability equals portability |
| 3 | ConfigMap = namespaced, **plain-text**, key/value config |
| 4 | Env vars are `env:` lists under a container, read by key |
| 5 | `configMapKeyRef{name,key}` — two names, not necessarily equal |
| 6 | **ConfigMap edits don't restart pods**; env vars are frozen at start |
| 7 | Mounted ConfigMap = a **directory**; keys become **files** |
| 8 | **Volume config updates live; env config doesn't** |
| 9 | `items` filters keys; **`subpath` mounts a file but kills live updates** |
| 10 | Secrets are **base64, not encrypted** |
| 11 | `echo -n … \| base64` — and `-n` is mandatory |
| 12 | `secretKeyRef` delivers **decoded** values to the container |
| 13 | Secret volume = decoded files; the pattern for certs and keys |
| 14 | Same machine, different payload; **RBAC is the real security** |

### Common pitfalls (all seen in the demos)

- **Applying the Deployment before the ConfigMap/Secret** → pod can't start.
- **Expecting an env var to update** after editing the ConfigMap → it stays stale until restart.
- **Pointing `mountPath` at a file** without `subpath` → mount fails.
- **Putting a multi-line value in YAML without `|`** → formatting collapses.
- **Encoding with `echo` instead of `echo -n`** → hidden newline in your password.
- **Assuming base64 means secure** → anyone with read access can decode.
- **Forgetting `kubectl rollout restart`** after rotating a credential.
- **Trying to reference a ConfigMap across namespaces** → not found.

### Mini exam (answer without looking back)

1. Write, from memory, a ConfigMap `app-cm` with `mode: fast` and a Deployment env var `MODE` sourced from it.
2. What changes in the previous answer if `mode` were a password?
3. You edit a ConfigMap mounted at `/etc/config`. What do you observe in the pod, and after how long?
4. Same question, but the mount used `subpath`. What's different?
5. A colleague says "our Secret is encrypted, so it's safe." Correct them in one sentence.
6. Which single field distinguishes ConfigMap injection from Secret injection — in env vars, and in volumes?

### If you can answer all six, you are ready for the exam questions on this topic.

---

## What's Next (Day 29)

- **DaemonSets** — one pod per node, and what they're for (node-level agents: logging, monitoring, CNI).

---

*End of Day 28 incremental notes.*
